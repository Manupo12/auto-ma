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


async def _extraer_tabla_generica(page: Page) -> List[Dict]:
    """Extrae cualquier tabla HTML como lista de dicts."""
    filas_data = []
    try:
        filas = await page.locator("table tbody tr").all()
        for fila in filas:
            celdas = await fila.locator("td").all_text_contents()
            if celdas:
                filas_data.append({f"col{i}": c.strip() for i, c in enumerate(celdas)})
    except Exception:
        pass
    return filas_data


async def _extraer_panel_activo(page: Page) -> str:
    """Extrae texto del panel visible después de clickear una pestaña."""
    try:
        content = await page.locator(".tab-pane.active, .panel-body, main").text_content(timeout=5000)
        return (content or "").strip()[:1500]
    except Exception:
        return ""


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

    # 3-6. Pestañas restantes: extraer tablas + texto visible
    for tab_key, data_key in [
        ("rehab_integral", "rehabilitacion_integral"),
        ("gestion_aut", "autorizaciones"),
        ("evoluciones", "evoluciones"),
        ("bitacoras", "bitacoras"),
    ]:
        if await _click_tab(page, tab_key):
            tablas = await _extraer_tabla_generica(page)
            if tablas:
                datos[data_key] = tablas
            else:
                texto = await _extraer_panel_activo(page)
                if texto:
                    datos[data_key] = texto

    return datos
