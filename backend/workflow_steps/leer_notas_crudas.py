"""
Paso 3: Leer notas crudas que Sandra escribió en su workspace.

Busca archivos .txt, .md, .docx que contengan la CC del paciente en el
nombre o en su contenido (primeros 500 chars). Devuelve hasta 5 archivos
con contenido (~2000 chars c/u).
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict


def _log(msg: str):
    print(f"[NOTAS {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _leer_texto(path: Path, max_chars: int = 2000) -> str:
    """Lee primeros N chars de .txt/.md/.docx."""
    try:
        if path.suffix.lower() in (".txt", ".md"):
            return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
        if path.suffix.lower() == ".docx":
            from docx import Document
            doc = Document(str(path))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            return text[:max_chars]
    except Exception as e:
        _log(f"Error leyendo {path.name}: {e}")
    return ""


def leer_notas_crudas(cc: str, max_archivos: int = 5) -> List[Dict]:
    """Busca archivos del workspace con el CC en nombre o contenido."""
    workspace = Path(os.getenv("WORKSPACE_DIR", str(Path.home() / "rilo-workspace")))
    if not workspace.exists():
        _log(f"Workspace no existe: {workspace}")
        return []

    candidatos = []
    extensiones = (".txt", ".md", ".docx")
    try:
        for path in workspace.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in extensiones:
                continue
            if path.stat().st_size > 5_000_000:
                continue

            if cc in path.name:
                contenido = _leer_texto(path)
                if contenido:
                    candidatos.append({"nombre": path.name, "ruta": str(path), "contenido": contenido})
                    continue

            contenido = _leer_texto(path, max_chars=500)
            if cc in contenido:
                contenido_completo = _leer_texto(path)
                candidatos.append({"nombre": path.name, "ruta": str(path), "contenido": contenido_completo})
    except Exception as e:
        _log(f"Error escaneando: {e}")

    candidatos.sort(key=lambda d: Path(d["ruta"]).stat().st_mtime, reverse=True)
    return candidatos[:max_archivos]


def ejecutar(paciente_cc: str) -> dict:
    notas = leer_notas_crudas(paciente_cc)
    return {"notas_crudas": notas, "total": len(notas)}
