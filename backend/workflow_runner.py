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
    ("verificar_portales", "verificando_portales", 6),
    ("generar_formatos", "generando", 7),
    ("qa_formatos", "qa", 8),
    ("convertir_pdf", "pdf", 9),
    ("notificar_listo", "notificando", 10),
]

TIMEOUT_POR_PASO = {
    "transcribir": 600,
    "resolver_paciente": 120,
    "leer_notas_crudas": 60,
    "leer_formatos_subidos": 60,
    "sintetizar_maestro": 300,
    "verificar_portales": 180,
    "generar_formatos": 120,
    "qa_formatos": 60,
    "convertir_pdf": 120,
    "notificar_listo": 30,
}


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
        _log(f"PASO {paso_num}/10: {step_name}")
        t_step = time.time()

        try:
            modulo = __import__(f"backend.workflow_steps.{step_name}", fromlist=["ejecutar"])
            kwargs = _build_kwargs(step_name, contexto)
            timeout = TIMEOUT_POR_PASO.get(step_name, 120)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(modulo.ejecutar, **kwargs)
                try:
                    resultado_step = future.result(timeout=timeout)
                except concurrent.futures.TimeoutError:
                    db.marcar_error(task_id, paso=paso_num, error=f"Timeout en {step_name} (>{timeout}s)")
                    return {"task_id": task_id, "estado": f"error_en_paso_{paso_num}", "error": f"Timeout >{timeout}s"}
            contexto[step_name] = resultado_step
            _log(f"PASO {paso_num} OK en {time.time()-t_step:.1f}s")

            if step_name in ("sintetizar_maestro", "generar_formatos") and not resultado_step.get("ok"):
                error = resultado_step.get("error", f"step {step_name} retornó ok=false")
                db.marcar_error(task_id, paso=paso_num, error=error)
                return {"task_id": task_id, "estado": f"error_en_paso_{paso_num}", "error": error}

            # Si faltan datos tras sintesis, seguir pero marcar advertencia
            if step_name == "sintetizar_maestro":
                datos_clinicos = resultado_step.get("datos_clinicos") or {}
                faltantes = datos_clinicos.get("_meta", {}).get("campos_faltantes", [])
                if faltantes:
                    _log(f"⚠️ Datos sin confirmar ({len(faltantes)}): {faltantes[:4]}")
                    if not contexto.get("advertencias"):
                        contexto["advertencias"] = []
                    contexto["advertencias"].extend(faltantes)

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
        "verificacion": contexto.get("verificar_portales", {}).get("resumen", {}),
        "discrepancias": contexto.get("verificar_portales", {}).get("verificaciones", []),
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
    if step_name == "verificar_portales":
        sintesis = contexto.get("sintetizar_maestro", {})
        return {
            "datos_clinicos": sintesis.get("datos_clinicos") or {},
            "paciente_cc": cc,
        }
    if step_name == "generar_formatos":
        # Usar datos enriquecidos de la verificacion si existen
        verif = contexto.get("verificar_portales", {})
        sintesis = contexto.get("sintetizar_maestro", {})
        datos_clinicos = verif.get("datos_enriquecidos") or sintesis.get("datos_clinicos") or {}
        # Aplicar campos completados del portal
        for campo, valor in verif.get("campos_completados", {}).items():
            if not _get_nested(datos_clinicos, campo) and valor:
                _set_nested(datos_clinicos, campo, valor)
        return {"datos_clinicos": datos_clinicos, "task_id": task_id, "verificaciones": verif.get("verificaciones", [])}
    if step_name == "qa_formatos":
        return {"formatos_generados": contexto.get("generar_formatos", {}).get("formatos_generados", [])}
    if step_name == "convertir_pdf":
        return {"qa_resultados": contexto.get("qa_formatos", {}).get("resultados", [])}
    if step_name == "notificar_listo":
        portales = contexto.get("resolver_paciente", {}).get("datos_portales", {})
        nombre = portales.get("medifolios", {}).get("nombre1", "") + " " + portales.get("medifolios", {}).get("apellido1", "")
        verif = contexto.get("verificar_portales", {})
        return {
            "task_id": task_id,
            "paciente_nombre": nombre.strip() or f"CC {cc}",
            "paciente_cc": cc,
            "formatos_generados": contexto.get("generar_formatos", {}).get("formatos_generados", []),
            "warnings": contexto.get("transcribir", {}).get("warnings", []),
            "resumen_verificacion": verif.get("resumen", {}),
            "discrepancias": verif.get("verificaciones", []),
        }
    return {}


def _get_nested(d: dict, campo: str):
    """Obtiene valor anidado: 'paciente.nombre' -> d['paciente']['nombre']"""
    partes = campo.split(".")
    for p in partes:
        if isinstance(d, dict):
            d = d.get(p, "")
        else:
            return ""
    return d if isinstance(d, str) else ""


def _set_nested(d: dict, campo: str, valor: str):
    """Setea valor anidado: 'paciente.nombre' = 'Maribel'"""
    partes = campo.split(".")
    for p in partes[:-1]:
        if p not in d:
            d[p] = {}
        d = d[p]
    d[partes[-1]] = valor
