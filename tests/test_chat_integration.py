"""Tests de integración del chat_handler con subprocess workers."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_chat_handler_procesar_via_workers_invoca_subprocess(tmp_path, monkeypatch):
    """_procesar_via_workers debe usar subprocess.run, no llamadas en-proceso."""
    monkeypatch.setenv("FASE_A_ENABLED", "true")
    from backend import chat_handler

    from docx import Document
    archivos = []
    for i in range(3):
        p = tmp_path / f"test_{i}.docx"
        doc = Document()
        doc.add_paragraph(f"Documento {i}")
        doc.save(str(p))
        archivos.append((p, 1, "01/01/2026"))

    with patch("backend.chat_handler.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"ok": true, "datos_raw": "PACIENTE: TEST"}',
            stderr="",
        )
        resultado = chat_handler._procesar_via_workers(archivos, cc="1193143688")

    assert mock_run.called, "subprocess.run no fue invocado"
    assert mock_run.call_count == 3, f"Esperado 3 subprocess (1 por archivo), invocado {mock_run.call_count}"
    args = mock_run.call_args_list[0][0][0]
    assert "lote_worker" in " ".join(args)
    assert isinstance(resultado, str)
    assert "PACIENTE" in resultado
