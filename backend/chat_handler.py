"""
Chat inteligente de Tomy (Dashboard) — Especialista RILO SAS.
Prompt ligero + carga de documentos por demanda.
"""
import os, json, re, requests, time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError: pass

API_KEY = os.getenv("OPENCODE_GO_API_KEY", "")
BASE_URL = os.getenv("OPENCODE_GO_BASE_URL", "https://opencode.ai/zen/go/v1")
MODEL = os.getenv("LLM_MODEL", "deepseek-v4-pro")
WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", Path.home() / "rilo-workspace"))
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./storage"))

# ═══ PROMPT BASE (ligero, ~2.5K, se manda SIEMPRE) ═══

SYSTEM_PROMPT = """Eres Tomy, asistente de Sandra (RILO SAS, fisioterapeuta ARL Positiva Colombia).
Español colombiano, cálido, SIMPLE. CERO jerga técnica (no digas API, JSON, endpoint, servidor).

📋 MANEJAS 7 FORMATOS (VOI = Valoración de Desempeño Ocupacional):
1. Análisis Exigencias  2. Carta Medidas  3. Carta Recomendaciones  4. Cierre Caso
5. Citación Empresas  6. Prueba Trabajo  7. VOI

🔄 FLUJO: cita → audio → dashboard → completar formato → verificar portales → enviar

🔑 VERIFICACIÓN OBLIGATORIA CONTRA PORTALES (NUNCA des por bueno un dato sin verificar):
- MEDIFOLIOS: server0medifolios.net, user 55162801-2. Datos: nombre, CC, dirección, siniestro, historia clínica.
- POSITIVA: positivacuida.positiva.gov.co, user 1075209386MR, pass Rilo2026*. Datos: siniestro OFICIAL, diagnóstico CIE-10, %PCL, estado rehab.
- CRUCE SINIESTRO: debe coincidir en AMBOS. Prevalece Positiva (fuente oficial ARL).
- Marcas: ✅ verificado ⚠️ pendiente ❌ discrepancia 👤 dato del paciente

🎯 CÓMO TRABAJAR:
- Si mencionan un archivo → búscalo y analízalo. NO lo leas de vuelta, COMPLETA lo que falta.
- Completa secciones objetivas (datos, fechas, siniestros) con marcas de verificación.
- Lo que requiera criterio clínico → pregúntale a Sandra.
- Si no tienes un dato → pídeselo específicamente. NUNCA inventes.
- Sé CONCISO. Ve directo al grano.

📁 Carpeta: C:\\Users\\Sandra\\Desktop\\SANDRA\\ACTIVIDADES OCUPACIONALES
🖥️ Dashboard: Home, Pacientes, Formatos, Chat, Archivos, Subir Audio

⚠️ ERES EL MÁXIMO EXPERTO EN RILO SAS. Sandra confía en ti. Sé breve y efectivo."""

# ═══ FIN PROMPT ═══

# Caché del workspace (el rglob sobre /mnt/c/ es lentísimo)
_cache_archivos = {"archivos": [], "timestamp": 0, "ws_list": ""}
_CACHE_TTL = 300  # 5 minutos

def _cache_workspace():
    """Actualiza caché de archivos del workspace si expiró."""
    global _cache_archivos
    ahora = time.time()
    if ahora - _cache_archivos["timestamp"] < _CACHE_TTL:
        return
    try:
        todos = []
        dirs_info = {}
        for item in WORKSPACE_DIR.iterdir():
            if item.name.startswith('.'): continue
            if item.is_dir():
                docs_nombres = []
                for sub in item.iterdir():
                    if sub.is_file() and sub.suffix.lower() in ['.docx', '.txt']:
                        todos.append(sub)  # Path completo
                        docs_nombres.append(sub.name)
                    elif sub.is_dir() and not sub.name.startswith('.'):
                        for sub2 in sub.iterdir():
                            if sub2.is_file() and sub2.suffix.lower() in ['.docx', '.txt']:
                                todos.append(sub2)  # Path completo, sin reconstruir
                                docs_nombres.append(sub2.name)
                if docs_nombres:
                    dirs_info[item.name] = docs_nombres
            elif item.is_file() and item.suffix.lower() in ['.docx', '.txt']:
                todos.append(item)
        
        ws_list = "\n".join(
            f"📁 {d}/: {', '.join(files[:4])}" for d, files in sorted(dirs_info.items())
        )[:800]
        
        _cache_archivos = {"archivos": todos, "timestamp": ahora, "ws_list": ws_list}
    except Exception:
        pass


