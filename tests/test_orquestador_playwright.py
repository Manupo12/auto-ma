"""Tests para orquestador de fuentes (Medifolios + Positiva)."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.live
@pytest.mark.asyncio
async def test_orquestador_extrae_ambos_portales(tmp_storage, monkeypatch):
    """Extrae de Medifolios y Positiva para un CC conocido."""
    monkeypatch.setenv("STORAGE_DIR", str(tmp_storage))
    from backend.playwright_real.orquestador import extraer_paciente_completo

    datos = await extraer_paciente_completo("1193143688", guardar=True)

    assert isinstance(datos, dict)
    assert datos["cc"] == "1193143688"
    assert "medifolios" in datos
    assert "positiva" in datos
    assert "_meta" in datos
    assert not datos["_meta"].get("parcial", True), \
        f"Ambos portales debieron responder. Meta: {datos['_meta']}"


def test_detectar_discrepancias():
    """Siniestros diferentes deben reportarse como discrepancia."""
    from backend.playwright_real.orquestador import _detectar_discrepancias

    medi = {"siniestro_medi": "503463870"}
    pos = {"siniestros": [{"id": "503476658"}]}

    disc = _detectar_discrepancias(medi, pos)
    assert len(disc) == 1
    assert disc[0]["campo"] == "siniestro"
    assert disc[0]["medifolios"] == "503463870"
    assert disc[0]["positiva"] == "503476658"
    assert "prevalecer" in disc[0]["resolucion"].lower()


def test_sin_discrepancias():
    """Siniestros iguales no generan conflicto."""
    from backend.playwright_real.orquestador import _detectar_discrepancias

    medi = {"siniestro_medi": "503463870"}
    pos = {"siniestros": [{"id": "503463870"}]}

    disc = _detectar_discrepancias(medi, pos)
    assert len(disc) == 0
