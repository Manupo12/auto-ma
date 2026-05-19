"""Tests para qa, pdf, notificar (steps finales del workflow)."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_qa_devuelve_warnings_pero_no_falla(tmp_path):
    from backend.workflow_steps.qa_formatos import qa_todos
    fake_doc = tmp_path / "fake.docx"
    from docx import Document
    Document().save(str(fake_doc))

    resultado = qa_todos([{"formato": "analisis", "archivo": str(fake_doc)}])
    assert "resultados" in resultado
    assert len(resultado["resultados"]) == 1


def test_convertir_pdf_skipea_si_libreoffice_falta(tmp_path, monkeypatch):
    from backend.workflow_steps.convertir_pdf import convertir_todos
    monkeypatch.setattr("backend.workflow_steps.convertir_pdf._tiene_libreoffice", lambda: False)

    formatos = [{"formato": "x", "archivo": str(tmp_path / "fake.docx")}]
    resultado = convertir_todos(formatos)
    assert not resultado["ok"]
    assert "libreoffice" in resultado["error"].lower()


def test_notificar_listo_envia_telegram(monkeypatch):
    from backend.workflow_steps.notificar_listo import notificar

    with patch("backend.notificador.enviar_telegram") as mock_tel:
        mock_tel.return_value = True
        ok = notificar(task_id="abc", paciente_nombre="Juan", paciente_cc="123",
                       formatos_generados=[{"formato":"analisis"}], warnings=[], dashboard_url="http://localhost:3000")

    assert mock_tel.called
    mensaje = mock_tel.call_args[0][0]
    assert "Juan" in mensaje
    assert "1 formato" in mensaje or "formatos" in mensaje
    assert "http://localhost:3000" in mensaje
