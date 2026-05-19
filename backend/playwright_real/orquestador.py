"""
Orquestador de extracción: une Medifolios + Positiva, cruza datos, marca discrepancias.

Uso:
    datos = await extraer_paciente_completo("1193143688")
    # datos["_meta"]["discrepancias"] → lista de conflictos encontrados
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from backend.playwright_real.session import abrir_contexto
from backend.playwright_real import medifolios
from backend.playwright_real import positiva


STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./storage"))


def _log(msg: str):
    import sys
    print(f"[ORQ {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _detectar_discrepancias(datos_medi: Dict, datos_pos: Dict) -> list:
    """Compara datos entre Medifolios y Positiva. Retorna lista de conflictos."""
    discrepancias = []

    siniestro_medi = datos_medi.get("siniestro_medi", "")
    siniestros_pos = datos_pos.get("siniestros", [])
    siniestro_pos = siniestros_pos[0].get("id", "") if siniestros_pos else ""

    if siniestro_medi and siniestro_pos and siniestro_medi != "[VERIFICAR]":
        if siniestro_medi != siniestro_pos:
            discrepancias.append({
                "campo": "siniestro",
                "medifolios": siniestro_medi,
                "positiva": siniestro_pos,
                "resolucion": "prevalecer Positiva (fuente oficial)",
            })

    return discrepancias


def _guardar_json(cc: str, datos: Dict):
    """Guarda JSON en storage/data/{cc}-completo.json."""
    data_dir = STORAGE_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / f"{cc}-completo.json"
    path.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"guardado: {path}")


def _cargar_json(cc: str) -> Optional[Dict]:
    """Carga JSON si existe."""
    path = STORAGE_DIR / "data" / f"{cc}-completo.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


async def extraer_paciente_completo(cc: str, guardar: bool = True) -> Dict:
    """
    Función principal. Extrae datos de Medifolios + Positiva.
    Si guardar=True, persiste JSON en storage/data/{cc}-completo.json.
    """
    _log(f"extrayendo CC {cc}...")

    datos_medi = {}
    datos_pos = {}

    # Extraer de Medifolios
    try:
        async with abrir_contexto(portal="medifolios") as (_, _, page):
            datos_medi = await medifolios.get_paciente_completo(page, cc)
        _log(f"MEDI: {len(datos_medi)} campos")
    except Exception as e:
        _log(f"MEDI: error {type(e).__name__}: {e}")
        datos_medi = {"cc_buscado": cc, "fuente": "medifolios", "error": f"{type(e).__name__}: {e}"}

    # Extraer de Positiva
    try:
        async with abrir_contexto(portal="positiva") as (_, _, page):
            datos_pos = await positiva.get_paciente_completo(page, cc)
        _log(f"POS: {len(datos_pos)} campos")
    except Exception as e:
        _log(f"POS: error {type(e).__name__}: {e}")
        datos_pos = {"cc_buscado": cc, "fuente": "positiva", "error": f"{type(e).__name__}: {e}"}

    # Detectar discrepancias
    discrepancias = _detectar_discrepancias(datos_medi, datos_pos)

    # Fusionar
    fusionado = {
        "cc": cc,
        "medifolios": datos_medi,
        "positiva": datos_pos,
        "_meta": {
            "extraido_en": datetime.now().isoformat(),
            "fuentes": ["medifolios", "positiva"],
            "discrepancias": discrepancias,
            "parcial": bool(datos_medi.get("error") or datos_pos.get("error")),
        },
    }

    if guardar:
        _guardar_json(cc, fusionado)

    return fusionado