def _buscar_archivo(mensaje: str) -> Optional[Path]:
    """Busca archivo mencionado en el mensaje. 3 estrategias. Usa caché."""
    if not WORKSPACE_DIR.exists(): return None
    triggers = ["formato","documento","archivo","arregla","completa","termina","revisa",
                "analisis","análisis","carta","cierre","citacion","prueba","valoracion",
                "desempeño","exigencias","recomendaciones","medidas","trabajo","voi"]
    if not any(t in mensaje.lower() for t in triggers): return None
    
    _cache_workspace()
    todos = _cache_archivos["archivos"]
    if not todos: return None
    
    ml = mensaje.lower()
    # Estrategia 1: nombre exacto
    for a in todos:
        if a.stem.lower() in ml: return a
    # Estrategia 2: partes del nombre
    for a in todos:
        partes = a.stem.lower().replace('_',' ').replace('-',' ').split()
        if sum(1 for p in partes if len(p)>3 and p in ml) >= 2: return a
    # Estrategia 3: tipo de formato PERO filtrando por nombre de paciente si se menciona
    tipos = {"analisis":"analisis","análisis":"analisis","voi":"voi",
             "medidas":"medidas","recomendaciones":"recomendaciones",
             "cierre":"cierre","citacion":"citacion","empresas":"citacion",
             "prueba":"prueba","valoracion":"valoracion","desempeño":"valoracion"}
    # Extraer posible nombre de paciente del mensaje
    nombres_paciente = []
    for patron in [r'(?:de|del|para)\s+([A-ZÁÉÍÓÚÑ]{2,}[A-ZÁÉÍÓÚÑ\s]{5,})',
                   r'([A-ZÁÉÍÓÚÑ]{2,}\s+[A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,})?)']:
        m = re.search(patron, mensaje)
        if m:
            partes = m.group(1).lower().split()
            nombres_paciente.extend([p for p in partes if len(p) > 3])
    
    for kw, tipo in tipos.items():
        if kw in ml:
            cand = [a for a in todos if tipo in a.stem.lower()]
            if cand:
                # Si hay nombre de paciente, priorizar archivos que lo contengan
                if nombres_paciente:
                    cand_con_nombre = [a for a in cand if any(n in a.stem.lower() for n in nombres_paciente)]
                    if cand_con_nombre:
                        return max(cand_con_nombre, key=lambda p: p.stat().st_mtime)
                # Si no, el más reciente
                return max(cand, key=lambda p: p.stat().st_mtime)
    return None


def _leer_docx(ruta: Path) -> str:
    """Lee .docx y retorna resumen para el LLM (máx 2500 chars)."""
    if ruta.suffix.lower() == '.txt':
        try: return f"📄 {ruta.name}:\n{ruta.read_text(encoding='utf-8',errors='ignore')[:2000]}"
        except: return ""
    if ruta.suffix.lower() != '.docx': return ""
    try:
        from docx import Document
        doc = Document(str(ruta))
        lines = [f"📄 {ruta.name} | {len(doc.paragraphs)} párrafos, {len(doc.tables)} tablas\n"]
        for p in doc.paragraphs[:30]:
            t = p.text.strip()
            if not t: continue
            if re.match(r'^\d+[\.\)]\s', t): lines.append(f"\n🔹 {t}")
            elif t.isupper() and len(t)<80: lines.append(f"\n📌 {t}")
            else: lines.append(f"  {t[:200]}")
        for ti, tb in enumerate(doc.tables[:3]):
            lines.append(f"\n📋 Tabla {ti+1}: {len(tb.rows)}×{len(tb.columns)}")
            for ri, row in enumerate(tb.rows[:5]):
                cells = [c.text.strip()[:60] for c in row.cells]
                lines.append(f"  {' | '.join(cells)}")
        return "\n".join(lines)[:2500]
    except Exception as e:
        return f"⚠️ Error leyendo {ruta.name}: {e}"


