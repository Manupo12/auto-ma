"""
Paso 7: QA 10 capas sobre cada DOCX generado.

Wrapper sobre skills/verificar-documento/scripts/qa_completo.py.
Si el script no existe o falla, devuelve warning (no bloquea).
"""
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List


def _log(msg: str):
    print(f"[QA {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _qa_script_path() -> Path:
    return Path(__file__).parent.parent.parent / "skills" / "verificar-documento" / "scripts" / "qa_completo.py"


def qa_uno(formato: dict) -> dict:
    archivo = formato.get("archivo")
    if not archivo or not Path(archivo).exists():
        return {**formato, "qa_ok": False, "qa_error": "archivo no existe"}
    qa_script = _qa_script_path()
    if not qa_script.exists():
        _log(f"qa_completo.py no encontrado, skip")
        return {**formato, "qa_ok": True, "qa_warnings": ["QA script no disponible"]}
    try:
        proc = subprocess.run(
            [sys.executable, str(qa_script), archivo],
            capture_output=True, text=True, timeout=60,
        )
        return {
            **formato,
            "qa_ok": proc.returncode == 0,
            "qa_output": proc.stdout[-500:],
            "qa_warnings": [l for l in proc.stdout.split("\n") if "WARN" in l.upper()][:5],
        }
    except Exception as e:
        return {**formato, "qa_ok": False, "qa_error": str(e)}


def qa_todos(formatos: List[dict]) -> Dict:
    resultados = [qa_uno(f) for f in formatos]
    return {
        "ok": True,
        "resultados": resultados,
        "total": len(formatos),
        "exitosos": sum(1 for r in resultados if r.get("qa_ok")),
        "con_warnings": sum(1 for r in resultados if r.get("qa_warnings")),
    }


def ejecutar(formatos_generados: List[dict]) -> dict:
    return qa_todos(formatos_generados)
