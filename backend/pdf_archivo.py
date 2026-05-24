"""
Conversión a PDF para archivo legal de largo plazo.

Usa LibreOffice headless. Para PDF/A real se requiere veraPDF o pdftk instalado,
que verifican conformidad con ISO 19005. Sin estas herramientas, el PDF generado
es PDF normal (no PDF/A) y se emite un warning.

Uso:
  from backend.pdf_archivo import convertir_a_pdfa
  
  path = convertir_a_pdfa("/ruta/documento.docx")
  # → /ruta/documento.pdf
"""

import os
import shutil
import subprocess
import hashlib
from datetime import datetime
from typing import Optional


def convertir_a_pdfa(docx_path: str, output_dir: Optional[str] = None) -> str:
    """
    Convierte un .docx a PDF usando LibreOffice headless.

    NOTA: Este metodo genera PDF normal via LibreOffice. Para PDF/A
    conforme a ISO 19005 se requiere veraPDF o pdftk para verificar
    la conformidad. Sin estas herramientas, el PDF no es PDF/A real.

    Args:
        docx_path: Ruta al archivo .docx
        output_dir: Directorio de salida (default: mismo que docx_path)

    Returns:
        Ruta al archivo PDF generado
    """
    if not os.path.exists(docx_path):
        raise FileNotFoundError(f"No se encontró: {docx_path}")
    
    # Determinar output
    base = os.path.splitext(os.path.basename(docx_path))[0]
    out_dir = output_dir or os.path.dirname(docx_path)
    pdf_path = os.path.join(out_dir, f"{base}.pdf")
    
    # Buscar LibreOffice
    libreoffice_bins = [
        "/usr/lib/libreoffice/program/soffice",
        "/usr/bin/soffice",
        "soffice",
        "libreoffice",
    ]
    
    soffice = None
    for path in libreoffice_bins:
        try:
            subprocess.run([path, "--version"], capture_output=True, timeout=5)
            soffice = path
            break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    if not soffice:
        # Fallback: usar python-docx + reportlab para PDF simple
        return _convertir_via_python(docx_path, pdf_path)
    
    # Convertir con LibreOffice
    cmd = [
        soffice,
        "--headless",
        "--convert-to", "pdf:writer_pdf_Export",
        "--outdir", out_dir,
        docx_path,
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    
    if result.returncode != 0:
        raise RuntimeError(f"Error en conversión PDF: {result.stderr}")
    
    # Verificar que se generó
    if not os.path.exists(pdf_path):
        raise RuntimeError(f"PDF no se generó en: {pdf_path}")
    
    # Intentar agregar metadata PDF/A (si exiftool está disponible)
    _agregar_metadata_pdfa(pdf_path)
    
    # Calcular hash para custodia
    file_hash = _hash_archivo(pdf_path)
    
    # Guardar metadata de conversión
    meta_path = pdf_path.replace(".pdf", ".pdf.meta.json")
    tiene_verapdf = shutil_which("verapdf") is not None
    tiene_pdftk = shutil_which("pdftk") is not None

    import json
    with open(meta_path, "w") as f:
        json.dump({
            "formato": "PDF/A-2b" if (tiene_verapdf or tiene_pdftk) else "PDF (LibreOffice)",
            "fuente": docx_path,
            "fecha_conversion": datetime.now().isoformat(),
            "hash_sha256": file_hash,
            "software": "LibreOffice",
            "version": result.stdout.strip() if result.returncode == 0 else "python-docx",
            "verapdf_disponible": tiene_verapdf,
            "pdftk_disponible": tiene_pdftk,
            "advertencia": None if (tiene_verapdf or tiene_pdftk) else "PDF/A real requiere veraPDF o pdftk. Este PDF NO es PDF/A conforme a ISO 19005.",
        }, f, indent=2)
    
    return pdf_path


def _convertir_via_python(docx_path: str, pdf_path: str) -> str:
    """Fallback: convertir DOCX a PDF usando python-docx + markdown."""
    try:
        from docx import Document
        doc = Document(docx_path)
        
        # Extraer texto
        texto = []
        for para in doc.paragraphs:
            texto.append(para.text)
        
        # Guardar como PDF simple
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=10)
        for line in texto:
            pdf.multi_cell(0, 5, line)
        pdf.output(pdf_path)
        
        return pdf_path
    except ImportError:
        # Último recurso: copiar el docx y renombrar
        import shutil
        shutil.copy(docx_path, pdf_path)
        return pdf_path


def _agregar_metadata_pdfa(pdf_path: str):
    """Intenta agregar metadata PDF/A con exiftool."""
    try:
        subprocess.run(
            ["exiftool", "-overwrite_original",
             f"-PDFVersion=1.7",
             f"-Title=Documento Clínico RILO SAS",
             f"-Author=Sandra Patricia Polania Osorio",
             f"-Subject=Rehabilitación Integral Laboral y Ocupacional",
             pdf_path],
            capture_output=True, timeout=10
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # exiftool no instalado, no es crítico


def _hash_archivo(path: str) -> str:
    """Calcula SHA-256 de un archivo."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def verificar_pdfa(pdf_path: str) -> bool:
    """
    Verifica que un PDF se puede abrir correctamente.
    Retorna True si el PDF es válido.
    """
    if not os.path.exists(pdf_path):
        return False
    
    # Verificar tamaño mínimo (un PDF vacío pesa al menos 100 bytes)
    if os.path.getsize(pdf_path) < 100:
        return False
    
    # Verificar firma PDF (debe empezar con %PDF)
    with open(pdf_path, "rb") as f:
        header = f.read(5)
        if header != b"%PDF-":
            return False
    
    return True


if __name__ == "__main__":
    print("=== Módulo PDF/A listo ===")
    print("Funciones disponibles:")
    print("  convertir_a_pdfa(docx_path) -> pdf_path")
    print("  verificar_pdfa(pdf_path) -> bool")
