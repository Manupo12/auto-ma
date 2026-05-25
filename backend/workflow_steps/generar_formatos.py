"""
Paso 6: Generar los formatos DOCX aplicables.

Wrapper sobre backend.doc_generator (que ya tiene las 7 funciones generar_*).
Selecciona qué formatos generar según el estado del caso (NUEVO, SEGUIMIENTO, CIERRE, PRUEBA_TRABAJO).
"""
import os
import re
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List


STORAGE = Path(os.getenv("STORAGE_DIR", "./storage"))
DOCS_DIR = STORAGE / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


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
    """
    Mezcla: portal SOBREESCRIBE datos de identidad del LLM.
    Solo los datos clinicos de evaluacion (que no estan en portales) se dejan del LLM.
    """
    json_paciente = _cargar_json_paciente(cc)
    if not json_paciente or json_paciente.get("_vacio"):
        return datos_llm

    medi = json_paciente.get("medifolios", {})
    pos = json_paciente.get("positiva", {})

    pac = datos_llm.setdefault("paciente", {})

    # CAMPOS DE IDENTIDAD: SIEMPRE usar portal
    nombre_portal = (
        " ".join(filter(None, [
            medi.get("nombre1", ""), medi.get("nombre2", ""),
            medi.get("apellido1", ""), medi.get("apellido2", "")
        ])).strip()
        or medi.get("nombre", "")
    )
    if nombre_portal:
        pac["nombre"] = nombre_portal

    pac["documento"] = medi.get("numero_id", "") or cc

    if medi.get("fecha_nacimiento"):
        pac["fecha_nacimiento"] = medi["fecha_nacimiento"]

    for campo_portal, campo_pac in [
        ("telefono", "telefono"),
        ("direccion", "direccion"),
        ("email", "email"),
        ("edad", "edad"),
    ]:
        if medi.get(campo_portal):
            pac[campo_pac] = medi[campo_portal]

    for campo_portal, campo_pac in [
        ("eps_ips", "eps_ips"), ("slct_eps_paciente", "eps_ips"),
        ("afp", "afp"),         ("slct_afp_paciente", "afp"),
    ]:
        if medi.get(campo_portal):
            pac[campo_pac] = medi[campo_portal]  # SOBREESCRIBE si portal tiene el dato

    # EMPRESA: portal cuando disponible
    emp = datos_llm.setdefault("empresa", {})
    empresa_portal = (
        medi.get("empresa") or medi.get("slct_empresa_paciente") or
        (pos.get("datos_asegurado") or {}).get("empresa") or
        json_paciente.get("empresa", {}).get("nombre", "")
    )
    if empresa_portal and empresa_portal not in ("Usuario Acciones", "[VERIFICAR]"):
        emp["nombre"] = empresa_portal

    nit_portal = (pos.get("datos_asegurado") or {}).get("nit", "")
    if nit_portal:
        emp["nit"] = nit_portal

    # SINIESTRO: solo portal-oficial, no [VERIFICAR]
    sin = datos_llm.setdefault("siniestro", {})
    siniestro_portal = ""
    if medi.get("siniestro_medi") and medi["siniestro_medi"] != "[VERIFICAR]":
        siniestro_portal = medi["siniestro_medi"]
    elif pos.get("siniestro_id"):
        siniestro_portal = pos["siniestro_id"]
    elif (pos.get("siniestros") or []):
        siniestro_portal = pos["siniestros"][0].get("id", "")
    # Fallback: siniestro en tabla de autorizaciones
    if not siniestro_portal and pos.get("autorizaciones"):
        for aut in pos["autorizaciones"][:3]:
            posible_sin = str(aut.get("descripcion", "")).strip()
            if re.match(r'^\d{8,12}$', posible_sin):
                siniestro_portal = posible_sin
                posible_fecha = str(aut.get("estado", "")).strip()
                if re.match(r'\d{2}/\d{2}/\d{4}', posible_fecha):
                    if not sin.get("fecha_evento"):
                        sin["fecha_evento"] = posible_fecha
                break
    if siniestro_portal:
        sin["id_siniestro"] = siniestro_portal

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


