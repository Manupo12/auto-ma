"""
Manejo de sesión Playwright con storage_state persistente y re-login automático.

Cada portal tiene un archivo de state en PLAYWRIGHT_SESSIONS_DIR/{portal}.json.
El state contiene cookies + localStorage. Vive ~15 min en ambos portales.

Uso:
    async with abrir_contexto(portal="medifolios") as (browser, ctx, page):
        # ya estás logueado (re-auto si hace falta)
        await page.goto(...)
"""
import os
import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Tuple

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from backend.playwright_real import selectores as S


SESSIONS_DIR = Path(os.getenv("PLAYWRIGHT_SESSIONS_DIR", "./storage/playwright_sessions"))
DEBUG = os.getenv("PLAYWRIGHT_DEBUG", "false").lower() == "true"
TIMEOUT_MS = int(os.getenv("PLAYWRIGHT_TIMEOUT_MS", "30000"))


def _log(msg: str):
    import sys
    from datetime import datetime
    print(f"[PWREAL {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _state_path(portal: str) -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR / f"{portal}.json"


async def _login_medifolios(page: Page):
    """Hace login en Medifolios. Asume page acaba de cargar MEDI_URL."""
    await page.goto(S.MEDI_URL, timeout=TIMEOUT_MS)
    await page.fill(S.MEDI_LOGIN["usuario_input"], os.getenv("MEDIFOLIOS_USER", ""))
    await page.fill(S.MEDI_LOGIN["password_input"], os.getenv("MEDIFOLIOS_PASSWORD", ""))
    await page.click(S.MEDI_LOGIN["submit_button"])
    # Cerrar popup "Cambia tu contraseña"
    try:
        await page.wait_for_selector(S.MEDI_LOGIN["popup_cambia_password_close"], timeout=5000)
        await page.click(S.MEDI_LOGIN["popup_cambia_password_close"])
    except Exception:
        pass
    # Verificar login OK
    await page.wait_for_selector(S.MEDI_LOGIN["post_login_heartbeat"], timeout=TIMEOUT_MS)
    _log("MEDI: login OK")


async def _login_positiva(page: Page):
    """Hace login en ARL Positiva."""
    await page.goto(S.POS_URL, timeout=TIMEOUT_MS)
    await page.fill(S.POS_LOGIN["usuario_input"], os.getenv("POSITIVA_USER", ""))
    await page.fill(S.POS_LOGIN["password_input"], os.getenv("POSITIVA_PASSWORD", ""))
    await page.click(S.POS_LOGIN["submit_button"])
    await page.wait_for_selector(S.POS_LOGIN["post_login_heartbeat"], timeout=TIMEOUT_MS)
    _log("POS: login OK")


async def _verificar_sesion(page: Page, portal: str) -> bool:
    """Heartbeat post-login: ¿la sesión sigue viva?"""
    selector = S.MEDI_LOGIN["post_login_heartbeat"] if portal == "medifolios" else S.POS_LOGIN["post_login_heartbeat"]
    try:
        count = await page.locator(selector).count()
        return count > 0
    except Exception:
        return False


async def login_y_guardar(portal: str) -> Path:
    """Hace login limpio y guarda storage_state. Retorna path al state."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not DEBUG)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        try:
            if portal == "medifolios":
                await _login_medifolios(page)
            elif portal == "positiva":
                await _login_positiva(page)
            else:
                raise ValueError(f"portal desconocido: {portal}")

            state_path = _state_path(portal)
            await ctx.storage_state(path=str(state_path))
            _log(f"{portal.upper()}: storage_state guardado en {state_path}")
            return state_path
        finally:
            await browser.close()


@asynccontextmanager
async def abrir_contexto(portal: str) -> Tuple[Browser, BrowserContext, Page]:
    """
    Context manager: devuelve (browser, context, page) listo para usar.
    Auto-loguea si el state no existe o expiró.
    """
    state_path = _state_path(portal)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not DEBUG)

        kwargs = {}
        if state_path.exists():
            kwargs["storage_state"] = str(state_path)
        ctx = await browser.new_context(**kwargs)
        page = await ctx.new_page()

        home_url = S.MEDI_URL if portal == "medifolios" else S.POS_URL.split("?")[0].replace("/cas/login", "/web/")
        await page.goto(home_url, timeout=TIMEOUT_MS)

        if not await _verificar_sesion(page, portal):
            _log(f"{portal.upper()}: sesión expirada o inexistente — re-login")
            if portal == "medifolios":
                await _login_medifolios(page)
            else:
                await _login_positiva(page)
            await ctx.storage_state(path=str(state_path))

        try:
            yield browser, ctx, page
        finally:
            try:
                await ctx.storage_state(path=str(state_path))
            except Exception:
                pass
            await browser.close()
