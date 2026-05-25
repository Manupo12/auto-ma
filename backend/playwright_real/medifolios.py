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
    """Llena CC y dispara busqueda del paciente via JS helper."""
    try:
        await page.fill(S.MEDI_PACIENTES["numero_id_input"], cc)
        await page.evaluate(S.MEDI_JS_CARGAR_PACIENTE, cc)
        await page.wait_for_timeout(4000)
    except Exception:
        return False

    try:
        nombre = await page.input_value(S.MEDI_PACIENTES["nombre1"], timeout=8000)
    except Exception:
        nombre = ""
    return bool(nombre)


async def _extraer_form_pacientes(page: Page) -> Dict:
    """Extrae TODOS los campos del formulario de pacientes via JS helper."""
    REMAP = {"slct_eps_paciente": "eps_ips", "slct_afp_paciente": "afp", "slct_arl_paciente": "arl", "slct_empresa_paciente": "empresa"}
    campos = await page.evaluate(S.MEDI_JS_EXTRAER_FORM)
    return {REMAP.get(k, k): v for k, v in campos.items() if v and str(v).strip()}


async def _extraer_siniestro_de_agenda(page: Page, cc: str, nombre_paciente: str = "") -> tuple:
    """
    Navega a Agenda Citas. Itera TODAS las citas visibles.
    Para cada cita que matchee (por CC o nombre), abre el detalle y lee observaciones.
    Retorna (siniestro, fuente) o ("", "").
    """
    from backend.playwright_real.session import capturar_screenshot_error

    try:
        await page.goto(S.MEDI_AGENDA["url"], timeout=30000)
        await page.wait_for_timeout(5000)
    except Exception as e:
        await capturar_screenshot_error(page, "medifolios", "agenda_nav_error")
        return "", ""

    try:
        select_el = page.locator(S.MEDI_AGENDA["select_profesional"]).first
        if await select_el.count() > 0:
            await select_el.select_option(S.MEDI_AGENDA["valor_sandra"])
            await page.wait_for_timeout(3000)
    except Exception:
        pass

    body = await page.text_content("body") or ""
    siniestro_match = re.search(r'NO\.?\s*SINIESTRO\s*:?\s*(\d{8,12})', body, re.IGNORECASE)
    if siniestro_match:
        return siniestro_match.group(1), "agenda_body"
    siniestro_match = re.search(r'[Ss]iniestro\s*:?\s*(\d{8,12})', body)
    if siniestro_match:
        return siniestro_match.group(1), "agenda_body"

    terminos_busqueda = [cc]
    if nombre_paciente:
        partes = nombre_paciente.split()
        if len(partes) >= 2:
            terminos_busqueda.append(partes[0])
            terminos_busqueda.append(partes[-1])

    filas = await page.query_selector_all("table tbody tr")
    for fila in filas:
        fila_texto = (await fila.text_content() or "").strip().upper()
        if not any(t.upper() in fila_texto for t in terminos_busqueda):
            continue

        link = await fila.query_selector("a[href], button, td")
        if not link:
            continue

        try:
            await link.click(timeout=8000)
            await page.wait_for_timeout(3000)

            for selector_obs in S.MEDI_AGENDA_DETALLE["campo_observaciones"]:
                try:
                    obs_el = page.locator(selector_obs).first
                    if await obs_el.count() > 0:
                        obs_text = await obs_el.input_value() or await obs_el.text_content() or ""
                        sin_match = re.search(r'(?:NO\.?\s*SINIESTRO|Siniestro)\s*:?\s*(\d{8,12})', obs_text, re.IGNORECASE)
                        if sin_match:
                            try:
                                close_btn = page.locator(S.MEDI_AGENDA_DETALLE["boton_cerrar_modal"]).first
                                if await close_btn.count() > 0:
                                    await close_btn.click()
                                    await page.wait_for_timeout(1000)
                            except Exception:
                                pass
                            return sin_match.group(1), "agenda_detalle"
                except Exception:
                    continue

            detail_body = await page.text_content("body") or ""
            sin_match = re.search(r'(?:NO\.?\s*SINIESTRO|Siniestro)\s*:?\s*(\d{8,12})', detail_body, re.IGNORECASE)
            if sin_match:
                await page.go_back()
                await page.wait_for_timeout(2000)
                return sin_match.group(1), "agenda_detalle"

            current_url = page.url
            if "agenda" not in current_url.lower():
                await page.goto(S.MEDI_AGENDA["url"], timeout=30000)
                await page.wait_for_timeout(3000)

        except Exception as e:
            await capturar_screenshot_error(page, "medifolios", "cita_click_error")
            continue

    return "", ""


