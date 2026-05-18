"""
Chat Tomy Dashboard v3 — Con diagnóstico incorporado.
Cada paso imprime en consola para detectar EXACTAMENTE dónde se cuelga.
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
- Si mencionan un archivo → búscalo, léelo, NO lo describas, COMPLETA lo que falta.
- Secciones objetivas con marcas de verificación. Criterio clínico → pregúntale a Sandra.
- Sin dato → pídelo. NUNCA inventes. Sé CONCISO, ve al grano.

📁 Carpeta: C:\\Users\\Sandra\\Desktop\\SANDRA\\ACTIVIDADES OCUPACIONALES
⚠️ EXPERTO ABSOLUTO EN RILO SAS. Breve y efectivo."""

# ─── Funciones con diagnóstico ───────────────────────────────────

def _buscar_archivo(mensaje: str) -> Optional[Path]:
    """Busca archivo. Con diagnóstico de cada paso."""
    _log(f"BUSCAR: iniciando búsqueda...")
    if not WORKSPACE_DIR.exists():
        _log(f"BUSCAR: workspace no existe: {WORKSPACE_DIR}")
        return None
    
    triggers = ["formato","documento","archivo","arregla","completa","termina","revisa",
                "analisis","análisis","carta","cierre","citacion","prueba","valoracion",
                "desempeño","exigencias","recomendaciones","medidas","trabajo","voi"]
    if not any(t in mensaje.lower() for t in triggers):
        _log("BUSCAR: sin triggers de archivo")
        return None
    
    _log("BUSCAR: escaneando workspace...")
    t0 = time.time()
    
    # Usar scandir para velocidad máxima (evitar rglob)
    todos = []
    try:
        for entry in os.scandir(WORKSPACE_DIR):
            if entry.name.startswith('.'): continue
            if entry.is_dir():
                try:
                    for sub in os.scandir(entry.path):
                        if sub.is_file() and sub.name.lower().endswith(('.docx','.txt')):
                            todos.append(Path(sub.path))
                        elif sub.is_dir() and not sub.name.startswith('.'):
                            try:
                                for sub2 in os.scandir(sub.path):
                                    if sub2.is_file() and sub2.name.lower().endswith(('.docx','.txt')):
                                        todos.append(Path(sub2.path))
                            except PermissionError: pass
                except PermissionError: pass
            elif entry.is_file() and entry.name.lower().endswith(('.docx','.txt')):
                todos.append(Path(entry.path))
    except Exception as e:
        _log(f"BUSCAR: error escaneando: {e}")
    
    _log(f"BUSCAR: {len(todos)} archivos en {time.time()-t0:.1f}s")
    
    if not todos:
        _log("BUSCAR: cero archivos encontrados")
        return None
    
    ml = mensaje.lower()
    
    # Estrategia 1: nombre exacto de archivo en el mensaje
    for a in todos:
        if a.stem.lower() in ml:
            _log(f"BUSCAR: encontrado por nombre exacto: {a.name}")
            return a
    
    # Estrategia 2: nombre del paciente + tipo de formato
    # Extraer palabras clave del mensaje (nombres propios)
    palabras_msg = set(re.findall(r'[a-záéíóúñ]{4,}', ml))
    for a in todos:
        palabras_archivo = set(re.findall(r'[a-záéíóúñ]{4,}', a.stem.lower()))
        coincidencias = palabras_msg & palabras_archivo
        if len(coincidencias) >= 2:
            _log(f"BUSCAR: encontrado por coincidencia ({len(coincidencias)} palabras): {a.name} → {coincidencias}")
            return a
    
    # Estrategia 3: tipo de formato + nombre paciente
    tipos = {"analisis":"analisis","análisis":"analisis","voi":"voi",
             "medidas":"medidas","recomendaciones":"recomendaciones",
             "cierre":"cierre","citacion":"citacion","empresas":"citacion",
             "prueba":"prueba","valoracion":"valoracion","desempeño":"valoracion"}
    
    for kw, tipo in tipos.items():
        if kw in ml:
            cand = [a for a in todos if tipo in a.stem.lower()]
            if cand:
                # Priorizar por nombre de paciente
                for a in cand:
                    if palabras_msg & set(re.findall(r'[a-záéíóúñ]{4,}', a.stem.lower())):
                        _log(f"BUSCAR: encontrado {tipo} con nombre: {a.name}")
                        return a
                # Fallback: más reciente
                a = max(cand, key=lambda p: p.stat().st_mtime)
                _log(f"BUSCAR: encontrado {tipo} (más reciente): {a.name}")
                return a
    
    _log(f"BUSCAR: no encontrado")
    return None


def _leer_docx(ruta: Path) -> str:
    """Lee .docx con timeout y diagnóstico."""
    _log(f"LEER: intentando abrir {ruta.name}...")
    t0 = time.time()
    
    if not ruta.exists():
        _log(f"LEER: ❌ archivo no existe: {ruta}")
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
        _log(f"LEER: python-docx importado, abriendo...")
        doc = Document(str(ruta))
        _log(f"LEER: abierto en {time.time()-t0:.1f}s, {len(doc.paragraphs)} párrafos")
        
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
        
        result = "\n".join(lines)[:2000]
        _log(f"LEER: {len(result)} chars extraídos en {time.time()-t0:.1f}s")
        return result
        
    except ImportError:
        _log("LEER: ❌ python-docx NO instalado")
        return ""
    except Exception as e:
        _log(f"LEER: ❌ error: {traceback.format_exc()}")
        return ""


def _llamar_llm(mensaje: str, cc: str = "", archivo_doc: str = "") -> str:
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
    
    messages.append({"role": "user", "content": ctx})
    
    total_chars = sum(len(m["content"]) for m in messages)
    total_words = sum(len(m["content"].split()) for m in messages)
    _log(f"LLM: enviando {total_chars} chars (~{total_words} palabras)...")
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
    """Procesa con diagnóstico completo."""
    _log(f"═════ NUEVO MENSAJE: '{mensaje[:80]}...' ═════")
    t_total = time.time()
    
    if not mensaje.strip():
        return {"contenido": "¿En qué te ayudo, Sandra? 😊", "accion": None}
    
    # Buscar archivo
    archivo = _buscar_archivo(mensaje)
    doc_content = _leer_docx(archivo) if archivo else ""
    
    # Detectar CC
    cc = paciente_cc
    if not cc:
        m = re.search(r'\b(\d{6,12})\b', mensaje.replace("'","").replace(".","").replace(",",""))
        if m: cc = m.group(1)
    
    # Llamar LLM
    respuesta = _llamar_llm(mensaje, cc, doc_content)
    
    _log(f"═════ RESPUESTA en {time.time()-t_total:.1f}s ═════")
    
    return {"contenido": respuesta, "accion": "documento" if doc_content else None}
