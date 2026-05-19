"""Tests para sintetizar_maestro.py."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_sintesis_compone_contexto_completo():
    from backend.workflow_steps.sintetizar_maestro import _componer_contexto

    transcripcion = {"texto": "Paciente dice que le duele.", "duracion": 60}
    datos_portales = {"cc": "1193143688", "medifolios": {"nombre1": "JUAN"}}
    notas_crudas = [{"nombre": "n.txt", "contenido": "Dolor lumbar"}]
    formatos_subidos = []

    ctx = _componer_contexto(transcripcion, datos_portales, notas_crudas, formatos_subidos, paciente_cc="1193143688")
    assert "TRANSCRIPCIÓN DEL AUDIO" in ctx
    assert "DATOS VERIFICADOS" in ctx
    assert "NOTAS CRUDAS" in ctx
    assert "Paciente dice que le duele" in ctx
    assert "JUAN" in ctx


def test_sintesis_llama_subprocess_lote_worker():
    from backend.workflow_steps.sintetizar_maestro import sintetizar

    with patch("backend.workflow_steps.sintetizar_maestro.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"ok": true, "respuesta": "Datos sintetizados", "tokens": {"total": 1000}}',
            stderr="",
        )
        resultado = sintetizar(
            transcripcion={"texto": "abc"},
            datos_portales={"cc": "123"},
            notas_crudas=[],
            formatos_subidos=[],
            paciente_cc="123",
        )

    assert mock_run.called
    assert "lote_worker" in " ".join(mock_run.call_args[0][0])
    assert "sintetizar" in " ".join(mock_run.call_args[0][0])
    assert resultado["respuesta_completa"] == "Datos sintetizados"


def test_chunking_si_contexto_grande():
    from backend.workflow_steps.sintetizar_maestro import _resumir_si_largo

    texto_largo = "Lorem ipsum " * 5000
    resumido = _resumir_si_largo(texto_largo, max_chars=10000)
    assert len(resumido) <= 10500
