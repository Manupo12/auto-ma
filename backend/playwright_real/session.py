"""
Manejo de sesion Playwright con storage_state persistente y re-login automatico.

Cada portal tiene un archivo de state en PLAYWRIGHT_SESSIONS_DIR/{portal}.json.
El state contiene cookies + localStorage. Vive ~15 min en ambos portales.

Uso:
    async with abrir_contexto(portal="medifolios") as (browser, ctx, page):
        # ya estas logueado (re-auto si hace falta)
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
TIMEOUT_MS = int(os.getenv("PLAYWRIGHT_TIMEOUT_MS", "60000"))


def _log(msg: str):
    import sys
    from datetime import datetime
    print(f"[PWREAL {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _state_path(portal: str) -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR / f"{portal}.json"


def _build_browser_context():
    """Crea browser y context con anti-deteccion para evitar captchas."""
    stealth_js = """() => {
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    }"""
    return {
        "headless": not DEBUG,
        "args": ["--disable-blink-features=AutomationControlled"],
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "init_script": stealth_js,
    }


async def _login_medifolios(page: Page):
    """Hace login en Medifolios."""
    await page.goto(S.MEDI_URL, timeout=TIMEOUT_MS)
    await page.wait_for_timeout(3000)
    await page.fill(S.MEDI_LOGIN["usuario_input"], os.getenv("MEDIFOLIOS_USER", ""))
    await page.fill(S.MEDI_LOGIN["password_input"], os.getenv("MEDIFOLIOS_PASSWORD", ""))
    await page.press(S.MEDI_LOGIN["password_input"], "Enter")
    # Cerrar popup "Cambia tu contrasena"
    try:
        await page.wait_for_selector(S.MEDI_LOGIN["popup_cambia_password_close"], timeout=5000)
        await page.click(S.MEDI_LOGIN["popup_cambia_password_close"])
    except Exception:
        pass
    await page.wait_for_timeout(3000)
    _log("MEDI: login OK")


async def _login_positiva(page: Page):
    """Hace login en ARL Positiva via CAS."""
    await page.goto(S.POS_URL, timeout=TIMEOUT_MS)
    await page.wait_for_timeout(3000)
    await page.fill(S.POS_LOGIN["usuario_input"], os.getenv("POSITIVA_USER", ""))
    await page.fill(S.POS_LOGIN["password_input"], os.getenv("POSITIVA_PASSWORD", ""))
    await page.click(S.POS_LOGIN["submit_button"])
    await page.wait_for_timeout(10000)

    body = await page.text_content("body") or ""
    if "Ingresar a Cuida" in body:
        links = await page.evaluate("""() =>
            Array.from(document.querySelectorAll('a'))
                .filter(a => a.textContent.includes('Ingresar a Cuida'))
                .map(a => a.href)
        """)
        if links:
            await page.goto(links[0], timeout=TIMEOUT_MS)
            await page.wait_for_timeout(5000)
    _log("POS: login OK")


async def _verificar_sesion(page: Page, portal: str) -> bool:
    """Heartbeat post-login: la sesion sigue viva?"""
    if portal == "medifolios":
        try:
            body = await page.text_content("body") or ""
            return "Menu Principal" in body or "Bienvenido" in body
        except Exception:
            return False
    else:
        try:
            body = await page.text_content("body") or ""
            return "MARIA GREIDY" in body or "Proveedor" in body
        except Exception:
            return False


async def login_y_guardar(portal: str) -> Path:
    """Hace login limpio y guarda storage_state. Retorna path al state."""
    async with async_playwright() as p:
        cfg = _build_browser_context()
        browser = await p.chromium.launch(headless=cfg["headless"], args=cfg["args"])
        ctx = await browser.new_context(user_agent=cfg["user_agent"])
        page = await ctx.new_page()
        await page.add_init_script(cfg["init_script"])
        try:
            if portal == "medifolios":
                await _login_medifolios(page)
            elif portal == "positiva":
                await _login_positiva(page)
            else:
                raise ValueError(f"portal desconocido: {portal}")

            state_path = _state_path(portal)
            # Backup antes de sobreescribir
            if state_path.exists():
                try:
                    import shutil
                    shutil.copy2(str(state_path), str(state_path) + ".bak")
                except Exception:
                    pass
            await ctx.storage_state(path=str(state_path))
            _log(f"{portal.upper()}: storage_state guardado en {state_path}")
            return state_path
        finally:
            await browser.close()


@asynccontextmanager
async def abrir_contexto(portal: str) -> Tuple[Browser, BrowserContext, Page]:
    """
    Context manager: devuelve (browser, context, page) listo para usar.
    Auto-loguea si el state no existe o expiro.
    """
    state_path = _state_path(portal)

    async with async_playwright() as p:
        cfg = _build_browser_context()
        browser = await p.chromium.launch(headless=cfg["headless"], args=cfg["args"])

        kwargs: dict = {"user_agent": cfg["user_agent"]}
        if state_path.exists():
            kwargs["storage_state"] = str(state_path)
        ctx = await browser.new_context(**kwargs)
        page = await ctx.new_page()
        await page.add_init_script(cfg["init_script"])

        if portal == "medifolios":
            home_url = S.MEDI_URL
        else:
            home_url = "https://positivacuida.positiva.gov.co/web/systemSelection/arp"

        await page.goto(home_url, timeout=TIMEOUT_MS)
        await page.wait_for_timeout(3000)

        if not await _verificar_sesion(page, portal):
            _log(f"{portal.upper()}: sesion expirada o inexistente — re-login")
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
