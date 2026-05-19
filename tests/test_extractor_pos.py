"""Tests para extractor real ARL Positiva."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.live
@pytest.mark.asyncio
async def test_extraer_paciente_juan():
    """CC 1193143688 = Juan Carlos Duran. Tiene siniestros en Positiva."""
    from backend.playwright_real.positiva import get_paciente_completo
    from backend.playwright_real.session import abrir_contexto

    async with abrir_contexto(portal="positiva") as (_, _, page):
        datos = await get_paciente_completo(page, cc="1193143688")

    assert isinstance(datos, dict)
    assert datos.get("siniestros", []) or datos.get("siniestro_principal"), \
        f"No se extrajo siniestro. Datos: {datos}"
