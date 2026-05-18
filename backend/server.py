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
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="RILO SAS API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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


# ── Modelos ────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    mensaje: str
    paciente_cc: Optional[str] = None


class GenerarRequest(BaseModel):
    estado_caso: Optional[str] = None


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
    Punto de entrada del chat. Por ahora responde con lógica básica.
    En producción, este endpoint reenvía al agente Hermes.
    """
    msg = req.mensaje.lower()
    cc = req.paciente_cc

    if "siniestro" in msg:
        respuesta = "El siniestro está registrado en los datos del paciente. ¿Necesitas generar algún formato?"
    elif "formato" in msg or "generar" in msg:
        respuesta = (
            "Puedo generar estos formatos:\n"
            "1. Análisis de Exigencias\n2. Carta de Medidas\n3. Carta de Recomendaciones\n"
            "4. Cierre de Caso\n5. Citación de Empresas\n6. Prueba de Trabajo\n"
            "7. Valoración del Desempeño\n\n¿Cuál necesitas? Dime el estado del caso (NUEVO, SEGUIMIENTO, CIERRE)."
        )
    elif "buscar" in msg or "paciente" in msg:
        respuesta = "Para buscar un paciente, dime el número de cédula."
    elif "corregir" in msg or "cambiar" in msg or "falta" in msg:
        respuesta = (
            "Entendido. Puedo corregir el documento. Dime qué hay que cambiar, por ejemplo:\n"
            "• 'Falta el número de siniestro'\n• 'Cambia la fecha a 15/05/2026'\n• 'El diagnóstico está mal'"
        )
    else:
        respuesta = (
            "¡Hola Sandra! Soy Tomy. Puedo ayudarte a:\n"
            "• Buscar pacientes en Medifolios y ARL Positiva\n"
            "• Generar los 7 formatos clínicos\n"
            "• Corregir documentos según tus indicaciones\n"
            "• Transcribir audios de citas\n\n¿En qué te ayudo?"
        )

    return {
        "rol": "asistente",
        "contenido": respuesta,
        "timestamp": datetime.now().isoformat(),
    }


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