def _sanitize_nombre(nombre: str) -> str:
    """Convierte un nombre en slug para nombre de archivo."""
    limpio = re.sub(r"[^a-zA-Z0-9\s]", "", nombre or "")
    limpio = re.sub(r"\s+", " ", limpio).strip()
    return limpio.replace(" ", "")[:40] or "paciente"


def _siguiente_version(fmt: str, cc: str, nombre_slug: str) -> int:
    """Encuentra el siguiente numero de version para este formato+paciente."""
    patron = DOCS_DIR.glob(f"{fmt}_{nombre_slug}_v*.docx")
    max_v = 0
    for p in patron:
        m = re.search(r"_v(\d+)\.docx$", p.name)
        if m:
            max_v = max(max_v, int(m.group(1)))
    return max_v + 1


def generar_todos(datos: dict, task_id: str) -> Dict:
    estado = datos.get("estado_caso", "SEGUIMIENTO")
    formatos = _seleccionar_formatos(estado)
    _log(f"Estado {estado}: generar {len(formatos)} formatos: {formatos}")

    generados = []
    errores = []
    cc = datos.get("paciente", {}).get("documento", "")
    if not cc:
        return {"ok": False, "error": "CC vacio en datos_clinicos, no se generan formatos sin identificador", "formatos_generados": [], "errores": [], "total": 0, "estado_caso": estado}

    nombre_pac = datos.get("paciente", {}).get("nombre", "")
    nombre_slug = _sanitize_nombre(nombre_pac)

    for fmt in formatos:
        try:
            version = _siguiente_version(fmt, cc, nombre_slug)
            output_name = f"{fmt}_{nombre_slug}_v{version}"
            path = generar_documento(fmt, datos, output_name=output_name)
            generados.append({"formato": fmt, "archivo": path, "version": version})
            _log(f"{fmt} v{version}: {Path(path).name}")
        except Exception as e:
            _log(f"{fmt}: {type(e).__name__}: {e}")
            errores.append({"formato": fmt, "error": f"{type(e).__name__}: {e}"})

    ok = len(errores) == 0
    ok_parcial = len(generados) > 0
    return {
        "ok": ok,
        "ok_parcial": ok_parcial,
        "formatos_generados": generados,
        "errores": errores,
        "total": len(formatos),
        "estado_caso": estado,
    }


def ejecutar(datos_clinicos: dict, task_id: str, verificaciones: list = None) -> dict:
    if not datos_clinicos:
        return {"ok": False, "error": "Sin datos_clinicos para generar"}
    cc = datos_clinicos.get("paciente", {}).get("documento", "")
    if not cc:
        return {"ok": False, "error": "CC vacio en datos_clinicos, no se generan formatos sin identificador"}
    if cc:
        datos_clinicos = _merge_paciente_con_llm(datos_clinicos, cc)

    advertencias = []
    if datos_clinicos.get("siniestro", {}).get("id_siniestro", "").startswith("["):
        advertencias.append("Siniestro no verificado en portal - confirmar numero con Sandra")
    if not datos_clinicos.get("siniestro", {}).get("fecha_evento"):
        advertencias.append("Fecha del evento no disponible - completar manualmente")
    if not datos_clinicos.get("siniestro", {}).get("diagnostico_cie10") or \
       "[FALTA" in str(datos_clinicos.get("siniestro", {}).get("diagnostico_cie10", "")):
        advertencias.append("Diagnostico CIE-10 no verificado - completar desde Positiva")

    if advertencias:
        datos_clinicos["_advertencias_documento"] = advertencias
        _log(f"Advertencias en generacion: {advertencias}")

    return generar_todos(datos_clinicos, task_id)
