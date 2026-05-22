"""
Servidor FastAPI — API backend para el dashboard RILO SAS.

Endpoints expuestos (todos en /api/...):
  POST /api/chat                              — Chat con Hermes (Tomy)
  POST /api/upload-audio                      — Subir audio, transcribir con Deepgram
  GET  /api/pacientes                         — Listar pacientes
  GET  /api/pacientes/{cc}                    — Obtener paciente por cédula
  GET  /api/pacientes/{cc}/formatos           — Listar formatos del paciente
  POST /api/pacientes/{cc}/generar            — Generar formatos
  POST /api/pacientes/{cc}/formatos/{fmt}/corregir — Corregir un formato

Ejecutar:
  cd /root/fisioterapia
  python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import json
import glob
import asyncio
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

# Cargar variables de entorno desde .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv no instalado. Las variables de .env no se cargarán.")
    print("   pip install python-dotenv")

import shutil
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="RILO SAS API", version="1.0.0")

_cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_raw.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STORAGE = Path(__file__).parent.parent / "storage"
DOCS_DIR = STORAGE / "docs"
PDFS_DIR = STORAGE / "pdfs"
DATA_DIR = STORAGE / "data"
AUDIO_DIR = STORAGE / "audio"

for d in [DOCS_DIR, PDFS_DIR, DATA_DIR, AUDIO_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Almacén de tareas asíncronas de extracción
_extraccion_tasks: Dict[str, dict] = {}


async def _ejecutar_extraccion_background(cc: str, task_id: str):
    """Ejecuta extracción en background y actualiza _extraccion_tasks."""
    from backend.playwright_real.orquestador import extraer_paciente_completo
    _extraccion_tasks[task_id] = {"estado": "extrayendo"}
    try:
        resultado = await extraer_paciente_completo(cc, guardar=True)
        _extraccion_tasks[task_id] = {
            "estado": "completo" if not resultado["_meta"].get("parcial") else "parcial",
            "datos": resultado,
            "discrepancias": resultado["_meta"].get("discrepancias", []),
        }
    except Exception as e:
        _extraccion_tasks[task_id] = {"estado": "error", "error": str(e)}


# ── Modelos ────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    mensaje: str
    paciente_cc: Optional[str] = None
    historial: Optional[List[dict]] = None  # Conversación previa


class GenerarRequest(BaseModel):
    estado_caso: Optional[str] = None


class LoginRequest(BaseModel):
    pin: str

class OrganizarFormatoRequest(BaseModel):
    paciente_cc: str

class CorregirRequest(BaseModel):
    mensaje: str


# ── Helpers ────────────────────────────────────────────────────────────────

def _cargar_datos_paciente(cc: str) -> dict:
    # Match both "CC-completo.json" and "YYYYMMDD-CC-completo.json"
    patterns = [
        str(DATA_DIR / f"{cc}-completo.json"),
        str(DATA_DIR / f"*{cc}-completo.json"),
        str(DATA_DIR / f"{cc}.json"),
    ]
    matches = []
    for pat in patterns:
        matches.extend(glob.glob(pat))
    # Remove duplicates and sort by modification time (newest first)
    matches = sorted(set(matches), key=os.path.getmtime, reverse=True)
    if not matches:
        raise HTTPException(status_code=404, detail=f"Paciente {cc} no encontrado")
    with open(matches[0], encoding="utf-8") as f:
        return json.load(f)


def _datos_a_paciente_info(datos: dict) -> dict:
    pac = datos.get("paciente", {})
    sin = datos.get("siniestro", {})
    return {
        "documento": pac.get("documento", ""),
        "nombre": pac.get("nombre", ""),
        "fecha_nacimiento": pac.get("fecha_nacimiento", ""),
        "edad": pac.get("edad", ""),
        "telefono": pac.get("telefono", ""),
        "direccion": pac.get("direccion", ""),
        "email": pac.get("email", ""),
        "eps_ips": pac.get("eps_ips", ""),
        "afp": pac.get("afp", ""),
        "empresa": datos.get("empresa", {}).get("nombre", ""),
        "siniestro": sin.get("id_siniestro", sin.get("numero_siniestro", "")),
        "estado_caso": datos.get("estado_caso", sin.get("estado_caso", "")),
        "ultima_actualizacion": datos.get("ultima_actualizacion", ""),
    }


def _listar_formatos_cc(cc: str) -> list:
    archivos = [f for f in glob.glob(str(DOCS_DIR / f"*{cc}*.docx"))
                if Path(f).is_file()]
    NOMBRES = {
        "analisis": ("1", "Análisis de Exigencias"),
        "medidas": ("2", "Carta de Medidas Preventivas"),
        "recomendaciones": ("3", "Carta de Recomendaciones"),
        "cierre": ("4", "Cierre de Caso"),
        "citacion": ("5", "Citación de Empresas"),
        "prueba": ("6", "Prueba de Trabajo"),
        "valoracion": ("7", "Valoración del Desempeño Ocupacional"),
    }
    # Keep only the newest DOCX per format key
    mejor: dict[str, tuple[str, float]] = {}
    for archivo in archivos:
        stem = Path(archivo).stem
        mtime = Path(archivo).stat().st_mtime
        for key in NOMBRES:
            if stem.startswith(key):
                if key not in mejor or mtime > mejor[key][1]:
                    mejor[key] = (archivo, mtime)
                break
    formatos = []
    for key, (archivo, mtime) in sorted(mejor.items(), key=lambda x: x[1][0]):
        fid, nombre = NOMBRES[key]
        fecha = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
        formatos.append({
            "id": fid,
            "nombre": nombre,
            "estado": "generado",
            "fecha_generacion": fecha,
            "archivo_docx": archivo,
        })
    return formatos


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"ok": True, "version": "1.0.0"}


@app.get("/api/stats")
def stats():
    archivos_json = glob.glob(str(DATA_DIR / "*-completo.json"))
    archivos_docx = [f for f in glob.glob(str(DOCS_DIR / "*.docx")) if Path(f).is_file()]

    total_pacientes = 0
    for archivo in archivos_json:
        try:
            with open(archivo, encoding="utf-8"):
                pass
            total_pacientes += 1
        except Exception:
            pass

    backup_fecha = "—"
    if archivos_docx:
        newest = max(archivos_docx, key=os.path.getmtime)
        backup_fecha = datetime.fromtimestamp(os.path.getmtime(newest)).strftime("%d/%m/%Y")

    return {
        "total_pacientes": total_pacientes,
        "total_formatos": len(archivos_docx),
        "backup_fecha": backup_fecha,
    }


@app.get("/api/download/{filename}")
def descargar_archivo(filename: str):
    safe_name = Path(filename).name  # strip any path traversal
    path = DOCS_DIR / safe_name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(
        str(path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=safe_name,
    )


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    Chat con Tomy — Motor IA REAL (DeepSeek v4).
    Misma conciencia que Telegram y CLI. Especialista absoluto en RILO SAS.
    Ahora siempre conoce los archivos del workspace.
    """
    try:
        from backend.chat_handler import procesar_mensaje
        resultado = procesar_mensaje(req.mensaje, req.paciente_cc, req.historial)
        return {
            "ok": True,
            "contenido": resultado["contenido"],
            "accion": resultado.get("accion"),
            "datos": resultado.get("datos"),
            "archivo": resultado.get("archivo"),
        }
    except Exception as e:
        return {
            "ok": False,
            "contenido": f"❌ Error: {str(e)}",
            "accion": None,
        }


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Streaming SSE del chat. El frontend lee los chunks con ReadableStream.
    """
    import json as _json
    import re as _re
    import requests as _req

    def _stream():
        from backend.chat_handler import (
            _listar_workspace, _buscar_archivos_paciente, _buscar_archivo,
            _leer_multiples_docx, _leer_docx, SYSTEM_PROMPT, API_KEY, BASE_URL, MODEL,
            _construir_contexto_sistema, _log,
        )

        mensaje = req.mensaje
        cc = req.paciente_cc or ""
        historial = req.historial or []

        workspace_files = _listar_workspace()
        if not cc:
            m = _re.search(r'\b(\d{6,12})\b', mensaje.replace("'","").replace(".",""))
            if m: cc = m.group(1)

        archivos_pac = _buscar_archivos_paciente(cc=cc, mensaje=mensaje)
        if archivos_pac:
            doc_content = _leer_multiples_docx(archivos_pac, max_chars_total=8000)
            archivo_nombre = f"{len(archivos_pac)} archivos"
        else:
            archivo = _buscar_archivo(mensaje)
            doc_content = _leer_docx(archivo) if archivo else ""
            archivo_nombre = archivo.name if archivo else None

        ctx_sistema = _construir_contexto_sistema()

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in historial[-6:]:
            rol = h.get("rol","")
            c = (h.get("contenido","") or "")[:2000]
            if rol == "usuario": messages.append({"role":"user","content":c})
            elif rol == "asistente": messages.append({"role":"assistant","content":c})

        partes = []
        if ctx_sistema: partes.append(ctx_sistema)
        partes.append(f"\n═══ MENSAJE ═══\n{mensaje}")
        if doc_content: partes.append(f"\n\n📄 DOCUMENTOS:\n{doc_content}")
        if cc: partes.append(f"\n[CC: {cc}]")
        if workspace_files: partes.append(f"\n\n📁 CARPETA:\n{workspace_files}")
        messages.append({"role":"user","content":"\n".join(partes)})

        if not API_KEY:
            yield 'data: {"tipo":"error","contenido":"Sin API key"}\n\n'
            return

        try:
            resp = _req.post(
                f"{BASE_URL}/chat/completions",
                headers={"Authorization":f"Bearer {API_KEY}","Content-Type":"application/json"},
                json={"model":MODEL,"messages":messages,"max_tokens":16000,
                      "temperature":0.7,"stream":True},
                stream=True, timeout=300,
            )
            for line in resp.iter_lines():
                if not line: continue
                s = line.decode("utf-8") if isinstance(line, bytes) else line
                if not s.startswith("data: "): continue
                raw = s[6:]
                if raw == "[DONE]": break
                try:
                    chunk = _json.loads(raw)
                    piece = chunk.get("choices",[{}])[0].get("delta",{}).get("content","") or ""
                    if piece:
                        yield f'data: {_json.dumps({"tipo":"delta","contenido":piece})}\n\n'
                except Exception:
                    pass
            yield f'data: {_json.dumps({"tipo":"fin","archivo":archivo_nombre,"accion":"documento" if doc_content else None})}\n\n'
        except Exception as e:
            yield f'data: {_json.dumps({"tipo":"error","contenido":str(e)[:100]})}\n\n'

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"},
    )


@app.post("/api/chat/audio")
async def chat_audio(
    audio: UploadFile = File(...),
    paciente_cc: str = Form(...),
):
    """
    Recibe audio desde el chat, inicia el workflow completo,
    retorna task_id para que el chat haga polling del progreso.
    """
    if os.getenv("TOMY_COMPLETO_ENABLED", "false").lower() != "true":
        raise HTTPException(503, "Tomy Completo no habilitado. Activar TOMY_COMPLETO_ENABLED=true en .env")

    ext = Path(audio.filename or "audio.m4a").suffix or ".m4a"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audio_path = WORKFLOW_AUDIOS_DIR / f"{paciente_cc}_{timestamp}{ext}"
    audio_path.write_bytes(await audio.read())

    from backend.task_db import TaskDB
    from backend.workflow_runner import ejecutar_workflow
    db = TaskDB(os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db"))
    task_id = db.crear_task(paciente_cc=paciente_cc, audio_path=str(audio_path))

    import threading
    threading.Thread(
        target=ejecutar_workflow,
        kwargs={"audio_path": str(audio_path), "paciente_cc": paciente_cc, "task_id_existente": task_id},
        daemon=True,
    ).start()

    duracion_min_est = round(audio_path.stat().st_size / (1024 * 1024 * 0.5))

    return {
        "ok": True,
        "task_id": task_id,
        "mensaje_tomy": (
            f"✅ Recibí el audio de CC {paciente_cc}. "
            f"Empiezo a procesarlo ahora — tarda entre 15-25 minutos. "
            f"Te aviso aquí y por Telegram cuando tenga los 7 formatos listos.\n\n"
            f"*ID de tarea:* `{task_id}` — podés consultar el progreso en Mi Día."
        ),
        "paciente_cc": paciente_cc,
    }


# ─── Archivos paciente para FilePicker ───────────────────────

@app.get("/api/archivos/paciente/{cc}")
def archivos_paciente(cc: str):
    result = []
    for f in sorted(DOCS_DIR.glob(f"*{cc}*.docx"), key=lambda x: x.stat().st_mtime, reverse=True):
        result.append({
            "nombre": f.name,
            "tamano_kb": f.stat().st_size // 1024,
            "modificado": datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m/%Y %H:%M"),
            "url_descarga": f"/api/download/{f.name}",
        })
    return {"ok": True, "archivos": result}


@app.post("/api/upload-audio")
async def upload_audio(
    audio: UploadFile = File(...),
    paciente_cc: str = Form(...),
):
    """Transcribe un audio con Deepgram y extrae datos cualitativos."""
    from backend.flujo_audio import transcribir_audio, extraer_datos_cualitativos

    ext = Path(audio.filename or "audio.m4a").suffix
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(await audio.read())
        audio_path = tmp.name

    try:
        try:
            transcripcion = transcribir_audio(audio_path)
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        datos = extraer_datos_cualitativos(transcripcion["texto"])

        destino = AUDIO_DIR / paciente_cc
        destino.mkdir(parents=True, exist_ok=True)
        with open(destino / "transcripcion.json", "w", encoding="utf-8") as f:
            json.dump({"transcripcion": transcripcion, "datos": datos}, f, indent=2, ensure_ascii=False)

        return {
            "ok": True,
            "transcripcion": transcripcion["texto"],
            "datos_extraidos": datos,
            "duracion": transcripcion["duracion"],
            "confianza": transcripcion["confianza"],
            "segmentos": transcripcion["segmentos"],
        }
    finally:
        os.unlink(audio_path)


@app.get("/api/pacientes")
def listar_pacientes():
    archivos = glob.glob(str(DATA_DIR / "*-completo.json"))
    pacientes = []
    for archivo in archivos:
        try:
            with open(archivo, encoding="utf-8") as f:
                datos = json.load(f)
            pacientes.append(_datos_a_paciente_info(datos))
        except Exception:
            pass
    return pacientes


@app.get("/api/pacientes/{cc}")
def obtener_paciente(cc: str):
    datos = _cargar_datos_paciente(cc)
    return _datos_a_paciente_info(datos)


@app.get("/api/pacientes/{cc}/formatos")
def listar_formatos(cc: str):
    return _listar_formatos_cc(cc)


@app.post("/api/pacientes/{cc}/generar")
def generar_formatos(cc: str, req: GenerarRequest):
    try:
        datos = _cargar_datos_paciente(cc)
    except HTTPException:
        raise

    try:
        from backend.format_selector import seleccionar_con_contexto
        from backend.json_validator import validar_para_formatos
        from backend.doc_generator import generar_documento

        # Map long format names to doc_generator short names
        NOMBRE_CORTO = {
            "analisis_exigencias": "analisis",
            "carta_medidas": "medidas",
            "carta_recomendaciones": "recomendaciones",
            "cierre_caso": "cierre",
            "citacion_empresas": "citacion",
            "prueba_trabajo": "prueba",
            "valoracion_desempeno": "valoracion",
        }

        ctx = seleccionar_con_contexto(datos, estado=req.estado_caso)
        resultados = validar_para_formatos(datos, ctx["formatos"])

        generados = []
        errores = []
        for fmt, res in resultados.items():
            fmt_corto = NOMBRE_CORTO.get(fmt, fmt)
            if res["ok"]:
                try:
                    path = generar_documento(fmt_corto, res["json_corregido"])
                    generados.append({"formato": fmt, "archivo": path})
                except Exception as e:
                    errores.append({"formato": fmt, "error": str(e)})
            else:
                errores.append({"formato": fmt, "error": "; ".join(res["errores"])})

        return {
            "ok": True,
            "generados": generados,
            "errores": errores,
            "mensaje": f"{len(generados)} formato(s) generado(s), {len(errores)} error(es)",
        }
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Error de importación: {e}")


@app.post("/api/pacientes/{cc}/formatos/{fmt}/corregir")
def corregir_formato(cc: str, fmt: str, req: CorregirRequest):
    try:
        from backend.correction_loop import analizar_mensaje_rechazo, ejecutar_correccion

        datos = _cargar_datos_paciente(cc)
        instruccion = analizar_mensaje_rechazo(req.mensaje)
        accion = ejecutar_correccion(instruccion, datos, fmt)

        return {
            "ok": True,
            "tipo": instruccion.tipo.value,
            "campo": instruccion.campo,
            "accion": accion,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.server:app", host="0.0.0.0", port=8000, reload=True)


# ── Nuevos endpoints: Agenda, Archivos, Notificaciones ──────────────────

WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", Path.home() / "rilo-workspace"))


@app.get("/api/agenda")
def get_agenda():
    """Obtener la agenda actual guardada (para el dashboard)."""
    try:
        from backend.notificador import api_get_agenda
        agenda = api_get_agenda()
        if agenda:
            return {"ok": True, **agenda}
        return {"ok": True, "citas": [], "mensaje": "No hay agenda guardada aún"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agenda/check")
def check_agenda_ahora():
    """Forzar revisión de agenda YA (8:30 PM automático, esto es manual)."""
    try:
        from backend.notificador import api_check_ahora
        resultado = api_check_ahora()
        return {"ok": True, **resultado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/archivos")
def listar_archivos(path: Optional[str] = None):
    """
    Listar archivos de la carpeta de trabajo de Sandra.
    Si path es None, lista la raíz del workspace.
    """
    try:
        base = WORKSPACE_DIR if path is None else WORKSPACE_DIR / path
        
        # Seguridad: evitar salir del workspace
        base = base.resolve()
        if not str(base).startswith(str(WORKSPACE_DIR.resolve())):
            raise HTTPException(status_code=403, detail="Acceso denegado")
        
        if not base.exists():
            return {"ok": True, "archivos": [], "path": str(path or "")}
        
        archivos = []
        for item in sorted(base.iterdir()):
            if item.name.startswith(".") or item.name.startswith("__"):
                continue
            
            info = {
                "nombre": item.name,
                "tipo": "carpeta" if item.is_dir() else "archivo",
                "tamano": item.stat().st_size if item.is_file() else 0,
                "modificado": datetime.fromtimestamp(item.stat().st_mtime).isoformat(),
            }
            
            # Detectar tipo de archivo
            if item.is_file():
                ext = item.suffix.lower()
                if ext == ".docx":
                    info["icono"] = "📄"
                elif ext == ".txt":
                    info["icono"] = "📝"
                elif ext == ".json":
                    info["icono"] = "📊"
                elif ext in [".mp3", ".wav", ".m4a"]:
                    info["icono"] = "🎙️"
                else:
                    info["icono"] = "📎"
            else:
                # Detectar si es carpeta de paciente (tiene archivos dentro)
                info["icono"] = "📁"
                info["contenido"] = sum(1 for _ in item.rglob("*") if _.is_file())
            
            archivos.append(info)
        
        return {"ok": True, "path": str(path or ""), "archivos": archivos}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/archivos/sync")
def sync_workspace():
    """Sincronizar carpeta de trabajo con git (pull + push)."""
    import subprocess
    try:
        # git pull
        pull = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=str(WORKSPACE_DIR),
            capture_output=True, text=True, timeout=30
        )
        # git add -A && git commit && git push
        add = subprocess.run(
            ["git", "add", "-A"],
            cwd=str(WORKSPACE_DIR),
            capture_output=True, text=True, timeout=10
        )
        commit = subprocess.run(
            ["git", "commit", "-m", f"💾 Auto-sync {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
            cwd=str(WORKSPACE_DIR),
            capture_output=True, text=True, timeout=10
        )
        push = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=str(WORKSPACE_DIR),
            capture_output=True, text=True, timeout=30
        )
        
        return {
            "ok": True,
            "pull": pull.stdout.strip(),
            "push": push.stdout.strip(),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/pacientes/buscar")
def buscar_paciente_agenda(q: Optional[str] = None):
    """
    Buscar paciente en la agenda actual.
    Útil para cuando Sandra atiende a alguien y quiere ver sus datos rápido.
    """
    try:
        from backend.notificador import api_get_agenda
        agenda = api_get_agenda()
        if not agenda or not agenda.get("citas"):
            return {"ok": True, "pacientes": []}
        
        citas = agenda["citas"]
        if q:
            q_lower = q.lower()
            citas = [c for c in citas if q_lower in c["paciente"].lower()]
        
        return {"ok": True, "pacientes": citas[:20]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Diagnóstico del workspace ──────────────────────────────────────

@app.get("/api/workspace")
def diagnosticar_workspace():
    """
    Diagnóstico del workspace: qué archivos ve Tomy, si la carpeta existe, etc.
    Útil para debuguear cuando el chat "no responde".
    """
    try:
        from backend.chat_handler import diagnosticar_workspace
        info = diagnosticar_workspace()
        return {"ok": True, **info}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Verificación de portales (Fase A) ──────────────────────────────────────

@app.on_event("startup")
async def iniciar_cron():
    """Inicia el scheduler de pre-extracción si está habilitado."""
    from backend.cron_pre_extraccion import iniciar_scheduler
    iniciar_scheduler()


@app.get("/api/verificar/{cc}")
def verificar_paciente(cc: str):
    """
    Verifica los datos de un paciente contra los portales.
    Si ya hay datos extraídos en storage/data/{cc}-completo.json los retorna.
    Si no, informa que se necesita extraer.
    """
    try:
        from backend.playwright_real.orquestador import _cargar_json
        datos = _cargar_json(cc)
        if datos:
            return {"ok": True, "estado": "completo", "datos": datos}
        return {
            "ok": True,
            "estado": "pendiente",
            "mensaje": f"CC {cc} — No hay datos extraídos aún.",
            "sugerencia": "Usa POST /api/verificar/{cc}/extraer-ahora para extraer ahora.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/verificar/{cc}/extraer-ahora")
async def extraer_paciente_ahora(cc: str):
    """
    DISPARA la extracción de portales AHORA (síncrono).
    Navega Medifolios + Positiva. Tarda 2-5 minutos.
    """
    try:
        from backend.playwright_real.orquestador import extraer_paciente_completo
        resultado = await extraer_paciente_completo(cc, guardar=True)
        return {
            "ok": True,
            "estado": "completo" if not resultado["_meta"].get("parcial") else "parcial",
            "datos": resultado,
            "discrepancias": resultado["_meta"].get("discrepancias", []),
            "mensaje": f"✅ CC {cc} extraído. "
                       f"{'Parcial — revisar log.' if resultado['_meta'].get('parcial') else 'Completo.'}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/verificar/{cc}/extraer-async")
async def extraer_paciente_async(cc: str):
    """
    Dispara extracción asíncrona en background.
    Devuelve task_id para consultar estado después.
    """
    task_id = f"{cc}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    _extraccion_tasks[task_id] = {"estado": "iniciando"}
    asyncio.create_task(_ejecutar_extraccion_background(cc, task_id))
    return {
        "ok": True,
        "task_id": task_id,
        "mensaje": f"Extracción de CC {cc} iniciada en background. Task ID: {task_id}",
    }


@app.get("/api/verificar/task/{task_id}")
def estado_extraccion_async(task_id: str):
    """Consulta estado de una extracción asíncrona."""
    estado = _extraccion_tasks.get(task_id, {"estado": "no_encontrado"})
    return {"ok": True, "task_id": task_id, **estado}


# ─── Portal Verificador ──────────────────────────────────────

class PortalVerifRequest(BaseModel):
    cc: str
    forzar: bool = False


class PortalAprenderRequest(BaseModel):
    cc: str
    campo: str
    valor_correcto: str
    fuente: str = "sandra"


@app.post("/api/portal/verificar")
async def portal_verificar(req: PortalVerifRequest):
    """Verificacion cruzada Medifolios vs Positiva vs JSON local."""
    from backend.portal_verificador import PortalVerificador
    v = PortalVerificador()
    resultado = await asyncio.get_event_loop().run_in_executor(
        None, lambda: v.verificar(req.cc, req.forzar)
    )
    return {"ok": True, "verificacion": resultado}


@app.post("/api/portal/aprender")
def portal_aprender(req: PortalAprenderRequest):
    """Sandra confirma que valor es correcto."""
    from backend.portal_verificador import PortalVerificador
    v = PortalVerificador()
    v.aprender_correccion(req.cc, req.campo, req.valor_correcto, req.fuente)
    return {"ok": True, "guardado": f"{req.campo} = {req.valor_correcto}"}


@app.get("/api/portal/estado")
async def portal_estado():
    """Verifica si los portales son accesibles."""
    import httpx
    resultados = {}
    urls = {
        "medifolios": "https://www.server0medifolios.net/",
        "positiva": "https://positivacuida.positiva.gov.co/cas/login",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        for portal, url in urls.items():
            try:
                r = await client.get(url)
                resultados[portal] = {"accesible": r.status_code < 500, "status": r.status_code}
            except Exception as e:
                resultados[portal] = {"accesible": False, "error": str(e)[:60]}
    return {"ok": True, "portales": resultados}


# ── Endpoints de Cron ──────────────────────────────────────────────

@app.get("/api/cron/estado")
def cron_estado():
    """Estado del scheduler nocturno."""
    try:
        from backend.cron_pre_extraccion import obtener_estado
        return {"ok": True, **obtener_estado()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/cron/disparar-ahora")
async def cron_disparar_ahora():
    """Disparar el cron nocturno manualmente (testing)."""
    try:
        from backend.cron_pre_extraccion import revisar_email_y_extraer
        await revisar_email_y_extraer()
        return {"ok": True, "mensaje": "Cron nocturno ejecutado manualmente."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/portales/health")
def portales_health():
    """
    Health check de portales.
    Verifica si hay storage_state y última extracción.
    """
    sessions_dir = Path(os.getenv("PLAYWRIGHT_SESSIONS_DIR", "./storage/playwright_sessions"))
    medi_state = sessions_dir / "medifolios.json"
    pos_state = sessions_dir / "positiva.json"
    return {
        "medifolios": {
            "configurado": bool(os.getenv("MEDIFOLIOS_USER")),
            "sesion_guardada": medi_state.exists(),
        },
        "positiva": {
            "configurado": bool(os.getenv("POSITIVA_USER")),
            "sesion_guardada": pos_state.exists(),
        },
        "fase_a_habilitada": os.getenv("FASE_A_ENABLED", "false").lower() == "true",
    }


# ─── Tomy Completo: workflow endpoints ─────────────────────────

WORKFLOW_AUDIOS_DIR = STORAGE / "workflow_audios"
WORKFLOW_AUDIOS_DIR.mkdir(parents=True, exist_ok=True)


@app.post("/api/procesar-paciente")
async def procesar_paciente(
    audio: UploadFile = File(...),
    paciente_cc: str = Form(...),
):
    """
    Endpoint principal: Sandra sube audio + CC.
    Se crea task, se guarda audio, se dispara workflow en background.
    Devuelve task_id para que el dashboard haga polling.
    """
    if os.getenv("TOMY_COMPLETO_ENABLED", "false").lower() != "true":
        raise HTTPException(503, "Tomy Completo no habilitado (TOMY_COMPLETO_ENABLED=false)")

    ext = Path(audio.filename or "audio.m4a").suffix or ".m4a"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audio_path = WORKFLOW_AUDIOS_DIR / f"{paciente_cc}_{timestamp}{ext}"
    contenido = await audio.read()
    audio_path.write_bytes(contenido)

    from backend.task_db import TaskDB
    from backend.workflow_runner import ejecutar_workflow

    db_path = os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db")
    db = TaskDB(db_path)
    task_id = db.crear_task(paciente_cc=paciente_cc, audio_path=str(audio_path))

    import threading
    def _runner():
        try:
            ejecutar_workflow(audio_path=str(audio_path), paciente_cc=paciente_cc, task_id_existente=task_id)
        except Exception as e:
            print(f"[WORKFLOW BG] error: {e}", file=__import__("sys").stderr)
    threading.Thread(target=_runner, daemon=True).start()

    return {
        "ok": True,
        "task_id": task_id,
        "audio_path": str(audio_path),
        "mensaje": f"Procesamiento iniciado. Te aviso por Telegram en 10-20 min. Mientras, ver progreso en /api/tasks/{task_id}",
    }


@app.get("/api/tasks/activas")
def listar_activas():
    """Tasks actualmente en proceso (dashboard 'Mi Dia')."""
    from backend.task_db import TaskDB
    db_path = os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db")
    db = TaskDB(db_path)
    return {"ok": True, "tasks": db.listar_activos()}


@app.get("/api/tasks/paciente/{cc}")
def listar_tasks_paciente(cc: str):
    """Historial de workflows del paciente."""
    from backend.task_db import TaskDB
    db_path = os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db")
    db = TaskDB(db_path)
    return {"ok": True, "tasks": db.listar_tasks_paciente(cc)}


@app.get("/api/tasks/{task_id}")
def estado_task(task_id: str):
    """Estado actual de un workflow task."""
    from backend.task_db import TaskDB
    db_path = os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db")
    db = TaskDB(db_path)
    task = db.obtener_task(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} no encontrada")
    return {"ok": True, "task": task}


@app.post("/api/tasks/{task_id}/cancelar")
def cancelar_task(task_id: str):
    """Cancela una task."""
    from backend.task_db import TaskDB
    db_path = os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db")
    db = TaskDB(db_path)
    db.guardar_resultado(task_id, {"cancelado_por_usuario": True}, estado="cancelado")
    return {"ok": True, "mensaje": "Task cancelada"}


@app.post("/api/organizar-formato")
async def endpoint_organizar_formato(
    archivo: UploadFile = File(...),
    paciente_cc: str = Form(...),
):
    """Sandra sube un formato crudo, Tomy lo organiza."""
    ext = Path(archivo.filename or "f.docx").suffix
    tmp_path = STORAGE / "formatos_subidos" / f"organizar_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_bytes(await archivo.read())

    from backend.organizador_formato import organizar_formato
    resultado = organizar_formato(str(tmp_path), paciente_cc)
    return resultado


@app.post("/api/corregir-paciente/{cc}")
async def endpoint_corregir(cc: str, req: CorregirRequest):
    """Sandra envía corrección por chat → Tomy interpreta y aplica."""
    from backend.correction_resolver import interpretar_correccion
    from backend.aplicador_correccion import aplicar_correccion

    correccion = interpretar_correccion(req.mensaje, paciente_cc=cc)
    if correccion.get("confianza", 0) < 0.5:
        return {
            "ok": False,
            "estado": "confianza_baja",
            "mensaje": "No entendí qué corregir. ¿Me lo decís de otra forma? Por ejemplo: 'el siniestro es 503476658'.",
            "interpretacion": correccion,
        }

    resultado = aplicar_correccion(cc, correccion)
    return resultado


# ─── Auth (opcional) ────────────────────────────────────────

@app.post("/api/login")
async def login(req: LoginRequest, response: Response):
    from backend.auth_simple import validar_pin, generar_token
    if not validar_pin(req.pin):
        raise HTTPException(401, "PIN incorrecto")
    token = generar_token("Sandra")
    response.set_cookie("rilo_session", token, httponly=True, samesite="lax", max_age=86400 * 30)
    return {"ok": True, "usuario": "Sandra"}


@app.post("/api/logout")
async def logout(response: Response):
    response.delete_cookie("rilo_session")
    return {"ok": True}


@app.get("/api/whoami")
async def whoami(rilo_session: Optional[str] = Cookie(None)):
    from backend.auth_simple import validar_token
    usuario = validar_token(rilo_session) if rilo_session else None
    return {"autenticado": bool(usuario), "usuario": usuario}


# ─── System Health ─────────────────────────────────────────

@app.get("/api/system/health")
def system_health():
    """Estado del sistema completo."""
    from backend.costos_tracker import resumen_dia

    storage = Path(os.getenv("STORAGE_DIR", "./storage"))
    disk = shutil.disk_usage(str(storage))

    return {
        "ok": True,
        "fase_a_habilitada": os.getenv("FASE_A_ENABLED", "false").lower() == "true",
        "tomy_completo_habilitado": os.getenv("TOMY_COMPLETO_ENABLED", "false").lower() == "true",
        "disk": {
            "total_gb": round(disk.total / 1024**3, 1),
            "libre_gb": round(disk.free / 1024**3, 1),
            "porcentaje_uso": round(100 * (disk.total - disk.free) / disk.total, 1),
        },
        "credenciales": {
            "deepgram": bool(os.getenv("DEEPGRAM_API_KEY")),
            "opencode_go": bool(os.getenv("OPENCODE_GO_API_KEY")),
            "telegram": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
            "medifolios": bool(os.getenv("MEDIFOLIOS_USER")),
            "positiva": bool(os.getenv("POSITIVA_USER")),
        },
        "costos_hoy": resumen_dia(),
    }
