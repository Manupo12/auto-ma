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
import os, json, re, requests, time, sys, traceback, subprocess
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

SYSTEM_PROMPT = """Eres Tomy, asistente EXPERTO de Sandra (RILO SAS, fisioterapeuta ARL Positiva Colombia).
Tu trabajo NO es solo leer documentos — es ORGANIZAR, VERIFICAR, CRUZAR Y CORREGIR.

═══════════════════════════════════════
📋 LOS 7 FORMATOS (VOI = Valoración Desempeño Ocupacional)
═══════════════════════════════════════
1. Análisis de Exigencias — perfil del cargo, demandas físicas, riesgos
2. Carta de Medidas Preventivas — restricciones, adaptaciones
3. Carta de Recomendaciones — reincorporación, seguimiento
4. Cierre de Caso — logros, estado final, concepto
5. Citación a Empresas — convocatoria, visita, análisis puesto
6. Prueba de Trabajo — tareas, observación, desempeño real
7. VOI (Valoración Desempeño Ocupacional Final) — historia ocupacional, áreas, concepto

═══════════════════════════════════════
🔍 PROTOCOLO DE VERIFICACIÓN (OBLIGATORIO)
═══════════════════════════════════════

POR CADA DATO CLÍNICO O ADMINISTRATIVO QUE ENCUENTRES, INDICÁ:

✅ VERIFICADO — si coincide en 2+ fuentes (ej: mismo siniestro en análisis y en VOI)
⚠️ PENDIENTE PORTAL — si necesita confirmarse en Medifolios o Positiva
❌ DISCREPANCIA — si hay conflicto entre formatos (ej: diagnóstico distinto en medidas vs VOI)
👤 DATO ORAL — si viene solo de las notas de Sandra, sin confirmar

QUÉ VERIFICAR EN MEDIFOLIOS (server0medifolios.net, user 55162801-2):
- Datos personales del paciente (nombre completo, CC, fecha nacimiento, dirección, tel)
- Empresa, EPS, AFP, ARL
- Historia clínica: diagnósticos, antecedentes, alergias
- Siniestro (del campo OBSERVACIONES en Agenda Citas → "NO. SINIESTRO...")

QUÉ VERIFICAR EN ARL POSITIVA (positivacuida.positiva.gov.co, user 1075209386MR):
- Siniestro OFICIAL (pestaña SINIESTROS — ID, fecha, tipo, %PCL)
- Diagnóstico CIE-10 (pestaña REHABILITACIÓN INTEGRAL)
- Datos del asegurado (pestaña DATOS ASEGURADO)
- Autorizaciones, evoluciones, bitácoras
- Matrículas RHI

═══════════════════════════════════════
📊 CÓMO CRUZAR DATOS ENTRE FORMATOS
═══════════════════════════════════════

1. PRIMERO: extraé TODOS los datos de TODOS los formatos
2. LUEGO: hacé una TABLA DE CONSISTENCIA comparando campo por campo:
   - Nombre del paciente: ¿coincide en los 7 formatos?
   - CC: ¿mismo número en todos?
   - Siniestro: ¿mismo ID y fecha?
   - Diagnóstico: ¿mismo CIE-10?
   - Empresa: ¿mismo nombre y NIT?
   - Fechas: ¿son coherentes? (ej: cierre después de valoración)
3. MARCA cada discrepancia con ❌ y sugerí cuál es el valor correcto
4. Si el dato aparece en un solo formato, marcalo ⚠️ PENDIENTE CRUCE

═══════════════════════════════════════
📝 CÓMO ORGANIZAR DATOS CRUDOS DE SANDRA
═══════════════════════════════════════

Sandra escribe sus notas de manera desorganizada. Tu trabajo es EXTRAER y ESTRUCTURAR:

1. Identificá fragmentos de texto que pertenezcan a cada sección del formato
2. Agrupalos bajo encabezados claros: "DATOS PERSONALES", "DIAGNÓSTICO", "METODOLOGÍA", etc.
3. Eliminá repeticiones y contradicciones (señalá las que encuentres)
4. Convertí lenguaje coloquial a lenguaje clínico (pero sin perder el significado)
5. Si falta un dato crítico, indicalo claramente: 🔴 FALTA: [campo] — [dónde obtenerlo]

═══════════════════════════════════════
✏️ CÓMO CORREGIR
═══════════════════════════════════════

Cuando encuentres errores o inconsistencias:
1. Mostrá el texto ORIGINAL (lo que dice ahora)
2. Mostrá el texto CORREGIDO (lo que debería decir)
3. Explicá POR QUÉ en una línea
4. Si la corrección requiere verificación en portal, marcalo ⚠️

Ejemplo:
  ❌ ORIGINAL: "Siniestro 503463870 — Fecha 02/03/2025"
  ✅ CORREGIDO: "Siniestro 503463870 — Fecha 02/03/2026"
  📎 MOTIVO: El año 2025 es anterior a la fecha de atención. ⚠️ Verificar en Positiva.

═══════════════════════════════════════
📋 FORMATO DE RESPUESTA (OBLIGATORIO)
═══════════════════════════════════════

Respondé SIEMPRE con esta estructura:

## 🔍 RESUMEN
[2-3 líneas: cuántos formatos, estado general, hallazgos principales]

## 📊 TABLA DE CONSISTENCIA
[Tabla comparando datos clave entre todos los formatos]
| Campo | Formato 1 | Formato 2 | ... | ¿Coincide? |

## ⚠️ VERIFICACIONES PENDIENTES EN PORTALES
- Medifolios: [lista de lo que hay que verificar]
- Positiva: [lista de lo que hay que verificar]

## 📝 DATOS ORGANIZADOS
[Secciones del formato principal con datos extraídos y organizados de TODOS los formatos]

## ❌ DISCREPANCIAS Y CORRECCIONES
[ORIGINAL → CORREGIDO, con motivo]

## 🔴 CAMPOS FALTANTES
[Lista de lo que falta, dónde obtenerlo, y prioridad]

═══════════════════════════════════════
⚠️ REGLAS DE ORO
═══════════════════════════════════════
- NUNCA inventes datos clínicos. Si no está en los documentos, decilo.
- NUNCA digas solo "falta X". Decí QUÉ falta, POR QUÉ importa, y DÓNDE conseguirlo.
- SIEMPRE cruzá los datos entre formatos antes de responder.
- SIEMPRE marcá qué verificar en portales.
- SIEMPRE organizá antes de corregir.
- Si Sandra escribió algo confuso, interpretalo pero señalá la ambigüedad.
- Español colombiano, cálido pero profesional. CERO jerga técnica innecesaria.

Eres el asistente CLÍNICO definitivo de RILO SAS. THOROUGH. PRECISE. ÚTIL."""

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
    chars_per_file = max(500, max_chars_total // max(len(rutas), 1))
    
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


def _llamar_llm(mensaje: str, cc: str = "", archivo_doc: str = "", workspace_files: str = "",
                historial=None, ctx_sistema: str = "") -> str:
    """Llama al LLM. DeepSeek v4: modelo de razonamiento — necesita max_tokens alto."""
    if not API_KEY:
        _log("LLM: ❌ sin API key")
        return "⚠️ No tengo conexión con mi cerebro (falta API key). Revisá el archivo .env"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Historial (ultimos 6 turnos)
    if historial:
        for h in historial[-6:]:
            rol = h.get("rol", "")
            contenido = (h.get("contenido", "") or "")[:2000]
            if rol == "usuario":
                messages.append({"role": "user", "content": contenido})
            elif rol == "asistente":
                messages.append({"role": "assistant", "content": contenido})

    # Construir contexto
    partes = []
    if ctx_sistema:
        partes.append(ctx_sistema)
    partes.append(f"\n═══ MENSAJE DE SANDRA ═══\n{mensaje}")
    if archivo_doc:
        partes.append(f"\n\n[Documentos encontrados]:\n{archivo_doc}\n⚠️ NO describas. COMPLETA lo que falta.")
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
    max_tokens_values = [16000, 24000]  # intento 1: 16000, intento 2: 24000 (reducido para lotes)
    
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


def _procesar_via_workers(archivos: list, cc: str) -> str:
    """
    Reemplazo de _procesar_en_lotes que aísla cada llamada LLM en subprocess.

    Cada subprocess procesa 1 archivo, imprime JSON con datos extraídos, muere.
    El OS libera la RAM del reasoning_content de DeepSeek al terminar el proceso.

    Para extracción usa LLM_MODEL_EXTRACCION (deepseek-v4-flash por defecto, sin razonamiento).
    Los resultados se concatenan y se devuelven como string para inyectar al contexto.
    """
    modelo_extraccion = os.getenv("LLM_MODEL_EXTRACCION", "deepseek-v4-flash")
    _log(f"WORKERS: {len(archivos)} archivos con modelo={modelo_extraccion}")
    t0 = time.time()

    todos_datos = []
    for i, (path, size_kb, mtime) in enumerate(archivos):
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "backend.lote_worker",
                 "--tipo", "extraer",
                 "--archivos", str(path),
                 "--modelo", modelo_extraccion,
                 "--cc", cc],
                capture_output=True, text=True, timeout=180,
                cwd=str(Path(__file__).parent.parent),
            )
            if proc.returncode == 0 and proc.stdout:
                resultado = json.loads(proc.stdout)
                if resultado.get("ok") and resultado.get("datos_raw"):
                    todos_datos.append(
                        f"═══ DOC {i+1}/{len(archivos)} ({path.name}) ═══\n"
                        f"{resultado['datos_raw']}"
                    )
                    tokens = resultado.get("tokens", {})
                    _log(f"WORKER {i+1}: {tokens.get('total', '?')}t en {resultado.get('tiempo_s', '?')}s")
            else:
                _log(f"WORKER {i+1}: FAILED exit={proc.returncode} stderr={proc.stderr[:200]}")
                todos_datos.append(f"═══ DOC {i+1} ({path.name}) ═══\n[ERROR de extracción]")
        except subprocess.TimeoutExpired:
            _log(f"WORKER {i+1}: TIMEOUT")
            todos_datos.append(f"═══ DOC {i+1} ({path.name}) ═══\n[TIMEOUT]")
        except Exception as e:
            _log(f"WORKER {i+1}: {type(e).__name__}: {e}")
            todos_datos.append(f"═══ DOC {i+1} ({path.name}) ═══\n[{type(e).__name__}]")

    elapsed = time.time() - t0
    resultado_str = "\n\n".join(todos_datos)
    _log(f"WORKERS: {len(archivos)} procesados en {elapsed:.1f}s → {len(resultado_str)} chars")

    return f"""[DATOS EXTRAÍDOS DE {len(archivos)} FORMATOS POR WORKERS AISLADOS]

{resultado_str}

⚠️ Tu tarea con estos datos:
1. CRUZAR campos entre documentos, detectar inconsistencias
2. VERIFICAR contra portales (marcar ✅/⚠️/❌)
3. ORGANIZAR información por secciones
4. CORREGIR discrepancias detectadas
5. COMPLETAR campos faltantes con prioridad"""


