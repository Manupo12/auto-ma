"""
Paso 2: Resolver datos del paciente.

Logica:
- Paciente NUEVO (sin cache) -> Playwright OBLIGATORIO. Si falla, error.
- Paciente EXISTENTE <24h -> usar cache, no abrir portales.
- Paciente EXISTENTE >24h -> Playwright para refrescar. Si falla, usar cache viejo.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Tuple


def _log(msg: str):
    print(f"[RESOLVER {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _json_path(cc: str) -> Path:
    storage = Path(os.getenv("STORAGE_DIR", "./storage"))
    matches = sorted((storage / "data").glob(f"*{cc}*completo.json"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _edad_horas(path: Path) -> float:
    return (time.time() - path.stat().st_mtime) / 3600 if path and path.exists() else 99999


def resolver_paciente(cc: str, forzar_extraer: bool = False) -> Tuple[dict, str]:
    path = _json_path(cc)
    edad = _edad_horas(path)
    es_nuevo = not path or not path.exists()

    # Caso 1: Cache fresco (<24h) y no forzar -> usar cache
    if not es_nuevo and edad < 24 and not forzar_extraer:
        _log(f"CC ***{cc[-4:]}: cache fresco ({edad:.1f}h) -> usando {path.name}")
        with open(path, encoding="utf-8") as f:
            return json.load(f), "cache"

    # Caso 2: Extraer de portales con Playwright (OBLIGATORIO para nuevos)
    _log(f"CC ***{cc[-4:]}: {'paciente NUEVO -> Playwright OBLIGATORIO' if es_nuevo else f'cache viejo ({edad:.1f}h) -> refrescando con Playwright'}")
    try:
        from backend.playwright_real.orquestador import extraer_paciente_completo
        datos = asyncio.run(extraer_paciente_completo(cc, guardar=True))
        parcial = datos.get("_meta", {}).get("parcial", True)
        _log(f"CC ***{cc[-4:]}: Playwright {'parcial' if parcial else 'completo'}")
        return datos, "extraido_al_vuelo"
    except Exception as e:
        _log(f"CC ***{cc[-4:]}: Playwright error - {e}")

    # Caso 3: Playwright fallo, pero hay cache viejo -> emergencia
    if not es_nuevo and path.exists():
        _log(f"CC ***{cc[-4:]}: usando cache viejo como emergencia ({edad:.1f}h)")
        with open(path, encoding="utf-8") as f:
            return json.load(f), "cache_viejo"

    # Caso 4: Paciente nuevo, Playwright fallo, sin cache -> ERROR (detener workflow)
    _log(f"CC ***{cc[-4:]}: SIN DATOS - paciente nuevo sin acceso a portales")
    return {
        "cc": cc,
        "_vacio": True,
        "error": "Playwright no disponible para paciente nuevo. Intente de nuevo.",
    }, "sin_datos"


def ejecutar(paciente_cc: str, forzar_extraer: bool = False) -> dict:
    datos, fuente = resolver_paciente(paciente_cc, forzar_extraer)
    return {"datos_portales": datos, "fuente": fuente}
