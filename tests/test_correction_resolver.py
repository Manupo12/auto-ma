"""Tests para correction_resolver."""
import sys
from pathlib import Path
from unittest.mock import patch
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_extrae_correccion_simple():
    from backend.correction_resolver import interpretar_correccion

    with patch("backend.correction_resolver._llamar_llm_clasificador") as mock_llm:
        mock_llm.return_value = {
            "campo": "siniestro.id_siniestro",
            "valor_nuevo": "503476658",
            "valor_anterior": "503463870",
            "confianza": 0.9,
        }
        r = interpretar_correccion("el siniestro no es 503463870 es 503476658", paciente_cc="1193143688")

    assert r["campo"] == "siniestro.id_siniestro"
    assert r["valor_nuevo"] == "503476658"


def test_extrae_correccion_campo_libre():
    from backend.correction_resolver import interpretar_correccion
    with patch("backend.correction_resolver._llamar_llm_clasificador") as mock_llm:
        mock_llm.return_value = {
            "campo": "metodologia",
            "valor_nuevo": "Observación directa de la tarea por 2 horas",
            "valor_anterior": None,
            "confianza": 0.7,
        }
        r = interpretar_correccion("la metodología es observación directa por 2 horas", paciente_cc="1193143688")
    assert r["campo"] == "metodologia"