def _procesar_en_lotes(archivos: list, cc: str, mensaje_original: str) -> str:
    """
    Procesa muchos archivos en lotes de 3-4. Cada lote: extraer datos clave.
    Luego junta todo y lo devuelve como contexto comprimido para la llamada final.
    Evita OOM en el contenedor sin sacrificar calidad.
    """
    TAMANO_LOTE = 2
    lotes = [archivos[i:i+TAMANO_LOTE] for i in range(0, len(archivos), TAMANO_LOTE)]
    _log(f"LOTES: {len(archivos)} archivos → {len(lotes)} lotes de ~{TAMANO_LOTE}")
    
    EXTRACT_PROMPT = """Extrae TODOS los datos clínicos y administrativos de estos documentos.
Devuelve SOLO datos, en este formato EXACTO:

PACIENTE: [nombre completo] | CC: [número]
SINIESTRO: [id] | FECHA: [dd/mm/aaaa] | TIPO: [AT/EL/EG]
DIAGNÓSTICO: [código CIE-10] - [descripción]
EMPRESA: [nombre] | NIT: [número]
FECHAS: consulta=[fecha], valoración=[fecha], cierre=[fecha]
SEGMENTO: [segmento corporal]
OBSERVACIONES: [datos relevantes, notas de Sandra, campos incompletos]
CAMPOS_VACIOS: [lista de campos que faltan en este documento]

Si un dato no aparece, escribe FALTA."""
    
    todos_los_datos = []
    t0 = time.time()
    
    for i, lote in enumerate(lotes):
        _log(f"LOTE {i+1}/{len(lotes)}: {len(lote)} archivos")
        
        # Leer archivos del lote
        contenido_lote = _leer_multiples_docx(lote, max_chars_total=3000)
        if not contenido_lote:
            continue
        
        # Llamar al LLM para extraer datos
        if not API_KEY:
            todos_los_datos.append(f"[LOTE {i+1}] Sin API key — no se pudo procesar")
            continue
        
        try:
            resp = requests.post(
                f"{BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": EXTRACT_PROMPT},
                        {"role": "user", "content": contenido_lote}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 4000,
                },
                timeout=120
            )
            if resp.status_code == 200:
                body = resp.json()
                choices = body.get("choices", [])
                if choices:
                    content = (choices[0].get("message", {}).get("content", "") or "").strip()
                    if content:
                        todos_los_datos.append(f"═══ LOTE {i+1} ═══\n{content}")
                        _log(f"LOTE {i+1}: extraídos {len(content)} chars")
                    else:
                        _log(f"LOTE {i+1}: respuesta vacía")
                else:
                    _log(f"LOTE {i+1}: sin choices")
            else:
                _log(f"LOTE {i+1}: HTTP {resp.status_code}")
        except Exception as e:
            _log(f"LOTE {i+1}: error {e}")
    
    elapsed = time.time() - t0
    resultado = "\n\n".join(todos_los_datos)
    _log(f"LOTES: {len(lotes)} procesados en {elapsed:.1f}s → {len(resultado)} chars comprimidos")
    
    # Devolver datos comprimidos + instrucción para el cruce final
    return f"""[DATOS EXTRAÍDOS DE {len(archivos)} FORMATOS EN {len(lotes)} LOTES]

{resultado}

⚠️ Con estos datos extraídos, tu tarea es:
1. CRUZAR: comparar campos entre lotes, detectar inconsistencias
2. VERIFICAR: marcar qué confirmar en Medifolios y Positiva
3. ORGANIZAR: estructurar la información por secciones
4. CORREGIR: señalar discrepancias y sugerir correcciones
5. COMPLETAR: listar campos faltantes con prioridad

Mensaje original de Sandra: "{mensaje_original[:200]}" """


