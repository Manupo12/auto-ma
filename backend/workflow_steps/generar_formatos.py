"""
Paso 6: Generar los formatos DOCX aplicables.

Wrapper sobre backend.doc_generator (que ya tiene las 7 funciones generar_*).
Selecciona qué formatos generar según el estado del caso (NUEVO, SEGUIMIENTO, CIERRE, PRUEBA_TRABAJO).
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List


STORAGE = Path(os.getenv("STORAGE_DIR", "./storage"))


def _log(msg: str):
    print(f"[GENERAR_FORMATOS {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _cargar_json_paciente(cc: str) -> dict:
    """Carga el JSON del paciente para enriquecer los datos del LLM."""
    import glob as _glob
    patterns = [
        str(STORAGE / "data" / f"{cc}-completo.json"),
        str(STORAGE / "data" / f"*{cc}*completo.json"),
        str(STORAGE / "data" / f"{cc}.json"),
    ]
    for pat in patterns:
        matches = sorted(_glob.glob(pat), key=os.path.getmtime, reverse=True)
        if matches:
            with open(matches[0], encoding="utf-8") as f:
                return json.load(f)
    return {}


def _merge_paciente_con_llm(datos_llm: dict, cc: str) -> dict:
    """Mezcla datos del JSON del paciente sobre lo que produjo el LLM."""
    json_paciente = _cargar_json_paciente(cc)
    if not json_paciente or json_paciente.get("_vacio"):
        return datos_llm

    medi = json_paciente.get("medifolios", {})
    pos = json_paciente.get("positiva", {})
    pac = json_paciente.get("paciente", {})

    # Rellenar paciente si falta
    if not datos_llm.get("paciente") or not datos_llm["paciente"].get("nombre"):
        datos_llm["paciente"] = datos_llm.get("paciente") or {}
        if not datos_llm["paciente"].get("nombre"):
            nombre = medi.get("nombre1", "") or medi.get("nombre", "") or pac.get("nombre", "")
            apellido = medi.get("apellido1", "") or pac.get("apellido", "")
            if nombre:
                datos_llm["paciente"]["nombre"] = f"{nombre} {apellido}".strip()
        if not datos_llm["paciente"].get("documento"):
            datos_llm["paciente"]["documento"] = cc
        for k in ("direccion", "telefono", "email", "edad", "eps_ips", "afp"):
            if not datos_llm["paciente"].get(k):
                val = medi.get(k) or pac.get(k) or ""
                if val:
                    datos_llm["paciente"][k] = val

    # Rellenar empresa si falta
    if not datos_llm.get("empresa") or not datos_llm["empresa"].get("nombre"):
        datos_llm["empresa"] = datos_llm.get("empresa") or {}
        empresa = medi.get("empresa") or pac.get("empresa") or json_paciente.get("empresa", {}).get("nombre", "")
        if empresa:
            datos_llm["empresa"]["nombre"] = empresa
        if not datos_llm["empresa"].get("cargo"):
            cargo = medi.get("cargo") or pac.get("cargo") or pac.get("ocupacion") or ""
            if cargo:
                datos_llm["empresa"]["cargo"] = cargo

    # Rellenar siniestro si falta
    if not datos_llm.get("siniestro") or not datos_llm["siniestro"].get("id_siniestro"):
        datos_llm["siniestro"] = datos_llm.get("siniestro") or {}
        if not datos_llm["siniestro"].get("id_siniestro"):
            siniestro = medi.get("siniestro_medi") or pos.get("siniestro_id") or json_paciente.get("siniestro", {}).get("id_siniestro", "")
            if siniestro and siniestro != "[VERIFICAR]":
                datos_llm["siniestro"]["id_siniestro"] = siniestro

    return datos_llm


def _log(msg: str):
    print(f"[GENERAR_FORMATOS {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


FORMATOS_POR_ESTADO = {
    "NUEVO": ["analisis", "medidas", "recomendaciones", "citacion", "valoracion", "cierre", "prueba"],
    "SEGUIMIENTO": ["analisis", "medidas", "recomendaciones", "valoracion", "citacion", "prueba", "cierre"],
    "CIERRE": ["analisis", "medidas", "recomendaciones", "cierre", "valoracion", "citacion", "prueba"],
    "PRUEBA_TRABAJO": ["analisis", "prueba", "valoracion", "medidas", "recomendaciones", "cierre", "citacion"],
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
        "ok": len(errores) == 0,
        "formatos_generados": generados,
        "errores": errores,
        "total": len(formatos),
        "estado_caso": estado,
    }


def ejecutar(datos_clinicos: dict, task_id: str, verificaciones: list = None) -> dict:
    if not datos_clinicos:
        return {"ok": False, "error": "Sin datos_clinicos para generar"}
    cc = datos_clinicos.get("paciente", {}).get("documento", "")
    if cc:
        datos_clinicos = _merge_paciente_con_llm(datos_clinicos, cc)
    return generar_todos(datos_clinicos, task_id)
