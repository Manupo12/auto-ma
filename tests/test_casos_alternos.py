"""Tests para casos alternos del workflow."""
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_workflow_continua_sin_portales_si_falla(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("FASE_A_ENABLED", "true")

    with patch("backend.playwright_real.orquestador.extraer_paciente_completo", new_callable=AsyncMock) as mock_ex:
        mock_ex.side_effect = RuntimeError("Portal caído")
        from backend.workflow_steps.resolver_paciente import resolver_paciente
        datos, fuente = resolver_paciente("9999")

    assert fuente == "sin_datos"
    assert datos["_vacio"] is True


def test_audio_baja_calidad_marca_warning(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    fake_audio = tmp_path / "fake.m4a"
    fake_audio.write_bytes(b"\x00" * 100)

    with patch("backend.flujo_audio.transcribir_audio") as mock_t, \
         patch("backend.workflow_steps.transcribir._calcular_duracion_s") as mock_dur:
        mock_dur.return_value = 600.0
        mock_t.return_value = {"texto": "blabla", "segmentos": [], "confianza": 0.4, "duracion": 600.0}
        from backend.workflow_steps.transcribir import transcribir_audio_largo
        resultado = transcribir_audio_largo(str(fake_audio), "123")

    assert resultado["warnings"]
    assert "Confianza baja" in resultado["warnings"][0]
