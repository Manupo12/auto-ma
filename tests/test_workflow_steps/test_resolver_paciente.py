"""Tests para resolver_paciente.py."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_resolver_usa_json_existente(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    json_path = data_dir / "1193143688-completo.json"
    json_path.write_text(json.dumps({"cc": "1193143688", "_meta": {}}), encoding="utf-8")

    from backend.workflow_steps.resolver_paciente import resolver_paciente
    datos, fuente = resolver_paciente("1193143688", forzar_extraer=False)
    assert datos["cc"] == "1193143688"
    assert fuente == "cache"


def test_resolver_dispara_extraccion_si_no_existe(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("FASE_A_ENABLED", "true")

    with patch("backend.playwright_real.orquestador.extraer_paciente_completo", new_callable=AsyncMock) as mock_extraer:
        mock_extraer.return_value = {"cc": "1193143688", "_meta": {"extraido_en": "now"}}
        from backend.workflow_steps.resolver_paciente import resolver_paciente
        datos, fuente = resolver_paciente("1193143688")

    assert mock_extraer.called
    assert fuente == "extraido_al_vuelo"


def test_resolver_devuelve_vacio_si_playwright_falla_sin_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    with patch("backend.playwright_real.orquestador.extraer_paciente_completo", new_callable=AsyncMock) as mock_extraer:
        mock_extraer.side_effect = Exception("Playwright failed")
        from backend.workflow_steps.resolver_paciente import resolver_paciente
        datos, fuente = resolver_paciente("9999")
    assert datos.get("_vacio")
    assert fuente == "sin_datos"
