"""
Paso 8: Convertir cada DOCX aprobado por QA a PDF/A.

Usa LibreOffice en modo headless si está instalado.
Si no está, deja un warning pero no bloquea.
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List


def _log(msg: str):
    print(f"[PDF {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _tiene_libreoffice() -> bool:
    return shutil.which("libreoffice") is not None or shutil.which("soffice") is not None


def _convertir_uno(docx_path: str, output_dir: Path) -> str:
    bin_lo = shutil.which("libreoffice") or shutil.which("soffice")
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [bin_lo, "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), docx_path]
    subprocess.run(cmd, capture_output=True, check=True, timeout=120)
    pdf_name = Path(docx_path).stem + ".pdf"
    return str(output_dir / pdf_name)


def convertir_todos(formatos: List[dict]) -> Dict:
    if not _tiene_libreoffice():
        return {"ok": False, "error": "LibreOffice no instalado", "pdfs": []}

    pdfs = []
    errores = []
    output_dir = Path(os.getenv("STORAGE_DIR", "./storage")) / "pdfs"
    for f in formatos:
        if not f.get("qa_ok"):
            continue
        try:
            pdf = _convertir_uno(f["archivo"], output_dir)
            pdfs.append({**f, "pdf": pdf})
            _log(f"✅ PDF: {Path(pdf).name}")
        except Exception as e:
            _log(f"❌ {f.get('formato','?')}: {e}")
            errores.append({"formato": f.get("formato"), "error": str(e)})

    formatos_a_convertir = sum(1 for f in formatos if f.get("qa_ok"))
    if formatos_a_convertir > 0:
        ok = len(pdfs) >= formatos_a_convertir
    else:
        ok = True
    return {"ok": ok, "pdfs": pdfs, "errores": errores}


def ejecutar(qa_resultados: List[dict]) -> dict:
    return convertir_todos(qa_resultados)
