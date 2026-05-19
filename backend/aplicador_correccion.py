"""
Aplicador de correcciones a JSON del paciente + regenera formatos afectados.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def _log(msg: str):
    print(f"[APLICADOR {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


CAMPO_FORMATOS = {
    "siniestro.": ["analisis", "medidas", "recomendaciones", "cierre", "prueba", "valoracion"],
    "paciente.": ["analisis", "medidas", "recomendaciones", "cierre", "citacion", "prueba", "valoracion"],
    "empresa.": ["analisis", "citacion", "valoracion"],
    "metodologia": ["analisis", "prueba"],
    "concepto_desempeno": ["valoracion", "cierre"],
    "recomendaciones.": ["medidas", "recomendaciones"],
    "logros": ["cierre"],
    "obstaculos": ["cierre"],
}


def _formatos_afectados(campo: str) -> List[str]:
    for key, formatos in CAMPO_FORMATOS.items():
        if campo.startswith(key) or campo == key.rstrip("."):
            return formatos
    return []


def _set_anidado(d: dict, path: str, valor):
    keys = path.split(".")
    cur = d
    for k in keys[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    cur[keys[-1]] = valor


def _regenerar_formatos_afectados(paciente_cc: str, formatos: List[str], datos: dict) -> Dict:
    if not formatos:
        return {"regenerados": [], "errores": []}
    from backend.workflow_steps.generar_formatos import generar_documento
    regenerados = []
    errores = []
    for fmt in formatos:
        try:
            output_name = f"{fmt}_{paciente_cc}_correccion_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            path = generar_documento(fmt, datos, output_name=output_name)
            regenerados.append({"formato": fmt, "archivo": path})
            _log(f"✅ regenerado {fmt}: {Path(path).name}")
        except Exception as e:
            errores.append({"formato": fmt, "error": f"{type(e).__name__}: {e}"})
            _log(f"❌ {fmt}: {e}")
    return {"regenerados": regenerados, "errores": errores}


def aplicar_correccion(paciente_cc: str, correccion: Dict) -> Dict:
    storage = Path(os.getenv("STORAGE_DIR", "./storage"))
    json_files = sorted((storage / "data").glob(f"*{paciente_cc}*completo.json"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    if not json_files:
        return {"ok": False, "error": f"No hay JSON para CC {paciente_cc}"}

    json_path = json_files[0]
    with open(json_path, encoding="utf-8") as f:
        datos = json.load(f)

    campo = correccion.get("campo")
    valor_nuevo = correccion.get("valor_nuevo")

    if not campo or valor_nuevo is None:
        return {"ok": False, "error": "Corrección sin campo o valor_nuevo"}

    _set_anidado(datos, campo, valor_nuevo)

    meta = datos.setdefault("_meta", {})
    correcciones = meta.setdefault("correcciones", [])
    correcciones.append({
        "campo": campo,
        "valor_nuevo": valor_nuevo,
        "valor_anterior": correccion.get("valor_anterior"),
        "fuente": "manual_sandra",
        "timestamp": datetime.now().isoformat(),
    })

    json_path.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"JSON actualizado: {campo} = {valor_nuevo}")

    formatos = _formatos_afectados(campo)
    regen = _regenerar_formatos_afectados(paciente_cc, formatos, datos)

    return {
        "ok": True,
        "campo_corregido": campo,
        "valor_nuevo": valor_nuevo,
        "formatos_regenerados": regen["regenerados"],
        "errores": regen["errores"],
    }
