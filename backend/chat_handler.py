"""
Chat Tomy Dashboard v4 — Con contexto de workspace y diagnóstico.
- Siempre inyecta lista de archivos del workspace al LLM
- Diagnóstico paso a paso (logs)
- Respuestas nunca genéricas: conoce los archivos reales
"""
import os, json, re, requests, time, sys, traceback
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError: pass

API_KEY = os.getenv("OPENCODE_GO_API_KEY", "")
BASE_URL = os.getenv("OPENCODE_GO_BASE_URL", "https://opencode.ai/zen/go/v1")
MODEL = os.getenv("LLM_MODEL", "deepseek-v4-pro")
WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", Path.home() / "rilo-workspace"))

# Caché del workspace (5 min TTL)
_cache_workspace = {"files": [], "ts": 0}

def _log(msg):
    """Log con timestamp a stderr (visible en consola uvicorn)."""
    print(f"[TOMY {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)

SYSTEM_PROMPT = """Eres Tomy, asistente de Sandra (RILO SAS, fisioterapeuta ARL Positiva Colombia).
Español colombiano, cálido, SIMPLE. CERO jerga técnica.

📋 7 FORMATOS (VOI = Valoración Desempeño Ocupacional):
1. Análisis Exigencias 2. Carta Medidas 3. Carta Recomendaciones 4. Cierre Caso
5. Citación Empresas 6. Prueba Trabajo 7. VOI

🔑 VERIFICACIÓN OBLIGATORIA CONTRA PORTALES:
- MEDIFOLIOS: server0medifolios.net, user 55162801-2. Siniestro, datos paciente, Hª clínica.
- POSITIVA: positivacuida.positiva.gov.co, user 1075209386MR, pass Rilo2026*. Siniestro OFICIAL, diagnóstico CIE-10.
- NUNCA des por bueno un dato sin verificar. Marcas: ✅ ⚠️ ❌ 👤

🎯 CÓMO TRABAJAR:
- Si mencionan un archivo → YA SABES cuál es porque te paso la lista abajo. Léelo, NO lo describas, COMPLETA lo que falta.
- Secciones objetivas con marcas de verificación. Criterio clínico → pregúntale a Sandra.
- Sin dato → pídelo. NUNCA inventes. Sé CONCISO, ve al grano.
- Si el usuario pregunta "¿qué archivos tengo?" o "¿qué hay en mi carpeta?" → responde con la lista de archivos que te pasé.

📁 Carpeta: C:\\Users\\Sandra\\Desktop\\SANDRA\\ACTIVIDADES OCUPACIONALES
⚠️ EXPERTO ABSOLUTO EN RILO SAS. Breve y efectivo."""

# ─── Funciones ───────────────────────────────────

def _listar_workspace() -> str:
    """Lista archivos del workspace para inyectar al LLM. Con caché 5 min."""
    global _cache_workspace
    now = time.time()
    if now - _cache_workspace["ts"] < 300 and _cache_workspace["files"]:
        return _cache_workspace["files"]

    if not WORKSPACE_DIR.exists():
        _log(f"WORKSPACE: no existe: {WORKSPACE_DIR}")
        return ""

    t0 = time.time()
    files = []
    try:
        for entry in sorted(os.scandir(WORKSPACE_DIR), key=lambda e: e.name):
            if entry.name.startswith('.'): continue
            if entry.is_file() and entry.name.lower().endswith(('.docx', '.txt', '.json', '.pdf')):
                size_kb = entry.stat().st_size // 1024
                mtime = datetime.fromtimestamp(entry.stat().st_mtime).strftime('%d/%m/%Y')
                files.append(f"  📄 {entry.name} ({size_kb}KB, {mtime})")
            elif entry.is_dir():
                # Contar archivos dentro
                try:
                    sub_count = sum(1 for _ in entry.rglob("*") if _.is_file() and not _.name.startswith('.'))
                    if sub_count > 0:
                        files.append(f"  📁 {entry.name}/ ({sub_count} archivos)")
                except PermissionError:
                    pass
            # También buscar en subcarpetas nivel 1
            if entry.is_dir():
                try:
                    for sub in sorted(os.scandir(entry.path), key=lambda e: e.name):
                        if sub.is_file() and sub.name.lower().endswith(('.docx', '.txt', '.json', '.pdf')):
                            size_kb = sub.stat().st_size // 1024
                            mtime = datetime.fromtimestamp(sub.stat().st_mtime).strftime('%d/%m/%Y')
                            files.append(f"  📄 {entry.name}/{sub.name} ({size_kb}KB, {mtime})")
                except PermissionError:
                    pass
    except Exception as e:
        _log(f"WORKSPACE: error escaneando: {e}")

    elapsed = time.time() - t0
    _log(f"WORKSPACE: {len(files)} archivos en {elapsed:.1f}s")

    result = "\n".join(files[:40])  # Máximo 40 archivos para no saturar el prompt
    _cache_workspace = {"files": result, "ts": now}
    return result


def _buscar_archivo(mensaje: str) -> Optional[Path]:
    """Busca archivo específico en el workspace mencionado en el mensaje."""
    _log(f"BUSCAR: '{mensaje[:80]}...'")
    if not WORKSPACE_DIR.exists():
        _log(f"BUSCAR: workspace no existe: {WORKSPACE_DIR}")
        return None

    t0 = time.time()

    # Escanear workspace
    todos = []
    try:
        for entry in os.scandir(WORKSPACE_DIR):
            if entry.name.startswith('.'): continue
            if entry.is_dir():
                try:
                    for sub in os.scandir(entry.path):
                        if sub.is_file() and sub.name.lower().endswith(('.docx', '.txt')):
                            todos.append(Path(sub.path))
                        elif sub.is_dir() and not sub.name.startswith('.'):
                            try:
                                for sub2 in os.scandir(sub.path):
                                    if sub2.is_file() and sub2.name.lower().endswith(('.docx', '.txt')):
                                        todos.append(Path(sub2.path))
                            except PermissionError: pass
                except PermissionError: pass
            elif entry.is_file() and entry.name.lower().endswith(('.docx', '.txt')):
                todos.append(Path(entry.path))
    except Exception as e:
        _log(f"BUSCAR: error: {e}")
        return None

    _log(f"BUSCAR: {len(todos)} archivos en {time.time()-t0:.1f}s")
    if not todos:
        return None

    ml = mensaje.lower()

    # Estrategia 1: nombre exacto
    for a in todos:
        if a.stem.lower() in ml:
            _log(f"BUSCAR: exacto → {a.name}")
            return a

    # Estrategia 2: coincidencia de palabras
    palabras_msg = set(re.findall(r'[a-záéíóúñ]{4,}', ml))
    for a in todos:
        palabras_archivo = set(re.findall(r'[a-záéíóúñ]{4,}', a.stem.lower()))
        coincidencias = palabras_msg & palabras_archivo
        if len(coincidencias) >= 2:
            _log(f"BUSCAR: coincidencia {coincidencias} → {a.name}")
            return a

    # Estrategia 3: tipo de formato
    tipos = {"analisis": "analisis", "análisis": "analisis", "voi": "voi",
             "medidas": "medidas", "recomendaciones": "recomendaciones",
             "cierre": "cierre", "citacion": "citacion", "empresas": "citacion",
             "prueba": "prueba", "valoracion": "valoracion", "desempeño": "valoracion"}

    for kw, tipo in tipos.items():
        if kw in ml:
            cand = [a for a in todos if tipo in a.stem.lower()]
            if cand:
                for a in cand:
                    if palabras_msg & set(re.findall(r'[a-záéíóúñ]{4,}', a.stem.lower())):
                        _log(f"BUSCAR: {tipo} con nombre → {a.name}")
                        return a
                a = max(cand, key=lambda p: p.stat().st_mtime)
                _log(f"BUSCAR: {tipo} más reciente → {a.name}")
                return a

    _log("BUSCAR: no encontrado")
    return None


def _leer_docx(ruta: Path) -> str:
    """Lee .docx con timeout y diagnóstico."""
    _log(f"LEER: {ruta.name}...")
    t0 = time.time()

    if not ruta.exists():
        _log(f"LEER: ❌ no existe: {ruta}")
        return ""

    if ruta.suffix.lower() == '.txt':
        try:
            content = ruta.read_text(encoding='utf-8', errors='ignore')
            _log(f"LEER: {len(content)} chars en {time.time()-t0:.1f}s")
            return f"📄 {ruta.name}:\n{content[:2000]}"
        except Exception as e:
            _log(f"LEER: error txt: {e}")
            return ""

    if ruta.suffix.lower() != '.docx':
        return ""

    try:
        from docx import Document
        doc = Document(str(ruta))
        _log(f"LEER: {len(doc.paragraphs)} párrafos en {time.time()-t0:.1f}s")

        lines = [f"📄 {ruta.name} | {len(doc.paragraphs)} párrafos\n"]
        for p in doc.paragraphs[:25]:
            t = p.text.strip()
            if not t: continue
            if re.match(r'^\d+[\.\)]\s', t):
                lines.append(f"\n🔹 {t}")
            elif t.isupper() and len(t) < 80:
                lines.append(f"\n📌 {t}")
            else:
                lines.append(f"  {t[:150]}")

        # También leer tablas (primeras 5 filas de cada tabla)
        for ti, tabla in enumerate(doc.tables[:3]):
            lines.append(f"\n📊 Tabla {ti+1}:")
            for ri, row in enumerate(tabla.rows[:5]):
                cells = [cell.text.strip()[:40] for cell in row.cells[:6]]
                lines.append(f"  {' | '.join(c for c in cells if c)}")

        result = "\n".join(lines)[:3000]
        _log(f"LEER: {len(result)} chars total")
        return result

    except ImportError:
        _log("LEER: ❌ python-docx NO instalado")
        return ""
    except Exception as e:
        _log(f"LEER: ❌ error: {traceback.format_exc()}")
        return ""


def _llamar_llm(mensaje: str, cc: str = "", archivo_doc: str = "", workspace_files: str = "") -> str:
    """Llama al LLM con diagnóstico."""
    if not API_KEY:
        _log("LLM: ❌ sin API key")
        return "⚠️ Falta configurar OPENCODE_GO_API_KEY."

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    ctx = mensaje
    if archivo_doc:
        ctx = f"{mensaje}\n\n[Documento]:\n{archivo_doc}\n\n⚠️ NO describas. COMPLETA lo que falta."
    if cc:
        ctx += f"\n[CC: {cc}]"

    # SIEMPRE inyectar lista de archivos del workspace
    if workspace_files:
        ctx += f"\n\n📁 Archivos en la carpeta de trabajo:\n{workspace_files}"

    messages.append({"role": "user", "content": ctx})

    total_chars = sum(len(m["content"]) for m in messages)
    _log(f"LLM: enviando {total_chars} chars...")
    t0 = time.time()

    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": messages, "temperature": 0.7, "max_tokens": 1200},
            timeout=60
        )
        elapsed = time.time() - t0
        _log(f"LLM: status={resp.status_code} en {elapsed:.1f}s")

        if resp.status_code == 200:
            text = resp.json()["choices"][0]["message"]["content"].strip()
            _log(f"LLM: respuesta {len(text)} chars")
            return text
        else:
            _log(f"LLM: error {resp.status_code}: {resp.text[:200]}")
            return f"🤔 Error {resp.status_code}. Intenta de nuevo."
    except requests.exceptions.Timeout:
        _log(f"LLM: ⏰ TIMEOUT tras {time.time()-t0:.1f}s")
        return "⏰ Tardé mucho. ¿Puedes ser más breve?"
    except Exception as e:
        _log(f"LLM: ❌ {e}")
        return "❌ Error de conexión."


