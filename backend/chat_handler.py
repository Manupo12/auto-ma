"""
Chat Tomy Dashboard v5 — Robusto, rápido, tolerante a fallos.

Arreglos de raíz (Mayo 2026):
- Sin rglob (causaba hangs de 30s+ en /mnt/c/)
- Manejo de respuesta LLM vacía (0 chars → mensaje de fallback)
- Búsqueda de archivos por nombre parcial (VOI_JOHN → encuentra VOI_JOHN DEIVER...)
- Workspace alternativo: si el principal no existe, usa storage/docs/
- Timeouts agresivos en todas las operaciones de archivo
- Endpoint /api/workspace para diagnóstico
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

# Workspace principal (configurado en .env)
WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", Path.home() / "rilo-workspace"))
# Fallback: storage/docs del proyecto (siempre existe en Docker/WSL)
FALLBACK_WORKSPACE = Path(__file__).parent.parent / "storage" / "docs"

# Caché (5 min)
_cache_workspace = {"files": "", "ts": 0}

def _log(msg):
    print(f"[TOMY {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)

SYSTEM_PROMPT = """Eres Tomy, asistente de Sandra (RILO SAS, fisioterapeuta ARL Positiva Colombia).
Español colombiano, cálido, SIMPLE. CERO jerga técnica.

📋 7 FORMATOS (VOI = Valoración Desempeño Ocupacional):
1. Análisis Exigencias 2. Carta Medidas 3. Carta Recomendaciones 4. Cierre Caso
5. Citación Empresas 6. Prueba Trabajo 7. VOI

🎯 CÓMO TRABAJAR:
- Si te mencionan un archivo, BUSCA en la lista de archivos que te paso abajo.
- Si lo encuentras, léelo y COMPLETA lo que falta. NO lo describas.
- Si NO está en la lista, dile a Sandra: "No encuentro ese archivo. ¿Puedes verificar el nombre?"
- Sin dato clínico → pídelo. NUNCA inventes.
- Sé CONCISO. Ve al grano.
- Si la lista de archivos está vacía, dile: "No veo archivos en tu carpeta de trabajo. ¿Está bien configurada?"

