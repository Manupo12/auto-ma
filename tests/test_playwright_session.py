"""Tests para playwright_real/session.py."""
import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.live
@pytest.mark.asyncio
async def test_login_medifolios_guarda_storage_state(tmp_path, monkeypatch):
    """Login real contra Medifolios + verificar que se crea storage_state."""
    monkeypatch.setenv("PLAYWRIGHT_SESSIONS_DIR", str(tmp_path))
    from backend.playwright_real.session import login_y_guardar

    state_path = await login_y_guardar(portal="medifolios")

    assert state_path.exists(), f"storage_state no fue creado: {state_path}"
    assert state_path.stat().st_size > 100, "storage_state demasiado pequeño"


@pytest.mark.live
@pytest.mark.asyncio
async def test_sesion_activa_reusa_state(tmp_path, monkeypatch):
    """Si existe storage_state válido, no re-loguea."""
    monkeypatch.setenv("PLAYWRIGHT_SESSIONS_DIR", str(tmp_path))
    from backend.playwright_real.session import login_y_guardar, abrir_contexto

    await login_y_guardar(portal="medifolios")

    async with abrir_contexto(portal="medifolios") as (browser, ctx, page):
        from backend.playwright_real.selectores import MEDI_LOGIN
        heartbeat = await page.locator(MEDI_LOGIN["post_login_heartbeat"]).count()
        assert heartbeat > 0, "heartbeat post-login falló — re-login esperado"