def _workspace_list() -> str:
    """Lista rápida del workspace (desde caché)."""
    _cache_workspace()
    return _cache_archivos.get("ws_list", "")


def _llamar_llm(mensaje: str, cc: str = "", archivo_doc: str = "", historial: list = None) -> str:
    """Llama al LLM con prompt ligero + contexto bajo demanda."""
    if not API_KEY:
        return "⚠️ Falta configurar OPENCODE_GO_API_KEY en .env. Dile a Manu."
    
    # Construir mensajes
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if historial:
        for msg in historial[-6:]:  # Solo últimos 6 para no saturar
            role = "assistant" if msg.get("rol") == "asistente" else "user"
            content = msg.get("contenido", "")
            if content and len(content) < 500:
                messages.append({"role": role, "content": content})
    
    # Contexto bajo demanda
    ctx = mensaje
    if archivo_doc:
        ctx = f"{mensaje}\n\n[Documento encontrado]:\n{archivo_doc}\n\n⚠️ NO describas el documento. COMPLETA lo que falta. Ve al grano."
    
    ws = _workspace_list()
    if ws:
        ctx += f"\n\n[Carpeta: {ws}]"
    if cc:
        ctx += f"\n\n[CC: {cc}]"
    
    messages.append({"role": "user", "content": ctx})
    
    try:
        resp = requests.post(f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": messages, "temperature": 0.7, "max_tokens": 1200},
            timeout=60)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        return f"🤔 Error momentáneo ({resp.status_code}). Intenta de nuevo."
    except requests.exceptions.Timeout:
        return "⏰ Tardé mucho. ¿Puedes ser más breve?"
    except Exception:
        return "❌ Fallo de conexión. Intenta otra vez."


def procesar_mensaje(mensaje: str, paciente_cc: str = "", historial: list = None) -> dict:
    """Procesa mensaje: busca archivos, carga datos, llama LLM."""
    if not mensaje.strip():
        return {"contenido": "¿En qué te ayudo, Sandra? 😊", "accion": None}
    
    msg_lower = mensaje.lower()
    
    # Detectar CC
    cc = paciente_cc
    if not cc:
        m = re.search(r'\b(\d{6,12})\b', mensaje.replace("'","").replace(".","").replace(",",""))
        if m: cc = m.group(1)
    
    # Buscar archivo mencionado
    archivo = _buscar_archivo(mensaje)
    doc_content = _leer_docx(archivo) if archivo else ""
    
    # Buscar datos verificados si pide verificación
    datos_ok = None
    if any(p in msg_lower for p in ["verifica","revisa","comprueba","confirma"]) and cc:
        try:
            from backend.puente_docker import obtener_datos_verificados
            r = obtener_datos_verificados(cc)
            if r.get("estado") != "pendiente_extraccion":
                datos_ok = r
        except ImportError: pass
    
    # Enriquecer mensaje si hay datos
    msg_final = mensaje
    if datos_ok:
        extra = "\n📊 DATOS VERIFICADOS DE PORTALES:\n"
        for c, i in datos_ok.get("campos_verificados", {}).items():
            if i.get("valor"): extra += f"{i.get('estado','?')} {c}: {i['valor']}\n"
        msg_final = mensaje + extra + "\nUsa estos datos verificados."
    
    respuesta = _llamar_llm(msg_final, cc, doc_content, historial)
    
    accion = "documento" if any(p in msg_lower for p in ["completa","termina","documento","formato"]) else \
             "verificar" if any(p in msg_lower for p in ["verifica","revisa","confirma"]) else None
    
    return {"contenido": respuesta, "accion": accion, "cc_detectada": cc}