async def _extraer_historia_clinica(page: Page, cc: str) -> Dict:
    """
    Navega a la seccion Historia Clinica de Medifolios.
    Extrae diagnosticos CIE-10, notas del fisioterapeuta, evoluciones.
    """
    from backend.playwright_real.session import capturar_screenshot_error

    resultado = {}

    urls_hc = [
        "https://www.server0medifolios.net/index.php/SALUD_HOME/historia_clinica",
        "https://www.server0medifolios.net/index.php/SALUD_HISTORIA/historia",
        "https://www.server0medifolios.net/index.php/SALUD_HC/hc",
    ]

    for url in urls_hc:
        try:
            await page.goto(url, timeout=15000)
            await page.wait_for_timeout(3000)
            body = await page.text_content("body") or ""
            if any(kw in body for kw in ["CIE", "Diagnostico", "Evolucion", "Historia"]):
                try:
                    cc_input = await page.wait_for_selector(S.MEDI_HC["input_cc_hc"], timeout=3000)
                    await cc_input.fill(cc)
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(3000)
                    body = await page.text_content("body") or ""
                except Exception:
                    pass

                cie10 = re.findall(r'\b([A-Z]\d{2,3}(?:\.\d)?)\b\s*[-–]?\s*([A-Za-záéíóúñ\s]{5,60})?', body)
                if cie10:
                    resultado["diagnosticos_hc"] = [
                        {"codigo": m[0], "descripcion": (m[1] or "").strip()}
                        for m in cie10[:5] if m[0]
                    ]

                notas_match = re.search(r'(?:Nota|Observaci[oó]n|Evoluci[oó]n)[:\s]+(.{50,500})', body, re.DOTALL)
                if notas_match:
                    resultado["notas_hc"] = notas_match.group(1).strip()[:500]

                if resultado:
                    return resultado
        except Exception:
            continue

    try:
        for texto_menu in ["Historia Clinica", "Historia clinica", "HC", "Historias"]:
            menu_link = page.locator(f"a:has-text('{texto_menu}')").first
            if await menu_link.count() > 0:
                await menu_link.click()
                await page.wait_for_timeout(3000)
                body = await page.text_content("body") or ""
                if cc in body:
                    cie10 = re.findall(r'\b([A-Z]\d{2,3}(?:\.\d)?)\b', body)
                    if cie10:
                        resultado["diagnosticos_hc"] = [{"codigo": c} for c in list(set(cie10))[:5]]
                    return resultado
    except Exception:
        await capturar_screenshot_error(page, "medifolios", "historia_clinica_error")

    return resultado


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

    nombre_para_agenda = datos.get("nombre", "")
    try:
        siniestro, fuente = await _extraer_siniestro_de_agenda(page, cc, nombre_para_agenda)
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

    try:
        hc = await _extraer_historia_clinica(page, cc)
        if hc:
            datos["historia_clinica"] = hc
    except Exception:
        pass

    campos_criticos = ["nombre", "fecha_nacimiento", "telefono"]
    datos["_campos_extraidos_medi"] = [c for c in campos_criticos if datos.get(c)]
    datos["_completo_medi"] = len(datos["_campos_extraidos_medi"]) >= 2

    return datos
