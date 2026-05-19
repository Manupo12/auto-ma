"""
Workflow runner — orquesta los 9 pasos del pipeline "Día de Sandra".

Uso:
    from backend.workflow_runner import ejecutar_workflow
    resultado = ejecutar_workflow(audio_path="/path/a.m4a", paciente_cc="1193143688")
    # → {"task_id": "abc12345", "estado": "listo", ...}

También se puede ejecutar en background con asyncio.create_task() desde FastAPI.
"""
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict


def _log(msg: str):
    print(f"[WORKFLOW {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


STEPS = [
    ("transcribir", "transcribiendo", 1),
    ("resolver_paciente", "resolviendo_paciente", 2),
    ("leer_notas_crudas", "leyendo_notas", 3),
    ("leer_formatos_subidos", "leyendo_formatos", 4),
    ("sintetizar_maestro", "sintetizando", 5),
    ("generar_formatos", "generando", 6),
    ("qa_formatos", "qa", 7),
    ("convertir_pdf", "pdf", 8),
    ("notificar_listo", "notificando", 9),
]


def ejecutar_workflow(audio_path: str, paciente_cc: str, task_id_existente: str = None) -> Dict:
    """Ejecuta los 9 pasos secuencialmente. Persiste estado en task_db."""
    if os.getenv("TOMY_COMPLETO_ENABLED", "false").lower() != "true":
        return {"estado": "deshabilitado", "razon": "TOMY_COMPLETO_ENABLED=false"}

    from backend.task_db import TaskDB

    db_path = os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db")
    db = TaskDB(db_path)

    if task_id_existente:
        task_id = task_id_existente
    else:
        task_id = db.crear_task(paciente_cc=paciente_cc, audio_path=audio_path)

    _log(f"═══ TASK {task_id} | CC {paciente_cc} ═══")
    contexto = {"audio_path": audio_path, "paciente_cc": paciente_cc, "task_id": task_id}
    t_total = time.time()

    for step_name, estado_label, paso_num in STEPS:
        db.actualizar_paso(task_id, paso=paso_num, estado=estado_label)
        _log(f"PASO {paso_num}/9: {step_name}")
        t_step = time.time()

        try:
            modulo = __import__(f"backend.workflow_steps.{step_name}", fromlist=["ejecutar"])
            kwargs = _build_kwargs(step_name, contexto)
            resultado_step = modulo.ejecutar(**kwargs)
            contexto[step_name] = resultado_step
            _log(f"PASO {paso_num} OK en {time.time()-t_step:.1f}s")

            if step_name in ("sintetizar_maestro", "generar_formatos") and not resultado_step.get("ok"):
                error = resultado_step.get("error", f"step {step_name} retornó ok=false")
                db.marcar_error(task_id, paso=paso_num, error=error)
                return {"task_id": task_id, "estado": f"error_en_paso_{paso_num}", "error": error}

            # NUEVO: Si faltan datos críticos tras síntesis, notificar y pausar
            if step_name == "sintetizar_maestro":
                datos_clinicos = resultado_step.get("datos_clinicos") or {}
                faltantes = datos_clinicos.get("_meta", {}).get("campos_faltantes", [])
                criticos = [f for f in faltantes if any(c in f.lower() for c in ["siniestro", "cc", "nombre", "diagnostico"])]
                if criticos:
                    _log(f"⚠️ Datos críticos faltantes: {criticos}")
                    try:
                        from backend.notificador import enviar_telegram
                        enviar_telegram(
                            f"⚠️ Procesé el audio de CC {paciente_cc} pero me faltan datos críticos:\n" +
                            "\n".join(f"  • {c}" for c in criticos[:5]) +
                            f"\n\n¿Me los das?: http://localhost:3000/paciente/{paciente_cc}"
                        )
                    except Exception as notif_err:
                        _log(f"Error notificando datos críticos: {notif_err}")
                    db.guardar_resultado(task_id, {"campos_faltantes": criticos, "datos_parciales": datos_clinicos}, estado="esperando_datos")
                    return {"task_id": task_id, "estado": "esperando_datos", "campos_faltantes": criticos}

        except Exception as e:
            _log(f"PASO {paso_num} FALLÓ: {type(e).__name__}: {e}")
            db.marcar_error(task_id, paso=paso_num, error=f"{type(e).__name__}: {e}")
            return {"task_id": task_id, "estado": f"error_en_paso_{paso_num}", "error": str(e)}

    formatos_generados = contexto.get("generar_formatos", {}).get("formatos_generados", [])
    pdfs = contexto.get("convertir_pdf", {}).get("pdfs", [])
    warnings = contexto.get("transcribir", {}).get("warnings", [])
    qa_warnings = []
    for r in contexto.get("qa_formatos", {}).get("resultados", []):
        qa_warnings.extend(r.get("qa_warnings", []))

    resultado_final = {
        "task_id": task_id,
        "estado": "listo",
        "duracion_total_s": round(time.time() - t_total, 1),
        "paciente_cc": paciente_cc,
        "formatos_generados": formatos_generados,
        "pdfs": pdfs,
        "warnings": warnings + qa_warnings,
    }
    db.guardar_resultado(task_id, resultado_final, estado="listo")
    _log(f"═══ TASK {task_id} LISTO en {time.time()-t_total:.1f}s ═══")
    return resultado_final


def _build_kwargs(step_name: str, contexto: dict) -> dict:
    audio = contexto.get("audio_path")
    cc = contexto.get("paciente_cc")
    task_id = contexto.get("task_id")

    if step_name == "transcribir":
        return {"audio_path": audio, "paciente_cc": cc}
    if step_name == "resolver_paciente":
        return {"paciente_cc": cc, "forzar_extraer": False}
    if step_name == "leer_notas_crudas":
        return {"paciente_cc": cc}
    if step_name == "leer_formatos_subidos":
        return {"task_id": task_id}
    if step_name == "sintetizar_maestro":
        return {
            "transcripcion": contexto.get("transcribir", {}),
            "datos_portales": contexto.get("resolver_paciente", {}).get("datos_portales", {}),
            "notas_crudas": contexto.get("leer_notas_crudas", {}).get("notas_crudas", []),
            "formatos_subidos": contexto.get("leer_formatos_subidos", {}).get("formatos_subidos", []),
            "paciente_cc": cc,
        }
    if step_name == "generar_formatos":
        sintesis = contexto.get("sintetizar_maestro", {})
        return {"datos_clinicos": sintesis.get("datos_clinicos") or {}, "task_id": task_id}
    if step_name == "qa_formatos":
        return {"formatos_generados": contexto.get("generar_formatos", {}).get("formatos_generados", [])}
    if step_name == "convertir_pdf":
        return {"qa_resultados": contexto.get("qa_formatos", {}).get("resultados", [])}
    if step_name == "notificar_listo":
        portales = contexto.get("resolver_paciente", {}).get("datos_portales", {})
        nombre = portales.get("medifolios", {}).get("nombre1", "") + " " + portales.get("medifolios", {}).get("apellido1", "")
        return {
            "task_id": task_id,
            "paciente_nombre": nombre.strip() or f"CC {cc}",
            "paciente_cc": cc,
            "formatos_generados": contexto.get("generar_formatos", {}).get("formatos_generados", []),
            "warnings": contexto.get("transcribir", {}).get("warnings", []),
        }
    return {}