def procesar_mensaje(mensaje: str, paciente_cc: str = "", historial: list = None) -> dict:
    """Procesa con diagnóstico completo. Siempre inyecta contexto de workspace."""
    _log(f"═════ '{mensaje[:80]}...' ═════")
    t_total = time.time()

    if not mensaje.strip():
        return {"contenido": "¿En qué te ayudo, Sandra? 😊", "accion": None}

    # 1. Listar workspace (siempre)
    workspace_files = _listar_workspace()

    # 2. Buscar archivo mencionado
    archivo = _buscar_archivo(mensaje)
    doc_content = _leer_docx(archivo) if archivo else ""

    # 3. Detectar CC
    cc = paciente_cc
    if not cc:
        m = re.search(r'\b(\d{6,12})\b', mensaje.replace("'", "").replace(".", "").replace(",", ""))
        if m: cc = m.group(1)

    # 4. Llamar LLM con contexto completo
    respuesta = _llamar_llm(mensaje, cc, doc_content, workspace_files)

    _log(f"═════ RESPUESTA en {time.time()-t_total:.1f}s ═════")

    archivo_nombre = archivo.name if archivo else None
    return {
        "contenido": respuesta,
        "accion": "documento" if doc_content else None,
        "archivo": archivo_nombre,
    }
