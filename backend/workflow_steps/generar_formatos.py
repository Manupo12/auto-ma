"""
Paso 6: Generar los formatos DOCX aplicables.

Wrapper sobre backend.doc_generator (que ya tiene las 7 funciones generar_*).
Selecciona qué formatos generar según el estado del caso (NUEVO, SEGUIMIENTO, CIERRE, PRUEBA_TRABAJO).
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List


def _log(msg: str):
    print(f"[GENERAR_FORMATOS {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


FORMATOS_POR_ESTADO = {
    "NUEVO": ["analisis", "medidas", "recomendaciones", "citacion", "valoracion"],
    "SEGUIMIENTO": ["analisis", "medidas", "recomendaciones", "valoracion"],
    "CIERRE": ["analisis", "medidas", "recomendaciones", "cierre", "valoracion"],
    "PRUEBA_TRABAJO": ["analisis", "prueba", "valoracion"],
}

FORMATO_FUNC = {
    "analisis": "generar_analisis_exigencia",
    "medidas": "generar_carta_medidas",
    "recomendaciones": "generar_carta_recomendaciones",
    "cierre": "generar_cierre_caso",
    "citacion": "generar_citacion_empresas",
    "prueba": "generar_prueba_trabajo",
    "valoracion": "generar_valoracion_desempeno",
}


def _seleccionar_formatos(estado_caso: str) -> List[str]:
    estado = (estado_caso or "SEGUIMIENTO").upper()
    return FORMATOS_POR_ESTADO.get(estado, FORMATOS_POR_ESTADO["SEGUIMIENTO"])


def generar_documento(formato_corto: str, datos: dict, output_name: str = None) -> str:
    from backend import doc_generator
    func_name = FORMATO_FUNC[formato_corto]
    func = getattr(doc_generator, func_name, None)
    if not func:
        raise ValueError(f"No existe generador para formato '{formato_corto}'")
    return func(datos, output_name=output_name)


def generar_todos(datos: dict, task_id: str) -> Dict:
    estado = datos.get("estado_caso", "SEGUIMIENTO")
    formatos = _seleccionar_formatos(estado)
    _log(f"Estado {estado}: generar {len(formatos)} formatos: {formatos}")

    generados = []
    errores = []
    cc = datos.get("paciente", {}).get("documento", "sin_cc")

    for fmt in formatos:
        try:
            output_name = f"{fmt}_{cc}_{task_id[:8]}"
            path = generar_documento(fmt, datos, output_name=output_name)
            generados.append({"formato": fmt, "archivo": path})
            _log(f"✅ {fmt}: {Path(path).name}")
        except Exception as e:
            _log(f"❌ {fmt}: {type(e).__name__}: {e}")
            errores.append({"formato": fmt, "error": f"{type(e).__name__}: {e}"})

    return {
        "ok": len(generados) > 0,
        "formatos_generados": generados,
        "errores": errores,
        "total": len(formatos),
        "estado_caso": estado,
    }


def ejecutar(datos_clinicos: dict, task_id: str) -> dict:
    if not datos_clinicos:
        return {"ok": False, "error": "Sin datos_clinicos para generar"}
    return generar_todos(datos_clinicos, task_id)
