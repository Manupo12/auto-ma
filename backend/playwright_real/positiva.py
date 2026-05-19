"""
Extractor real ARL Positiva.

Consulta Integral → 6 pestañas:
  DATOS ASEGURADO, SINIESTROS, REHABILITACIÓN INTEGRAL,
  GESTIÓN AUTORIZACIONES, EVOLUCIONES, BITACORAS
"""
from typing import Dict, List
from playwright.async_api import Page

from backend.playwright_real import selectores as S


async def _buscar_paciente(page: Page, cc: str) -> bool:
    """Va a Consulta Integral y busca por CC."""
    try:
        await page.click(S.POS_CONSULTA_INTEGRAL["menu"], timeout=10000)
        await page.wait_for_selector(S.POS_CONSULTA_INTEGRAL["numero_id_input"], timeout=10000)
        await page.fill(S.POS_CONSULTA_INTEGRAL["numero_id_input"], cc)
        await page.click(S.POS_CONSULTA_INTEGRAL["buscar_button"])
        await page.wait_for_load_state("networkidle", timeout=15000)
        return True
    except Exception:
        return False


async def _click_tab(page: Page, tab_key: str) -> bool:
    """Click en una pestaña de Consulta Integral."""
    try:
        selector = S.POS_TABS[tab_key]
        await page.click(selector, timeout=10000)
        await page.wait_for_load_state("networkidle", timeout=10000)
        return True
    except Exception:
        return False


async def _extraer_tabla_siniestros(page: Page) -> List[Dict]:
    """Extrae filas de la tabla SINIESTROS."""
    siniestros = []
    try:
        filas = await page.locator(S.POS_TABLA_SINIESTROS["filas"]).all()
        for fila in filas:
            celdas = await fila.locator("td").all_text_contents()
            if len(celdas) >= 9:
                siniestros.append({
                    "id": celdas[S.POS_TABLA_SINIESTROS["col_siniestro"] - 1].strip(),
                    "fecha": celdas[S.POS_TABLA_SINIESTROS["col_fecha"] - 1].strip(),
                    "tipo_evento": celdas[S.POS_TABLA_SINIESTROS["col_tipo_evento"] - 1].strip(),
                    "pcl": celdas[S.POS_TABLA_SINIESTROS["col_pcl"] - 1].strip(),
                    "diagnostico": celdas[S.POS_TABLA_SINIESTROS["col_diagnostico"] - 1].strip(),
                })
    except Exception:
        pass
    return siniestros


async def _extraer_datos_asegurado(page: Page) -> Dict:
    """Extrae datos visibles de la pestaña DATOS ASEGURADO."""
    datos = {}
    try:
        label_value_pairs = await page.locator(".form-group, .row, tr").all()
        for pair in label_value_pairs[:15]:
            text = (await pair.text_content() or "").strip()
            if ":" in text:
                parts = text.split(":", 1)
                datos[parts[0].strip()] = parts[1].strip()
    except Exception:
        pass
    return datos


async def get_paciente_completo(page: Page, cc: str) -> Dict:
    """
    Función principal. Navega las 6 pestañas y extrae datos.
    """
    datos = {"cc_buscado": cc, "fuente": "positiva"}

    encontrado = await _buscar_paciente(page, cc)
    if not encontrado:
        datos["error_busqueda"] = "paciente no encontrado en Positiva"
        return datos

    # 1. Siniestros
    if await _click_tab(page, "siniestros"):
        siniestros = await _extraer_tabla_siniestros(page)
        datos["siniestros"] = siniestros
        if siniestros:
            datos["siniestro_principal"] = siniestros[0]
    else:
        datos["error_siniestros"] = "no se pudo acceder a la pestaña SINIESTROS"

    # 2. Datos asegurado
    if await _click_tab(page, "datos_asegurado"):
        datos_aseg = await _extraer_datos_asegurado(page)
        datos.update(datos_aseg)

    # 3. Rehabilitación integral
    if await _click_tab(page, "rehab_integral"):
        try:
            contenido = await page.locator("[data-tab='rehabilitacion']").text_content(timeout=5000)
            if contenido:
                datos["rehabilitacion_integral"] = contenido.strip()[:1000]
        except Exception:
            pass

    # 4. Gestión autorizaciones
    if await _click_tab(page, "gestion_aut"):
        try:
            contenido = await page.locator("[data-tab='autorizaciones']").text_content(timeout=5000)
            if contenido:
                datos["autorizaciones"] = contenido.strip()[:1000]
        except Exception:
            pass

    # 5. Evoluciones
    if await _click_tab(page, "evoluciones"):
        try:
            contenido = await page.locator("[data-tab='evoluciones']").text_content(timeout=5000)
            if contenido:
                datos["evoluciones"] = contenido.strip()[:1000]
        except Exception:
            pass

    # 6. Bitácoras
    if await _click_tab(page, "bitacoras"):
        try:
            contenido = await page.locator("[data-tab='bitacoras']").text_content(timeout=5000)
            if contenido:
                datos["bitacoras"] = contenido.strip()[:1000]
        except Exception:
            pass

    return datos