def _get_data_dir() -> Path:
    """Retorna el directorio de datos (configurable vía STORAGE_DIR)."""
    storage = Path(os.getenv("STORAGE_DIR", str(Path(__file__).parent.parent / "storage")))
    return storage / "data"


def _cargar_datos_verificados(cc: str) -> Optional[dict]:
    """Busca storage/data/*{cc}*completo.json y lo carga."""
    if not cc:
        return None
    data_dir = _get_data_dir()
    if not data_dir.exists():
        return None
    pattern = f"*{cc}*completo.json"
    matches = sorted(data_dir.glob(pattern), key=os.path.getmtime, reverse=True)
    if not matches:
        return None
    try:
        with open(matches[0], encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _formatear_datos_verificados(datos: dict) -> str:
    """Genera texto con marcas ✅/⚠️/❌ a partir del JSON de orquestador."""
    if not datos:
        return ""
    partes = []
    medi = datos.get("medifolios", {})
    pos = datos.get("positiva", {})

    siniestro_medi = medi.get("siniestro_medi", "[SIN DATO]")
    siniestros_pos = pos.get("siniestros", [])
    siniestro_pos_id = siniestros_pos[0].get("id", "[SIN DATO]") if siniestros_pos else "[SIN DATO]"

    if siniestro_medi == siniestro_pos_id and siniestro_medi != "[SIN DATO]":
        partes.append(f"✅ Siniestro: {siniestro_pos_id} (coincide Medifolios + Positiva)")
    elif siniestro_medi and siniestro_pos_id and siniestro_medi != "[SIN DATO]" and siniestro_pos_id != "[SIN DATO]":
        partes.append(f"❌ Siniestro DISCREPANCIA: Medifolios={siniestro_medi} vs Positiva={siniestro_pos_id}")
        partes.append("   → Prevalece Positiva (fuente oficial)")
    elif siniestro_pos_id and siniestro_pos_id != "[SIN DATO]":
        partes.append(f"✅ Siniestro: {siniestro_pos_id} (Positiva)")
        if siniestro_medi == "[SIN DATO]" or not siniestro_medi:
            partes.append("   ⚠️ No disponible en Medifolios")
    else:
        partes.append("⚠️ Siniestro no disponible en ningún portal")

    nombre_medi = medi.get("nombre1") or medi.get("nombre", "")
    apellido_medi = medi.get("apellido1", "")
    nombre = f"{nombre_medi} {apellido_medi}".strip()
    if nombre:
        partes.append(f"✅ Paciente: {nombre}")
    if medi.get("telefono"):
        partes.append(f"✅ Teléfono: {medi['telefono']}")
    if medi.get("direccion"):
        partes.append(f"✅ Dirección: {medi['direccion']}")

    discrepancias = datos.get("_meta", {}).get("discrepancias", [])
    for d in discrepancias:
        partes.append(f"❌ {d.get('campo', 'desconocido')}: Medifolios={d.get('medifolios','?')} vs Positiva={d.get('positiva','?')}")
        if d.get("resolucion"):
            partes.append(f"   → {d['resolucion']}")

    if not partes:
        partes.append("ℹ️ No hay datos verificados disponibles")

    fecha = datos.get("_meta", {}).get("extraido_en", "")
    header = f"📋 DATOS VERIFICADOS (extraído: {fecha})" if fecha else "📋 DATOS VERIFICADOS"
    return f"\n\n═══════════════════════════════\n{header}\n" + "\n".join(partes) + "\n═══════════════════════════════\n"


def _construir_contexto_sistema() -> str:
    """
    Captura el estado actual del sistema para inyectar al LLM.
    Tomy sabe que hay en el dashboard antes de responder.
    Rapido: solo lee SQLite y cuenta archivos, sin I/O pesada.
    """
    lineas = ["═══ ESTADO ACTUAL DEL SISTEMA ═══"]

    # 1. Tareas activas en el workflow
    try:
        db_path = os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db")
        from backend.task_db import TaskDB
        db = TaskDB(db_path)
        activas = db.listar_activos()
        if activas:
            lineas.append(f"\n🔄 PROCESANDO AHORA ({len(activas)} tarea(s)):")
            PASOS = {
                1: "Transcribiendo audio", 2: "Buscando datos del paciente",
                3: "Leyendo notas", 4: "Leyendo formatos subidos",
                5: "Sintetizando (IA razonadora)", 6: "Generando 7 formatos",
                7: "Verificando calidad", 8: "Convirtiendo a PDF", 9: "Notificando",
            }
            for t in activas[:3]:
                paso_label = PASOS.get(t.get("paso_actual", 0), t.get("estado", "?"))
                lineas.append(f"  • CC {t['paciente_cc']}: {paso_label} (paso {t.get('paso_actual','?')}/9)")
        else:
            lineas.append("\n⚡ Sin tareas activas — sistema libre")
    except Exception as e:
        lineas.append(f"\n[Tareas: no disponible — {e}]")

    # 2. Agenda del dia
    try:
        from backend.notificador import api_get_agenda
        agenda = api_get_agenda()
        if agenda and agenda.get("citas"):
            citas = agenda["citas"]
            lineas.append(f"\n📅 AGENDA HOY ({len(citas)} cita(s)):")
            for c in citas[:6]:
                nombre = c.get("paciente", "?")
                hora = c.get("hora", "?")
                cc_cita = c.get("cc", "")
                procesado = "✅" if c.get("procesado") else "⏳"
                lineas.append(f"  {procesado} {hora} — {nombre}" + (f" (CC {cc_cita})" if cc_cita else ""))
        else:
            lineas.append("\n📅 AGENDA: No hay agenda cargada para hoy")
    except Exception:
        lineas.append("\n📅 AGENDA: no disponible")

    # 3. Pacientes en el sistema
    try:
        import glob as _glob
        storage = Path(os.getenv("STORAGE_DIR", "./storage"))
        data_dir = storage / "data"
        jsons = _glob.glob(str(data_dir / "*-completo.json"))
        lineas.append(f"\n👥 PACIENTES EN SISTEMA: {len(jsons)}")
        if len(jsons) <= 5:
            for jpath in jsons:
                try:
                    import json as _json
                    with open(jpath, encoding="utf-8") as f:
                        d = _json.load(f)
                    nombre = d.get("paciente", {}).get("nombre", "?")
                    cc_p = d.get("paciente", {}).get("documento", "?")
                    lineas.append(f"  • {nombre} (CC {cc_p})")
                except Exception:
                    pass
    except Exception:
        pass

    # 4. Formatos generados hoy y recientes
    try:
        docs_dir = storage / "docs"
        from datetime import date
        hoy_str = date.today().strftime("%Y-%m-%d")
        docs_hoy = []
        docs_recientes = []
        for f in sorted(docs_dir.glob("*.docx"), key=lambda x: x.stat().st_mtime, reverse=True):
            mtime_str = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")
            if mtime_str == hoy_str:
                docs_hoy.append(f.name)
            docs_recientes.append(f"{f.name} ({mtime_str})")
            if len(docs_recientes) >= 5:
                break
        if docs_hoy:
            lineas.append(f"\n📄 FORMATOS GENERADOS HOY: {len(docs_hoy)}")
            for d in docs_hoy[:5]:
                lineas.append(f"  • {d}")
        if docs_recientes and not docs_hoy:
            lineas.append(f"\n📄 FORMATOS RECIENTES:")
            for d in docs_recientes[:3]:
                lineas.append(f"  • {d}")
    except Exception:
        pass

    # 5. Feature flags
    tomy_on = os.getenv("TOMY_COMPLETO_ENABLED", "false").lower() == "true"
    fase_a = os.getenv("FASE_A_ENABLED", "false").lower() == "true"
    lineas.append(f"\n⚙️ Pipeline: {'✅ activo' if tomy_on else '❌ inactivo (TOMY_COMPLETO_ENABLED=false)'}")
    if fase_a:
        lineas.append("⚙️ Extraccion portales: ✅ activa")

    return "\n".join(lineas)


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

    # 3. NUEVO: Cargar datos verificados si Fase A activa
    datos_verificados = None
    sugerir_extraccion = False
    if os.getenv("FASE_A_ENABLED", "false").lower() == "true" and cc:
        datos_verificados = _cargar_datos_verificados(cc)
        if datos_verificados:
            _log(f"VERIFIED: datos cargados para CC {cc}")
        else:
            sugerir_extraccion = True
            _log(f"VERIFIED: sin datos para CC {cc}")

    # 4. Buscar archivos — PRIMERO multi (todos los del paciente), luego individual
    archivos_paciente = _buscar_archivos_paciente(cc=cc, mensaje=mensaje)
    
    if archivos_paciente and len(archivos_paciente) >= 3:
        # MODO WORKERS (Fase A) o LOTES (legacy)
        if os.getenv("FASE_A_ENABLED", "false").lower() == "true":
            doc_content = _procesar_via_workers(archivos_paciente, cc)
            archivo_nombre = f"{len(archivos_paciente)} archivos (workers)"
        else:
            doc_content = _procesar_en_lotes(archivos_paciente, cc, mensaje)
            archivo_nombre = f"{len(archivos_paciente)} archivos (lotes-legacy)"
    elif archivos_paciente:
        # Pocos archivos: leer directo
        doc_content = _leer_multiples_docx(archivos_paciente, max_chars_total=8000)
        archivo_nombre = f"{len(archivos_paciente)} archivos"
    else:
        # MODO INDIVIDUAL: buscar un solo archivo
        archivo = _buscar_archivo(mensaje)
        doc_content = _leer_docx(archivo) if archivo else ""
        archivo_nombre = archivo.name if archivo else None

    # 4.5. NUEVO: detectar comando "organiza este formato"
    if any(kw in mensaje.lower() for kw in ["organiza este formato", "organízame este", "organizame el formato"]):
        archivo = _buscar_archivo(mensaje)
        if archivo and cc:
            try:
                from backend.organizador_formato import organizar_formato
                resultado_org = organizar_formato(str(archivo), cc)
                if resultado_org.get("ok"):
                    doc_content = (doc_content or "") + f"\n\n[FORMATO ORGANIZADO]:\n{json.dumps(resultado_org, ensure_ascii=False, indent=2)}"
            except Exception as e:
                _log(f"ORGANIZAR: error {e}")

    # 5. Inyectar datos verificados al contexto del LLM
    if datos_verificados:
        doc_content = (doc_content or "") + _formatear_datos_verificados(datos_verificados)

    # 6. Si no hay datos y hay CC, agregar sugerencia
    if sugerir_extraccion:
        mensaje_con_sugerencia = mensaje + (
            "\n\n💡 No tengo datos verificados de este paciente todavía. "
            "¿Quieres que verifique en Medifolios y Positiva ahora? (~2 min)."
        )
    else:
        mensaje_con_sugerencia = mensaje

    # 7. Llamar LLM con todo el contexto
    ctx_sistema = _construir_contexto_sistema()
    respuesta = _llamar_llm(mensaje_con_sugerencia, cc, doc_content, workspace_files,
                            historial=historial, ctx_sistema=ctx_sistema)
    
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
