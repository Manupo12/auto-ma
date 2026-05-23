"""
Paso 2: Resolver datos del paciente.

1. Si existe JSON pre-extraído reciente (<48h) → usarlo.
2. Si no existe y FASE_A_ENABLED → disparar Playwright en vivo.
3. Si no existe y Fase A desactivada → devolver vacío con marca.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Tuple


def _log(msg: str):
    print(f"[RESOLVER {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _json_path(cc: str) -> Path:
    storage = Path(os.getenv("STORAGE_DIR", "./storage"))
    matches = sorted((storage / "data").glob(f"*{cc}*completo.json"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _es_reciente(path: Path, horas_max: int = 8760) -> bool:
    if not path or not path.exists():
        return False
    edad_h = (time.time() - path.stat().st_mtime) / 3600
    return edad_h < horas_max  # 8760h = 1 año. Siempre usar si existe.


def resolver_paciente(cc: str, forzar_extraer: bool = False) -> Tuple[dict, str]:
    """Retorna (datos_dict, fuente: 'cache'|'extraido_al_vuelo'|'sin_datos')."""
    if not forzar_extraer:
        path = _json_path(cc)
        if _es_reciente(path):
            _log(f"CC {cc}: usando cache ({path.name})")
            with open(path, encoding="utf-8") as f:
                return json.load(f), "cache"

    if os.getenv("FASE_A_ENABLED", "false").lower() != "true":
        _log(f"CC {cc}: Fase A desactivada, sin datos verificados")
        return {"cc": cc, "_vacio": True, "razon": "FASE_A_ENABLED=false"}, "sin_datos"

    _log(f"CC {cc}: extrayendo al vuelo con Playwright")
    try:
        from backend.playwright_real.orquestador import extraer_paciente_completo
        datos = asyncio.run(extraer_paciente_completo(cc, guardar=True))
        return datos, "extraido_al_vuelo"
    except Exception as e:
        _log(f"CC {cc}: error en extracción - {e}")
        return {"cc": cc, "_vacio": True, "error": str(e)}, "sin_datos"


def ejecutar(paciente_cc: str, forzar_extraer: bool = False) -> dict:
    """Punto de entrada para workflow_runner."""
    datos, fuente = resolver_paciente(paciente_cc, forzar_extraer)
    return {"datos_portales": datos, "fuente": fuente}
