"""Tests para aplicador_correccion."""
import json
import sys
from pathlib import Path
from unittest.mock import patch
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_aplica_correccion_simple(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    json_path = data_dir / "1193143688-completo.json"
    json_path.write_text(json.dumps({
        "cc": "1193143688",
        "siniestro": {"id_siniestro": "503463870"},
        "_meta": {"correcciones": []}
    }), encoding="utf-8")

    from backend.aplicador_correccion import aplicar_correccion
    correccion = {"campo": "siniestro.id_siniestro", "valor_nuevo": "503476658", "valor_anterior": "503463870"}

    with patch("backend.aplicador_correccion._regenerar_formatos_afectados") as mock_regen:
        mock_regen.return_value = {"regenerados": [], "errores": []}
        resultado = aplicar_correccion(paciente_cc="1193143688", correccion=correccion)

    assert resultado["ok"]
    nuevo = json.loads(json_path.read_text())
    assert nuevo["siniestro"]["id_siniestro"] == "503476658"
    assert len(nuevo["_meta"]["correcciones"]) == 1


def test_aplicar_correccion_campo_inexistente_crea_ruta(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    json_path = data_dir / "123-completo.json"
    json_path.write_text(json.dumps({"cc": "123"}), encoding="utf-8")

    from backend.aplicador_correccion import aplicar_correccion
    correccion = {"campo": "metodologia", "valor_nuevo": "Nueva metodología"}

    with patch("backend.aplicador_correccion._regenerar_formatos_afectados") as mock_regen:
        mock_regen.return_value = {"regenerados": [], "errores": []}
        resultado = aplicar_correccion(paciente_cc="123", correccion=correccion)

    assert resultado["ok"]
    nuevo = json.loads(json_path.read_text())
    assert nuevo["metodologia"] == "Nueva metodología"
