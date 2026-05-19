"""Tests para generar_formatos.py."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_genera_solo_formatos_aplicables_por_estado():
    from backend.workflow_steps.generar_formatos import _seleccionar_formatos
    formatos = _seleccionar_formatos("NUEVO")
    assert "analisis" in formatos
    assert "valoracion" in formatos
    assert "cierre" not in formatos

    formatos_cierre = _seleccionar_formatos("CIERRE")
    assert "cierre" in formatos_cierre


def test_genera_formatos_llama_a_doc_generator(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    datos = {
        "paciente": {"documento": "1193143688", "nombre": "JUAN DURAN"},
        "siniestro": {"id_siniestro": "503463870"},
        "empresa": {"nombre": "ACME"},
        "estado_caso": "SEGUIMIENTO",
    }
    from backend.workflow_steps.generar_formatos import generar_todos

    with patch("backend.workflow_steps.generar_formatos.generar_documento") as mock_gen:
        mock_gen.return_value = str(tmp_path / "fake.docx")
        resultado = generar_todos(datos, task_id="abc123")

    assert resultado["ok"]
    assert mock_gen.called
    assert resultado["formatos_generados"]
