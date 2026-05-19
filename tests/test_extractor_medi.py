"""Tests para extractor real Medifolios."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.live
@pytest.mark.asyncio
async def test_extraer_paciente_sandra():
    """CC 55162801 = Sandra. Sus datos siempre están en Medifolios."""
    from backend.playwright_real.medifolios import get_paciente_completo
    from backend.playwright_real.session import abrir_contexto

    async with abrir_contexto(portal="medifolios") as (_, _, page):
        datos = await get_paciente_completo(page, cc="55162801")

    assert isinstance(datos, dict)
    assert "nombre" in datos or "nombre1" in datos
    nombre = datos.get("nombre") or f"{datos.get('nombre1','')} {datos.get('apellido1','')}"
    assert "SANDRA" in nombre.upper()
