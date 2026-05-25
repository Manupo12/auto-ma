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
    """
    Compara Medifolios vs. Positiva campo a campo.
    Retorna lista de conflictos con nivel de severidad y recomendacion.
    """
    import unicodedata
    import re as _re
    discrepancias = []

    def _norm(s: str) -> str:
        if not s: return ""
        s = unicodedata.normalize("NFD", str(s).lower().strip())
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        return " ".join(s.split())

    def _similitud_palabras(s1: str, s2: str) -> float:
        p1 = set(s1.split())
        p2 = set(s2.split())
        if not p1 or not p2:
            return 0.0
        inter = p1 & p2
        union = p1 | p2
        return len(inter) / len(union)

    def _agregar(campo, v_medi, v_pos, severidad="advertencia", resolucion=""):
        if v_medi and v_pos and _norm(str(v_medi)) != _norm(str(v_pos)):
            discrepancias.append({
                "campo": campo,
                "medifolios": v_medi,
                "positiva": v_pos,
                "severidad": severidad,
                "resolucion": resolucion or f"Verificar cual es correcto — diferencia: '{v_medi}' vs '{v_pos}'",
            })

    # 1. Siniestro (critico)
    siniestro_medi = datos_medi.get("siniestro_medi", "")
    siniestros_pos = datos_pos.get("siniestros", [])
    siniestro_pos = siniestros_pos[0].get("id", "") if siniestros_pos else ""
    _agregar("siniestro", siniestro_medi, siniestro_pos,
             severidad="critico", resolucion="Usar valor de Positiva (fuente oficial ARL)")

    # 2. Nombre del paciente (advertencia)
    nombre_medi = datos_medi.get("nombre", "")
    nombre_pos = (datos_pos.get("datos_asegurado", {}) or {}).get("nombre", "")
    if nombre_medi and nombre_pos and _norm(nombre_medi) != _norm(nombre_pos):
        n1 = nombre_medi.replace("Á","A").replace("É","E").replace("Í","I").replace("Ó","O").replace("Ú","U").upper()
        n2 = nombre_pos.replace("Á","A").replace("É","E").replace("Í","I").replace("Ó","O").replace("Ú","U").upper()
        if n1 == n2:
            pass
        elif _similitud_palabras(_norm(nombre_medi), _norm(nombre_pos)) > 0.8:
            pass
        else:
            _agregar("nombre", nombre_medi, nombre_pos,
                     severidad="advertencia", resolucion="Verificar cedula fisica del paciente")

    # 3. Diagnostico CIE-10 (critico)
    diag_medi = datos_medi.get("diagnostico_cie10", "")
    siniestro_principal = next((s for s in siniestros_pos if s.get("tipo") in ["AT", ""]), {})
    diag_pos = siniestro_principal.get("diagnostico", "") if siniestros_pos else ""
    if diag_pos and len(diag_pos) > 3:
        match = _re.match(r"^([A-Z]\d{2,3})", diag_pos.strip())
        if match:
            diag_pos = match.group(1)
    _agregar("diagnostico_cie10", diag_medi, diag_pos,
             severidad="critico", resolucion="Usar Positiva (diagnostico oficial ARL)")

    # 4. Empresa (informativo)
    empresa_medi = datos_medi.get("empresa", "")
    empresa_pos = (datos_pos.get("datos_asegurado", {}) or {}).get("empresa", "")
    _agregar("empresa", empresa_medi, empresa_pos,
             severidad="informativo", resolucion="Usar el nombre completo de Positiva para documentos oficiales")

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

    pos_tiene_datos = bool(
        datos_pos.get("siniestros") or datos_pos.get("siniestro_id") or
        datos_pos.get("diagnosticos") or datos_pos.get("cie10_candidatos") or
        datos_pos.get("fecha_siniestro")
    )
    medi_tiene_datos = bool(
        datos_medi.get("nombre1") or datos_medi.get("nombre")
    )

    parcial = (
        bool(datos_medi.get("error") or datos_pos.get("error")) or
        not pos_tiene_datos or
        not medi_tiene_datos
    )

    # Fusionar
    fusionado = {
        "cc": cc,
        "medifolios": datos_medi,
        "positiva": datos_pos,
        "_meta": {
            "extraido_en": datetime.now().isoformat(),
            "fuentes": ["medifolios", "positiva"],
            "discrepancias": discrepancias,
            "parcial": parcial,
        },
    }

    if not pos_tiene_datos:
        fusionado["_meta"]["pos_sin_datos"] = True
        fusionado["_meta"]["advertencia_portales"] = "Positiva no devolvio siniestros ni diagnostico"

    if guardar:
        _guardar_json(cc, fusionado)

    return fusionado
