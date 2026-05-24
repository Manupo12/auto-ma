"""
Extractor real de datos del paciente desde Medifolios — actualizado Mayo 2026.

Fuentes:
  1. Form pacientes (SALUD_HOME/paciente): datos personales
  2. Agenda Citas (SALUD_GESTIONCITAS/agenda_cita): siniestro en observaciones
"""
import re
from typing import Dict
from playwright.async_api import Page

from backend.playwright_real import selectores as S


async def _navegar_a_pacientes(page: Page):
    """Navega a la pagina de Pacientes via URL directa."""
    await page.goto(S.MEDI_PACIENTES["url"], timeout=30000)
    await page.wait_for_timeout(4000)


async def _cargar_paciente_en_form(page: Page, cc: str) -> bool:
    """Llena CC y dispara busqueda del paciente."""
    try:
        await page.fill(S.MEDI_PACIENTES["numero_id_input"], cc)
    except Exception:
        return False

    await page.wait_for_timeout(1000)

    for b in await page.query_selector_all("button"):
        t = (await b.text_content() or "").strip().lower()
        if "buscar" in t:
            await b.click()
            break
    else:
        await page.press(S.MEDI_PACIENTES["numero_id_input"], "Enter")

    await page.wait_for_timeout(5000)

    nombre = await page.input_value(S.MEDI_PACIENTES["nombre1"], timeout=5000).catch(lambda: "")
    return bool(nombre)


async def _extraer_form_pacientes(page: Page) -> Dict:
    """Extrae campos del formulario de pacientes."""
    campos = {}
    field_ids = [
        "nombre1", "nombre2", "apellido1", "apellido2", "numero_id",
        "direccion", "telefono", "email", "fecha_nacimiento", "edad"
    ]
    for fid in field_ids:
        try:
            el = page.locator(f"#{fid}")
            val = await el.input_value(timeout=2000)
            if val and val.strip():
                campos[fid] = val.strip()
        except Exception:
            pass

    try:
        sexo = page.locator("select[name='sexo'], #sexo")
        val = await sexo.input_value(timeout=2000)
        if val:
            campos["sexo"] = val
    except Exception:
        pass

    return campos


async def _extraer_siniestro_de_agenda(page: Page, cc: str):
    """Navega a Agenda Citas y busca siniestro en observaciones. Retorna (siniestro, fuente)."""
    try:
        await page.goto(S.MEDI_AGENDA["url"], timeout=30000)
        await page.wait_for_timeout(5000)
    except Exception:
        return "", ""

    body = await page.text_content("body") or ""

    siniestro_match = re.search(
        r"[Nn][Oo]\.?\s*[Ss]iniestro[:\s]*(\d{8,12})", body
    )
    if siniestro_match:
        return siniestro_match.group(1), "agenda"

    siniestro_match = re.search(r"[Ss]iniestro[:\s]*(\d{8,12})", body)
    if siniestro_match:
        return siniestro_match.group(1), "agenda"

    try:
        cita_link = await page.query_selector(f"tr:has-text('{cc}') a, a:has-text('{cc}')")
        if cita_link:
            await cita_link.click()
            await page.wait_for_timeout(5000)
            obs_body = await page.text_content("body") or ""
            siniestro_match = re.search(r"[Ss]iniestro[:\s]*(\d{8,12})", obs_body)
            if siniestro_match:
                return siniestro_match.group(1), "historia"
    except Exception:
        pass

    return "", ""


async def get_paciente_completo(page: Page, cc: str) -> Dict:
    """
    Funcion principal. Extrae datos del paciente desde Medifolios.
    """
    datos = {"cc_buscado": cc, "fuente": "medifolios"}

    try:
        await _navegar_a_pacientes(page)
        cargado = await _cargar_paciente_en_form(page, cc)
        if cargado:
            form = await _extraer_form_pacientes(page)
            datos.update(form)
            partes = [datos.get(k, "") for k in ("nombre1", "nombre2", "apellido1", "apellido2") if datos.get(k)]
            if partes:
                datos["nombre"] = " ".join(partes)
        else:
            datos["error_form"] = "paciente no encontrado o no cargado en el form"
    except Exception as e:
        datos["error_form"] = f"{type(e).__name__}: {e}"

    try:
        siniestro, fuente = await _extraer_siniestro_de_agenda(page, cc)
        if siniestro:
            datos["siniestro_medi"] = siniestro
            datos["siniestro_fuente"] = fuente
        else:
            datos["siniestro_medi"] = "[VERIFICAR]"
            datos["siniestro_fuente"] = "no_encontrado"
    except Exception as e:
        datos["error_agenda"] = f"{type(e).__name__}: {e}"
        datos["siniestro_medi"] = "[VERIFICAR]"
        datos["siniestro_fuente"] = "error"

    return datos
