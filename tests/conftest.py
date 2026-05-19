"""Fixtures comunes para tests de Fase A."""
import os
import sys
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
import pytest

# Asegurar que backend sea importable
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@pytest.fixture
def tmp_storage(tmp_path):
    """Crea un storage/ temporal para tests."""
    storage = tmp_path / "storage"
    for sub in ["docs", "data", "audio", "playwright_sessions", "screenshots"]:
        (storage / sub).mkdir(parents=True, exist_ok=True)
    return storage


@pytest.fixture
def mock_llm_response():
    """Mock para requests.post a OpenCode Go."""
    def _mock(content="Datos extraídos correctamente", reasoning="", tokens=500):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "choices": [{
                "message": {"content": content, "reasoning_content": reasoning},
                "finish_reason": "stop",
            }],
            "usage": {"total_tokens": tokens},
        }
        return resp
    return _mock


@pytest.fixture
def datos_paciente_juan():
    """JSON de paciente de prueba (Juan Carlos)."""
    return {
        "paciente": {
            "documento": "1193143688",
            "nombre": "JUAN CARLOS DURAN NARVAEZ",
            "edad": "45",
            "telefono": "3001234567",
        },
        "siniestro": {"id_siniestro": "503463870", "fecha_evento": "02/03/2026"},
        "empresa": {"nombre": "ACME S.A.S."},
        "estado_caso": "SEGUIMIENTO",
    }


# Marcadores para tests live (que tocan portales reales)
def pytest_collection_modifyitems(config, items):
    skip_live = pytest.mark.skip(reason="needs --live flag")
    if config.getoption("--live", default=False):
        return
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


def pytest_addoption(parser):
    parser.addoption(
        "--live", action="store_true", default=False,
        help="Ejecutar tests live contra portales reales",
    )