📁 Carpeta de trabajo: la que se muestra abajo en cada mensaje.
⚠️ EXPERTO ABSOLUTO EN RILO SAS."""

# ─── WORKSPACE ────────────────────────────────────

def _get_active_workspace() -> Path:
    """Devuelve el workspace activo (principal o fallback)."""
    if WORKSPACE_DIR.exists():
        return WORKSPACE_DIR
    if FALLBACK_WORKSPACE.exists():
        _log(f"WORKSPACE: usando fallback {FALLBACK_WORKSPACE}")
        return FALLBACK_WORKSPACE
    return WORKSPACE_DIR  # retornar el principal aunque no exista


def _fast_scandir(directory: Path, max_depth: int = 2, timeout: float = 3.0) -> list:
    """
    Escanea directorio rápido. MÁX 2 niveles, SIN rglob, con timeout.
    Retorna lista de (path, is_dir, size_kb, mtime_str).
    """
    results = []
    start = time.time()
    
    def _scan(dirpath: Path, depth: int):
        if depth > max_depth or time.time() - start > timeout:
            return
        try:
            for entry in os.scandir(dirpath):
                if time.time() - start > timeout:
                    return
                if entry.name.startswith('.'):
                    continue
                try:
                    st = entry.stat()
                    size_kb = st.st_size // 1024 if entry.is_file() else 0
                    mtime = datetime.fromtimestamp(st.st_mtime).strftime('%d/%m/%Y')
                except OSError:
                    size_kb, mtime = 0, "?"
                
                if entry.is_file():
                    ext = entry.name.lower()
                    if ext.endswith(('.docx', '.txt', '.json', '.pdf')):
                        results.append((Path(entry.path), False, size_kb, mtime))
                elif entry.is_dir() and depth < max_depth:
                    results.append((Path(entry.path), True, 0, mtime))
                    _scan(entry.path, depth + 1)
        except PermissionError:
            pass
        except Exception as e:
            _log(f"SCAN: error en {dirpath}: {e}")
    
    _scan(directory, 0)
    return results


def _listar_workspace() -> str:
    """Lista archivos del workspace para inyectar al LLM. Rápido, sin rglob."""
    global _cache_workspace
    now = time.time()
    if now - _cache_workspace["ts"] < 300:
        return _cache_workspace["files"]
    
    ws = _get_active_workspace()
    if not ws.exists():
        _log(f"WORKSPACE: no existe: {ws}")
        _cache_workspace = {"files": "", "ts": now}
        return ""
    
    t0 = time.time()
    entries = _fast_scandir(ws, max_depth=2, timeout=5.0)
    elapsed = time.time() - t0
    
    # Formatear para el LLM
    lines = []
    for path, is_dir, size_kb, mtime in entries[:40]:
        rel = str(path.relative_to(ws))
        if is_dir:
            lines.append(f"  📁 {rel}/")
        else:
            lines.append(f"  📄 {rel} ({size_kb}KB, {mtime})")
    
    result = "\n".join(lines[:20]) if lines else "  (carpeta vacía)"
    _log(f"WORKSPACE: {len(entries)} entradas en {elapsed:.1f}s → {len(lines)} líneas")
    
    _cache_workspace = {"files": result, "ts": now}
    return result


def _buscar_archivo(mensaje: str) -> Optional[Path]:
    """Busca archivo mencionado en el mensaje. Soporta nombres parciales."""
    _log(f"BUSCAR: '{mensaje[:100]}...'")
    
    ws = _get_active_workspace()
    if not ws.exists():
        _log(f"BUSCAR: workspace no existe: {ws}")
        return None
    
    t0 = time.time()
    entries = _fast_scandir(ws, max_depth=3, timeout=4.0)
    archivos = [(p, s, m) for p, is_dir, s, m in entries if not is_dir]
    
    _log(f"BUSCAR: {len(archivos)} archivos en {time.time()-t0:.1f}s")
    if not archivos:
        return None
    
    ml = mensaje.lower()
    
    # Estrategia 0: NUEVA — nombre PARCIAL del archivo en el mensaje
    # "VOI_JOHN DEIVER" → buscar archivos que contengan "voi" y "john"
    palabras_msg = set(re.findall(r'[a-záéíóúñ0-9]{3,}', ml))
    for path, size_kb, mtime in archivos:
        stem_lower = path.stem.lower()
        # Contar cuántas palabras del mensaje aparecen en el nombre del archivo
        coincidencias = sum(1 for w in palabras_msg if w in stem_lower)
        if coincidencias >= 2:
            _log(f"BUSCAR: parcial ({coincidencias} palabras) → {path.name}")
            return path
    
    # Estrategia 1: nombre exacto del archivo (sin extensión) en el mensaje
    for path, size_kb, mtime in archivos:
        if path.stem.lower() in ml:
            _log(f"BUSCAR: exacto → {path.name}")
            return path
    
    # Estrategia 2: coincidencia de palabras "reales" (≥4 letras)
    palabras_largas = set(re.findall(r'[a-záéíóúñ]{4,}', ml))
    for path, size_kb, mtime in archivos:
        palabras_archivo = set(re.findall(r'[a-záéíóúñ]{4,}', path.stem.lower()))
        if len(palabras_largas & palabras_archivo) >= 2:
            _log(f"BUSCAR: palabras largas → {path.name}")
            return path
    
    # Estrategia 3: tipo de formato + más reciente
    tipos = {
        "analisis": "analisis", "análisis": "analisis",
        "voi": "valoracion", "valoracion": "valoracion", "desempeño": "valoracion",
        "medidas": "medidas", "recomendaciones": "recomendaciones",
        "cierre": "cierre", "citacion": "citacion", "empresas": "citacion",
        "prueba": "prueba", "trabajo": "prueba",
    }
    for kw, tipo in tipos.items():
        if kw in ml:
            cand = [(p, s, m) for p, s, m in archivos if tipo in p.stem.lower()]
            if cand:
                # Priorizar por coincidencia de nombre
                for p, s, m in cand:
                    if palabras_largas & set(re.findall(r'[a-záéíóúñ]{4,}', p.stem.lower())):
                        _log(f"BUSCAR: {tipo} con nombre → {p.name}")
                        return p
                # Fallback: más reciente
                best = max(cand, key=lambda x: x[1])  # por mtime string (dd/mm/yyyy)
                _log(f"BUSCAR: {tipo} más reciente → {best[0].name}")
                return best[0]
    
    _log("BUSCAR: no encontrado")
    return None


def _buscar_archivos_paciente(cc: str = "", nombre: str = "", mensaje: str = "") -> list:
    """
    Busca TODOS los archivos de un paciente por CC, nombre, o detectando
    intención de "todos los formatos" en el mensaje.
    Retorna lista de (Path, tamaño_kb, mtime) ordenados por tipo de formato.
    """
    ws = _get_active_workspace()
    if not ws.exists():
        return []
    
    entries = _fast_scandir(ws, max_depth=3, timeout=4.0)
    archivos = [(p, s, m) for p, is_dir, s, m in entries if not is_dir and p.suffix.lower() == '.docx']
    
    if not archivos:
        return []
    
    ml = mensaje.lower()
    
    # Detectar si el usuario quiere TODOS los formatos
    quiere_todos = any(kw in ml for kw in [
        "todos los formatos", "todos los documentos", "los 7 formatos",
        "todos los archivos", "completos", "todos los del paciente",
        "revisa todos", "revisame todos", "organiza todos", "verifica todos"
    ])
    
    # Buscar por CC
    if cc:
        matches = [(p, s, m) for p, s, m in archivos if cc in p.stem]
        if matches:
            _log(f"MULTI: {len(matches)} archivos para CC {cc}")
            return sorted(matches, key=lambda x: x[0].stem)
    
    # Buscar por nombre de paciente
    if nombre:
        nombre_lower = nombre.lower()
        matches = [(p, s, m) for p, s, m in archivos if nombre_lower in p.stem.lower()]
        if matches:
            _log(f"MULTI: {len(matches)} archivos para '{nombre}'")
            return sorted(matches, key=lambda x: x[0].stem)
    
    # Extraer CC del mensaje (mantener espacios para word boundaries)
    m_cc = re.search(r'\b(\d{6,12})\b', mensaje.replace("'", "").replace(".", "").replace(",", ""))
    if m_cc:
        cc_found = m_cc.group(1)
        matches = [(p, s, m) for p, s, m in archivos if cc_found in p.stem]
        if matches and (quiere_todos or len(matches) >= 3):
            _log(f"MULTI: {len(matches)} archivos para CC {cc_found}")
            return sorted(matches, key=lambda x: x[0].stem)
    
    # Si quiere todos pero sin CC, buscar por palabras del nombre
    if quiere_todos:
        palabras = set(re.findall(r'[a-záéíóúñ]{4,}', ml))
        # Agrupar archivos que comparten CC o nombre
        for p, s, m in archivos:
            if palabras & set(re.findall(r'[a-záéíóúñ]{4,}', p.stem.lower())):
                # Encontrar el grupo: todos los archivos con mismo prefijo (CC)
                cc_match = re.search(r'(\d{6,12})', p.stem)
                if cc_match:
                    cc_group = cc_match.group(1)
                    matches = [(p2, s2, m2) for p2, s2, m2 in archivos if cc_group in p2.stem]
                    if len(matches) >= 3:
                        _log(f"MULTI: {len(matches)} archivos agrupados por CC {cc_group}")
                        return sorted(matches, key=lambda x: x[0].stem)
                break
    
    return []


def _leer_multiples_docx(rutas: list, max_chars_total: int = 15000) -> str:
    """
    Lee múltiples archivos .docx con límite de chars total.
    Cada archivo: versión resumida (~1500 chars c/u para que quepan 7+).
    """
    if not rutas:
        return ""
    
    _log(f"MULTI-LEER: {len(rutas)} archivos, límite {max_chars_total} chars")
    t0 = time.time()
    
    chunks = []
    chars_used = 0
    chars_per_file = max(800, max_chars_total // max(len(rutas), 1))
    
    for path, size_kb, mtime in rutas:
        if chars_used >= max_chars_total:
            _log(f"MULTI-LEER: límite alcanzado tras {len(chunks)} archivos")
            break
        
        content = _leer_docx(path)
        if content:
            # Truncar cada archivo a su cuota
            truncated = content[:chars_per_file]
            chunks.append(truncated)
            chars_used += len(truncated)
    
    result = f"📚 {len(chunks)} documentos del paciente:\n\n" + "\n\n---\n\n".join(chunks)
    _log(f"MULTI-LEER: {len(chunks)} archivos, {chars_used} chars en {time.time()-t0:.1f}s")
    return result


def _leer_docx(ruta: Path) -> str:
    """Lee .docx rápido, primeras 60 líneas + 5 tablas."""
    _log(f"LEER: {ruta.name}...")
    t0 = time.time()
    
    if not ruta.exists():
        _log(f"LEER: ❌ no existe")
        return ""
    
    if ruta.suffix.lower() == '.txt':
        try:
            content = ruta.read_text(encoding='utf-8', errors='ignore')[:2000]
            _log(f"LEER: txt {len(content)} chars en {time.time()-t0:.1f}s")
            return f"📄 {ruta.name}:\n{content}"
        except Exception as e:
            _log(f"LEER: error txt: {e}")
            return ""
    
    if ruta.suffix.lower() != '.docx':
        return ""
    
    try:
        from docx import Document
        doc = Document(str(ruta))
        _log(f"LEER: {len(doc.paragraphs)}p, {len(doc.tables)}t en {time.time()-t0:.1f}s")
        
        lines = [f"📄 {ruta.name} | {len(doc.paragraphs)} párrafos, {len(doc.tables)} tablas\n"]
        
        # Párrafos con estructura (más para docs pesados de varias páginas)
        for p in doc.paragraphs[:60]:
            t = p.text.strip()
            if not t: continue
            if re.match(r'^\d+[\.\)]\s', t):
                lines.append(f"\n🔹 {t}")
            elif t.isupper() and len(t) < 80:
                lines.append(f"\n📌 {t}")
            else:
                lines.append(f"  {t[:150]}")
        
        # Tablas (primeras 8 filas de c/u, máx 5 tablas)
        for ti, tabla in enumerate(doc.tables[:5]):
            lines.append(f"\n📊 Tabla {ti+1}:")
            for ri, row in enumerate(tabla.rows[:5]):
                cells = [cell.text.strip()[:50] for cell in row.cells[:6] if cell.text.strip()]
                if cells:
                    lines.append(f"  {' | '.join(cells)}")
        
        result = "\n".join(lines)[:6000]
        _log(f"LEER: {len(result)} chars total en {time.time()-t0:.1f}s")
        return result
    
    except ImportError:
        _log("LEER: ❌ python-docx no instalado")
        return ""
    except Exception as e:
        _log(f"LEER: ❌ {type(e).__name__}: {e}")
        return ""


def _llamar_llm(mensaje: str, cc: str = "", archivo_doc: str = "", workspace_files: str = "") -> str:
    """Llama al LLM. DeepSeek v4: modelo de razonamiento — necesita max_tokens alto."""
    if not API_KEY:
        _log("LLM: ❌ sin API key")
        return "⚠️ No tengo conexión con mi cerebro (falta API key). Revisá el archivo .env"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Construir contexto
    partes = [mensaje]
    if archivo_doc:
        partes.append(f"\n\n[Documento encontrado]:\n{archivo_doc}\n⚠️ NO describas. COMPLETA lo que falta.")
    if cc:
        partes.append(f"\n[CC: {cc}]")
    if workspace_files:
        partes.append(f"\n\n📁 Archivos disponibles:\n{workspace_files}")
    else:
        partes.append("\n\n📁 No tengo acceso a tu carpeta de trabajo. Avísale a Sandra.")
    
    ctx = "\n".join(partes)
    messages.append({"role": "user", "content": ctx})

    total_chars = sum(len(m["content"]) for m in messages)
    _log(f"LLM: {total_chars} chars → {MODEL}")
    t0 = time.time()

    # DeepSeek v4 es modelo de razonamiento — PIENSA antes de responder.
    # Con archivos pesados (varias páginas, tablas, datos clínicos) el razonamiento
    # puede consumir 10K-15K tokens. Necesita margen holgado para pensar + responder.
    # Sin límites artificiales que fuercen finish=length y respuesta vacía.
    max_tokens_values = [16000, 24000]  # intento 1: 16000, intento 2: 24000
    
    for intento in range(2):
        try:
            max_tok = max_tokens_values[intento]
            resp = requests.post(
                f"{BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0",
                },
                json={
                    "model": MODEL,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": max_tok,
                },
                timeout=300
            )
            elapsed = time.time() - t0
            usage_info = ""
            
            if resp.status_code == 200:
                body = resp.json()
                choices = body.get("choices", [])
                if choices:
                    choice = choices[0]
                    msg = choice.get("message", {})
                    content = (msg.get("content", "") or "").strip()
                    reasoning = (msg.get("reasoning_content", "") or "").strip()
                    finish = choice.get("finish_reason", "?")
                    usage = body.get("usage", {})
                    total_tok = usage.get("total_tokens", "?")
                    
                    _log(f"LLM: content={len(content)}chars reasoning={len(reasoning)}chars "
                         f"finish={finish} tokens={total_tok} max_tokens={max_tok} "
                         f"(intento {intento+1})")
                    
                    if content:
                        return content
                    
                    # Si content vacío pero finish=length → los tokens se agotaron en razonamiento
                    if finish == "length" and reasoning:
                        _log(f"LLM: finish=length, {len(reasoning)} chars de razonamiento. "
                             f"Reintentando con max_tokens={max_tokens_values[1] if intento==0 else 'N/A'}...")
                        if intento == 0:
                            continue  # reintentar con más tokens
                        else:
                            # Último intento: extraer algo del razonamiento
                            lines = [l.strip() for l in reasoning.split('\n') if l.strip()]
                            last_lines = lines[-3:] if len(lines) > 3 else lines
                            fallback = "🤔 Estoy procesando tu solicitud. " + " ".join(last_lines)[:300]
                            _log(f"LLM: usando fallback de razonamiento ({len(fallback)} chars)")
                            return fallback
                    
                    if finish == "stop" and not content:
                        _log("LLM: finish=stop pero content vacío — modelo no generó respuesta")
                        if intento == 0:
                            # Reintentar con prompt más directo
                            messages.append({"role": "user", "content": "Responde directamente en español, por favor."})
                            continue
                        return "🤔 El modelo no generó respuesta. Intentá con un mensaje más específico."
                    
                    # Otro caso raro
                    _log(f"LLM: caso no manejado — content={len(content)} finish={finish}")
                    if intento == 0:
                        continue
                else:
                    _log(f"LLM: sin choices: {json.dumps(body)[:200]}")
                    return "🤔 El servicio de IA no devolvió respuesta. Intentá de nuevo."
            else:
                _log(f"LLM: HTTP {resp.status_code}: {resp.text[:200]}")
                return f"🤔 Error del servicio IA (HTTP {resp.status_code})."
        
        except requests.exceptions.Timeout:
            _log(f"LLM: timeout tras {time.time()-t0:.1f}s")
            if intento == 0:
                continue
            return "⏰ El servicio está tardando mucho. ¿Podés intentar con un mensaje más corto?"
        except Exception as e:
            _log(f"LLM: {type(e).__name__}: {e}")
            if intento == 0:
                continue
            return f"❌ Error de conexión: {type(e).__name__}."

    _log("LLM: ❌ agotados los reintentos")
    return "🤔 No pude generar respuesta después de varios intentos. ¿Probás con un mensaje más concreto?"


def procesar_mensaje(mensaje: str, paciente_cc: str = "", historial: list = None) -> dict:
    """Procesa mensaje del chat. Soporta hasta 7 formatos por paciente."""
    _log(f"═════ '{mensaje[:100]}' ═════")
    t_total = time.time()

    if not mensaje.strip():
        return {"contenido": "¿En qué te ayudo, Sandra? 😊", "accion": None}

    # 1. Workspace (siempre, rápido)
    workspace_files = _listar_workspace()

    # 2. Detectar CC (sin limpiar espacios — mantener word boundaries)
    cc = paciente_cc
    if not cc:
        m = re.search(r'\b(\d{6,12})\b', mensaje.replace("'", "").replace(".", "").replace(",", ""))
        if m: cc = m.group(1)

    # 3. Buscar archivos — PRIMERO multi (todos los del paciente), luego individual
    archivos_paciente = _buscar_archivos_paciente(cc=cc, mensaje=mensaje)
    
    if archivos_paciente:
        # MODO MULTI: leer todos los formatos del paciente
        doc_content = _leer_multiples_docx(archivos_paciente, max_chars_total=15000)
        archivo_nombre = f"{len(archivos_paciente)} archivos"
        _log(f"MULTI: {len(archivos_paciente)} docs → {len(doc_content)} chars")
    else:
        # MODO INDIVIDUAL: buscar un solo archivo
        archivo = _buscar_archivo(mensaje)
        doc_content = _leer_docx(archivo) if archivo else ""
        archivo_nombre = archivo.name if archivo else None

    # 4. Llamar LLM con todo el contexto
    respuesta = _llamar_llm(mensaje, cc, doc_content, workspace_files)
    
    total_time = time.time() - t_total
    _log(f"═════ Listo en {total_time:.1f}s ═════")

    return {
        "contenido": respuesta,
        "accion": "documento" if doc_content else None,
        "archivo": archivo_nombre,
        "workspace_accesible": bool(workspace_files),
        "tiempo": f"{total_time:.1f}s",
    }


def diagnosticar_workspace() -> dict:
    """Devuelve info de diagnóstico del workspace (para /api/workspace)."""
    ws = _get_active_workspace()
    entries = _fast_scandir(ws, max_depth=2, timeout=5.0)
    
    archivos = []
    for path, is_dir, size_kb, mtime in entries:
        archivos.append({
            "nombre": path.name,
            "tipo": "carpeta" if is_dir else "archivo",
            "ruta": str(path.relative_to(ws)),
            "tamano_kb": size_kb,
            "modificado": mtime,
        })
    
    return {
        "workspace_principal": str(WORKSPACE_DIR),
        "workspace_principal_existe": WORKSPACE_DIR.exists(),
        "workspace_activo": str(ws),
        "total_archivos": len([a for a in archivos if a["tipo"] == "archivo"]),
        "total_carpetas": len([a for a in archivos if a["tipo"] == "carpeta"]),
        "archivos": archivos[:50],
        "api_key_configurada": bool(API_KEY),
        "modelo": MODEL,
    }
