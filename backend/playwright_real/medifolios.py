"""
Extractor real de datos del paciente desde Medifolios.

Usa los selectores documentados en skills/flujo-browser/references/.
4 fuentes de datos:
  1. Form pacientes (DATOS PERSONALES + DATOS GENERALES)
  2. Historia Clínica → Visión Clínica
  3. Agenda Citas → Popup → Observaciones (siniestro)
"""
import re
from typing import Dict
from playwright.async_api import Page

from backend.playwright_real import selectores as S


async def _navegar_a_pacientes(page: Page):
    """Click en menú Pacientes."""
    try:
        await page.click(S.MEDI_PACIENTES["menu_pacientes"], timeout=10000)
    except Exception:
        pass
    await page.wait_for_selector(S.MEDI_PACIENTES["numero_id_input"], timeout=10000)


async def _cargar_paciente_en_form(page: Page, cc: str) -> bool:
    """JS para forzar carga (Enter nativo no dispara)."""
    ok = await page.evaluate(S.MEDI_JS_CARGAR_PACIENTE, cc)
    if not ok:
        return False
    await page.wait_for_function(
        "() => { const f = document.getElementById('nombre1'); return f && f.value.length > 0; }",
        timeout=15000,
    )
    return True


async def _extraer_form_pacientes(page: Page) -> Dict:
    """Extrae todos los campos del form de pacientes vía JS."""
    return await page.evaluate(S.MEDI_JS_EXTRAER_FORM)


async def _extraer_siniestro_de_agenda(page: Page, cc: str) -> str:
    """Navega a Agenda Citas → busca cita del paciente → extrae siniestro de observaciones."""
    try:
        await page.click(S.MEDI_AGENDA["menu_agenda"], timeout=10000)
    except Exception:
        return ""

    try:
        await page.select_option(S.MEDI_AGENDA["select_profesional"], S.MEDI_AGENDA["valor_sandra"])
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass

    try:
        link_selector = S.MEDI_AGENDA["cita_link_template"].format(cc=cc)
        await page.click(link_selector, timeout=5000)
    except Exception:
        return ""

    try:
        obs_el = await page.wait_for_selector(S.MEDI_AGENDA["popup_detalle_observaciones"], timeout=5000)
        observaciones = await obs_el.input_value() if obs_el else ""
        match = re.search(S.MEDI_REGEX_SINIESTRO, observaciones, re.IGNORECASE)
        return match.group(1) if match else ""
    except Exception:
        return ""


async def get_paciente_completo(page: Page, cc: str) -> Dict:
    """
    Función principal. Retorna dict con campos extraídos + campos faltantes marcados.
    """
    datos = {"cc_buscado": cc, "fuente": "medifolios"}

    try:
        await _navegar_a_pacientes(page)
        cargado = await _cargar_paciente_en_form(page, cc)
        if cargado:
            form = await _extraer_form_pacientes(page)
            datos.update(form)
        else:
            datos["error_form"] = "no se pudo cargar el paciente"
    except Exception as e:
        datos["error_form"] = f"{type(e).__name__}: {e}"

    try:
        siniestro = await _extraer_siniestro_de_agenda(page, cc)
        if siniestro:
            datos["siniestro_medi"] = siniestro
        else:
            datos["siniestro_medi"] = "[VERIFICAR]"
    except Exception as e:
        datos["error_siniestro"] = f"{type(e).__name__}: {e}"
        datos["siniestro_medi"] = "[VERIFICAR]"

    return datos
