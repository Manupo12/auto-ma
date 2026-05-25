"""
Extractor real ARL Positiva — actualizado Mayo 2026.

Flujo:
  1. CONSULTA INTEGRAL: buscar paciente → extraer siniestros, CIE-10, datos asegurado
  2. RHI Consultar Caso: datos de rehabilitacion
"""
import re
from typing import Dict, List
from playwright.async_api import Page

from backend.playwright_real import selectores as S


async def _buscar_en_consulta_integral(page: Page, cc: str) -> bool:
    """Navega a CONSULTA INTEGRAL y busca paciente por CC."""
    await page.goto("https://positivacuida.positiva.gov.co/consultas/consulta-caso/consultaCaso.page", timeout=30000)
    await page.wait_for_timeout(5000)

    try:
        cc_input = await page.wait_for_selector(
            "input[name*='numeroIdentificacion'], input[name*='numeroDocumento']", timeout=8000
        )
        await cc_input.fill(cc)
    except Exception:
        return False

    for b in await page.query_selector_all("button, input[type=submit]"):
        t = (await b.text_content() or "").strip().lower()
        if "buscar" in t or "consultar" in t:
            await b.click()
            break
    else:
        await cc_input.press("Enter")

    await page.wait_for_timeout(8000)
    return True


async def _extraer_datos_visibles(page: Page) -> Dict:
    """Extrae todos los datos visibles del HTML usando patrones de texto."""
    body = await page.text_content("body") or ""
    datos = {}

    fecha_match = re.search(r"[Ff]echa\s*[Ss]iniestro[:\s]*(\d{2,4}[-/]\d{2}[-/]\d{2,4})", body)
    if fecha_match:
        datos["fecha_siniestro"] = fecha_match.group(1)

    cie10_text = ""
    try:
        for selector in [
            "table:has(th:has-text('Diagnóstico'))",
            "table:has(th:has-text('CIE'))",
            "table:has(th:has-text('DX'))",
            "[data-tab='siniestros'] table",
            "table.siniestros",
            "table.datos-clinicos",
            "table.datosClinicos",
        ]:
            els = await page.query_selector_all(selector)
            for el in els:
                txt = await el.text_content() or ""
                cie10_text += txt + "\n"
    except Exception:
        cie10_text = body

    cie10_matches = re.findall(r'([A-Z]\d{2,3}(?:\.\d)?)\s*[-–]\s*([A-Za-záéíóúñ ]{5,60})', cie10_text)
    if cie10_matches:
        datos["diagnosticos"] = [{"codigo": m[0], "descripcion": m[1].strip()} for m in cie10_matches[:3]]
    else:
        cie10_simple = re.findall(r'\b([A-Z]\d{2,3}(?:\.\d)?)\b', cie10_text)
        if cie10_simple:
            datos["cie10_candidatos"] = list(set(cie10_simple))[:5]

    datos["texto_completo_len"] = len(body)
    return datos


async def _extraer_siniestros_tabla(page: Page) -> list:
    """Extrae siniestros usando query_selector_all sobre la tabla de siniestros."""
    siniestros = []

    try:
        for tab_label in ["SINIESTROS", "Siniestros", "siniestros"]:
            tabs = await page.query_selector_all(f"a:has-text('{tab_label}'), li:has-text('{tab_label}')")
            if tabs:
                await tabs[0].click()
                await page.wait_for_timeout(5000)
                break
    except Exception:
        pass

    try:
        filas = await page.query_selector_all(S.POS_TABLA_SINIESTROS["filas"])
    except Exception:
        filas = await page.query_selector_all("tbody tr")

    for fila in filas:
        try:
            celdas = await fila.query_selector_all("td")
            if len(celdas) < 3:
                continue

            siniestro = {
                "id": (await celdas[S.POS_TABLA_SINIESTROS["col_siniestro"] - 1].text_content() or "").strip(),
                "fecha": (await celdas[S.POS_TABLA_SINIESTROS["col_fecha"] - 1].text_content() or "").strip(),
            }
            if len(celdas) > S.POS_TABLA_SINIESTROS["col_tipo_evento"]:
                siniestro["tipo"] = (await celdas[S.POS_TABLA_SINIESTROS["col_tipo_evento"] - 1].text_content() or "").strip()
            if len(celdas) > S.POS_TABLA_SINIESTROS["col_diagnostico"]:
                siniestro["diagnostico"] = (await celdas[S.POS_TABLA_SINIESTROS["col_diagnostico"] - 1].text_content() or "").strip()

            if siniestro["id"] and siniestro["id"].isdigit() and len(siniestro["id"]) >= 7:
                siniestros.append(siniestro)
        except Exception:
            continue

    return siniestros


async def _buscar_en_rhi(page: Page, cc: str) -> Dict:
    """Busca en RHI Consultar Caso."""
    rhi = {}
    try:
        await page.goto("https://positivacuida.positiva.gov.co/web/rhi/consultarCaso/init", timeout=30000)
        await page.wait_for_timeout(5000)

        doc_input = await page.wait_for_selector("#numeroDocumento", timeout=5000)
        await doc_input.fill(cc)

        for b in await page.query_selector_all("button"):
            t = (await b.text_content() or "").strip().lower()
            if "buscar" in t or "consultar" in t:
                await b.click()
                break

        await page.wait_for_timeout(8000)
        body = await page.text_content("body") or ""

        matriculas = re.findall(r"[Mm]atr[ií]cula[:\s]*(\d+)", body)
        if matriculas:
            rhi["matricula"] = matriculas[0]

        fechas = re.findall(r"(\d{2}/\d{2}/\d{4})", body)
        if fechas:
            rhi["fechas_encontradas"] = fechas[:5]

    except Exception:
        return {"_error": "RHI no disponible", "_rhi_ok": False}
    return rhi


async def get_paciente_completo(page: Page, cc: str) -> Dict:
    """
    Funcion principal. Extrae datos del paciente desde Positiva.
    """
    datos = {"cc_buscado": cc, "fuente": "positiva"}

    encontrado = await _buscar_en_consulta_integral(page, cc)
    if not encontrado:
        datos["error_busqueda"] = "No se pudo buscar en Consulta Integral"
        return datos

    visible = await _extraer_datos_visibles(page)
    datos.update(visible)

    if not datos.get("cie10_candidatos"):
        rhi_data = await _buscar_en_rhi(page, cc)
        datos["rhi"] = rhi_data

    siniestros = await _extraer_siniestros_tabla(page)
    if siniestros:
        datos["siniestros"] = siniestros
        datos["siniestro_id"] = siniestros[0]["id"]

    return datos
