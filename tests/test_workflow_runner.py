"""Tests para workflow_runner.py — orquesta los 9 pasos."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_runner_ejecuta_los_9_pasos_en_orden(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("WORKFLOW_DB_PATH", str(tmp_path / "wf.db"))
    monkeypatch.setenv("TOMY_COMPLETO_ENABLED", "true")

    with patch("backend.workflow_steps.transcribir.ejecutar") as m1, \
         patch("backend.workflow_steps.resolver_paciente.ejecutar") as m2, \
         patch("backend.workflow_steps.leer_notas_crudas.ejecutar") as m3, \
         patch("backend.workflow_steps.leer_formatos_subidos.ejecutar") as m4, \
         patch("backend.workflow_steps.sintetizar_maestro.ejecutar") as m5, \
         patch("backend.workflow_steps.generar_formatos.ejecutar") as m6, \
         patch("backend.workflow_steps.qa_formatos.ejecutar") as m7, \
         patch("backend.workflow_steps.convertir_pdf.ejecutar") as m8, \
         patch("backend.workflow_steps.notificar_listo.ejecutar") as m9:

        m1.return_value = {"texto": "...", "warnings": []}
        m2.return_value = {"datos_portales": {"medifolios": {"nombre1": "JUAN"}}, "fuente": "cache"}
        m3.return_value = {"notas_crudas": [], "total": 0}
        m4.return_value = {"formatos_subidos": [], "total": 0}
        m5.return_value = {"ok": True, "datos_clinicos": {"paciente": {"nombre": "JUAN", "documento": "1193143688"}, "estado_caso": "SEGUIMIENTO"}}
        m6.return_value = {"ok": True, "formatos_generados": [{"formato": "analisis", "archivo": "/tmp/a.docx"}], "errores": []}
        m7.return_value = {"ok": True, "resultados": [{"formato": "analisis", "qa_ok": True}], "exitosos": 1}
        m8.return_value = {"ok": True, "pdfs": [{"formato": "analisis", "pdf": "/tmp/a.pdf"}]}
        m9.return_value = {"ok": True, "telegram_enviado": True}

        from backend.workflow_runner import ejecutar_workflow
        resultado = ejecutar_workflow(audio_path="/tmp/a.m4a", paciente_cc="1193143688")

    for m in [m1, m2, m3, m4, m5, m6, m7, m8, m9]:
        assert m.called, f"step no fue invocado: {m}"

    assert resultado["estado"] == "listo"
    assert resultado["task_id"]


def test_runner_marca_error_si_step_falla(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("WORKFLOW_DB_PATH", str(tmp_path / "wf.db"))
    monkeypatch.setenv("TOMY_COMPLETO_ENABLED", "true")

    with patch("backend.workflow_steps.transcribir.ejecutar") as m1:
        m1.side_effect = RuntimeError("Deepgram timeout")
        from backend.workflow_runner import ejecutar_workflow
        resultado = ejecutar_workflow(audio_path="/tmp/a.m4a", paciente_cc="1193143688")

    assert "error" in resultado["estado"]
    assert "Deepgram" in resultado.get("error", "")
