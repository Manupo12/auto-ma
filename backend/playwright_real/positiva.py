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
    body = await page.text_content("body") or ""
    body_lower = body.lower()
    if any(msg in body_lower for msg in ["no se encontro", "sin resultados", "0 registros", "no se encontraron", "no hay datos", "no existe"]):
        return False
    if cc not in body:
        return False
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
    """
    Extrae siniestros leyendo headers de tabla para detectar columnas dinamicamente.
    Para cada siniestro, abre la pagina de detalle y extrae datos completos.
    """
    from backend.playwright_real.session import capturar_screenshot_error
    siniestros = []

    for selector in [
        "a:has-text('SINIESTROS')",
        "a:has-text('Siniestros')",
        "li:has-text('SINIESTROS') a",
        "[data-tab='siniestros']",
    ]:
        try:
            tab = page.locator(selector).first
            if await tab.count() > 0:
                await tab.click()
                await page.wait_for_timeout(3000)
                break
        except Exception:
            continue

    try:
        await page.wait_for_selector("table tbody tr", timeout=10000)
    except Exception:
        await capturar_screenshot_error(page, "positiva", "siniestros_tabla_no_carga")

    col_map = {}
    try:
        headers = await page.query_selector_all("table thead th, table tr:first-child th, table tr:first-child td")
        for i, h in enumerate(headers):
            texto = (await h.text_content() or "").strip().lower()
            if any(kw in texto for kw in ["siniestro", "no.", "numero", "nro."]):
                col_map["siniestro"] = i
            elif any(kw in texto for kw in ["fecha", "ocurrencia"]):
                if "siniestro" not in col_map or i != col_map.get("siniestro"):
                    col_map["fecha"] = i
            elif any(kw in texto for kw in ["tipo", "evento", "clase"]):
                col_map["tipo"] = i
            elif any(kw in texto for kw in ["diagnostico", "diagnóstico", "cie", "dx"]):
                col_map["diagnostico"] = i
            elif any(kw in texto for kw in ["pcl", "perdida", "pérdida"]):
                col_map["pcl"] = i
            elif any(kw in texto for kw in ["estado", "estatus"]):
                col_map["estado"] = i
    except Exception:
        pass

    col_map.setdefault("siniestro", 0)
    col_map.setdefault("fecha", 1)
    col_map.setdefault("tipo", 2)
    col_map.setdefault("diagnostico", 7)

    filas = []
    for sel in [
        "table.siniestros tbody tr",
        "[data-tab='siniestros'] tbody tr",
        "#siniestros tbody tr",
        "table tbody tr",
    ]:
        try:
            filas = await page.query_selector_all(sel)
            if filas:
                break
        except Exception:
            continue

    for fila in filas:
        try:
            celdas = await fila.query_selector_all("td")
            if len(celdas) < 3:
                continue

            idx_sin = col_map.get("siniestro", 0)
            idx_fecha = col_map.get("fecha", 1)
            idx_tipo = col_map.get("tipo", 2)
            idx_dx = col_map.get("diagnostico", 7)

            sin_id = (await celdas[idx_sin].text_content() or "").strip() if idx_sin < len(celdas) else ""
            fecha = (await celdas[idx_fecha].text_content() or "").strip() if idx_fecha < len(celdas) else ""
            tipo = (await celdas[idx_tipo].text_content() or "").strip() if idx_tipo < len(celdas) else ""
            diagnostico = (await celdas[idx_dx].text_content() or "").strip() if idx_dx < len(celdas) else ""

            sin_limpio = re.sub(r'\D', '', sin_id)
            if not sin_limpio or len(sin_limpio) < 7:
                continue

            siniestro = {
                "id": sin_limpio,
                "fecha": fecha,
                "tipo": tipo,
                "diagnostico": diagnostico,
            }

            try:
                link = await fila.query_selector("a[href]")
                if link:
                    href = await link.get_attribute("href") or ""
                    await link.click()
                    await page.wait_for_timeout(5000)
                    detalle_body = await page.text_content("body") or ""

                    cie10_matches = re.findall(r'([A-Z]\d{2,3}(?:\.\d)?)\s*[-–]\s*([A-Za-záéíóúñ\s,\.]{5,80})', detalle_body)
                    if cie10_matches:
                        siniestro["diagnosticos_detalle"] = [
                            {"codigo": m[0], "descripcion": m[1].strip()}
                            for m in cie10_matches[:3]
                        ]

                    seg_match = re.search(r'(?:segmento|region|zona)[:\s]+([A-Za-záéíóúñ\s,]+?)(?:\n|\.)', detalle_body, re.IGNORECASE)
                    if seg_match:
                        siniestro["segmento"] = seg_match.group(1).strip()

                    pcl_match = re.search(r'PCL[:\s]+(\d+(?:\.\d+)?)\s*%', detalle_body, re.IGNORECASE)
                    if pcl_match:
                        siniestro["pcl"] = pcl_match.group(1) + "%"

                    fecha_match = re.search(r'[Ff]echa\s+[Ss]iniestro[:\s]+(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})', detalle_body)
                    if fecha_match:
                        siniestro["fecha_siniestro_exacta"] = fecha_match.group(1)

                    await page.go_back()
                    await page.wait_for_timeout(3000)
                    try:
                        for sel_tab in ["a:has-text('SINIESTROS')", "a:has-text('Siniestros')"]:
                            tab = page.locator(sel_tab).first
                            if await tab.count() > 0:
                                await tab.click()
                                await page.wait_for_timeout(2000)
                                break
                    except Exception:
                        pass
            except Exception:
                pass

            siniestros.append(siniestro)
        except Exception:
            continue

    if not siniestros:
        body = await page.text_content("body") or ""
        match = re.search(r'\b(5\d{8})\b', body)
        if match:
            siniestros = [{"id": match.group(1), "fecha": "", "tipo": "AT", "_fuente": "regex_fallback"}]

    return siniestros


async def _buscar_en_rhi(page: Page, cc: str) -> Dict:
    """
    Busca en RHI Consultar Caso. Extrae siniestro confirmado, diagnostico,
    plan de manejo, fechas de tratamiento.
    """
    rhi = {}
    try:
        await page.goto(S.POS_RHI_COMPLETO["url"], timeout=30000)
        await page.wait_for_timeout(5000)

        for selector_cc in S.POS_RHI_COMPLETO["input_cc"].split(", "):
            try:
                doc_input = await page.wait_for_selector(selector_cc, timeout=3000)
                await doc_input.fill(cc)
                break
            except Exception:
                continue

        for b in await page.query_selector_all("button"):
            t = (await b.text_content() or "").strip().lower()
            if "buscar" in t or "consultar" in t:
                await b.click()
                break
        else:
            await page.keyboard.press("Enter")

        await page.wait_for_timeout(8000)
        body = await page.text_content("body") or ""

        matriculas = re.findall(r"[Mm]atr[ií]cula[:\s]*(\d+)", body)
        if matriculas:
            rhi["matricula"] = matriculas[0]

        sin_match = re.search(r'\b(5\d{8})\b', body)
        if sin_match:
            rhi["siniestro_rhi"] = sin_match.group(1)

        cie10 = re.findall(r'\b([A-Z]\d{2,3}(?:\.\d)?)\b\s*[-–]?\s*([A-Za-záéíóúñ\s,\.]{5,60})?', body)
        if cie10:
            rhi["diagnosticos_rhi"] = [
                {"codigo": m[0], "descripcion": (m[1] or "").strip()}
                for m in cie10[:3]
            ]

        fechas = re.findall(r"(\d{2}/\d{2}/\d{4})", body)
        if fechas:
            rhi["fechas_encontradas"] = list(dict.fromkeys(fechas))[:8]

        plan_match = re.search(r'[Pp]lan[:\s]+(.{30,300}?)(?:\n\n|\.\s)', body, re.DOTALL)
        if plan_match:
            rhi["plan_manejo"] = plan_match.group(1).strip()[:300]

        estado_match = re.search(r'[Ee]stado[:\s]+([A-Za-záéíóúñ\s]+?)(?:\n|,)', body)
        if estado_match:
            rhi["estado_caso"] = estado_match.group(1).strip()

    except Exception as e:
        return {"_error": f"RHI no disponible: {e}", "_rhi_ok": False}

    rhi["_rhi_ok"] = bool(rhi.get("siniestro_rhi") or rhi.get("matricula"))
    return rhi


async def _extraer_datos_asegurado(page: Page) -> Dict:
    """
    Navega a pestana DATOS ASEGURADO y extrae datos parseando celdas de tabla.
    NO usa regex sobre body completo -- eso captura el header del usuario logueado.
    """
    from backend.playwright_real.session import capturar_screenshot_error

    datos = {}

    navegado = False
    for selector in [
        "a:has-text('DATOS ASEGURADO')",
        "a:has-text('Datos Asegurado')",
        "a:has-text('DATOS DEL ASEGURADO')",
        "[data-tab='datos']",
        "li:has-text('DATOS ASEGURADO') a",
    ]:
        try:
            tab = page.locator(selector).first
            if await tab.count() > 0:
                await tab.click()
                await page.wait_for_timeout(4000)
                navegado = True
                break
        except Exception:
            continue

    if not navegado:
        await capturar_screenshot_error(page, "positiva", "datos_asegurado_tab_no_encontrado")

    tablas = await page.query_selector_all("table")
    for tabla in tablas:
        filas = await tabla.query_selector_all("tr")
        for fila in filas:
            celdas = await fila.query_selector_all("td, th")
            textos = [(await c.text_content() or "").strip() for c in celdas]

            if len(textos) >= 2:
                label = textos[0].lower().rstrip(":").strip()
                valor = textos[1].strip()

                if not valor or len(valor) < 2:
                    continue
                if valor in ("Usuario Acciones", "MARIA GREIDY", "1075209386"):
                    continue
                if valor == label:
                    continue

                if label in ("empresa", "razon social", "razón social", "empleador"):
                    datos["empresa"] = valor
                elif label in ("nit", "nit empresa"):
                    datos["nit"] = valor
                elif label in ("cargo", "cargo asegurado", "ocupacion", "ocupación"):
                    datos["cargo_asegurado"] = valor
                elif label in ("eps", "eps del trabajador"):
                    datos["eps"] = valor
                elif label in ("afp", "fondo de pensiones"):
                    datos["afp"] = valor
                elif label in ("tipo de vinculacion", "tipo vinculacion", "tipo contrato"):
                    datos["tipo_vinculacion"] = valor
                elif label in ("salario", "ibc"):
                    datos["salario"] = valor

    if not datos.get("empresa"):
        try:
            empresa_label = page.locator("td:has-text('Empresa'), th:has-text('Empresa'), label:has-text('Empresa')").first
            if await empresa_label.count() > 0:
                empresa_valor = await page.evaluate("""(el) => {
                    const next = el.nextElementSibling;
                    return next ? next.textContent.trim() : '';
                }""", await empresa_label.element_handle())
                if empresa_valor and empresa_valor not in ("Usuario Acciones", "MARIA GREIDY"):
                    datos["empresa"] = empresa_valor
        except Exception:
            pass

    return datos


async def _extraer_rehab_integral(page: Page) -> Dict:
    """
    Navega a REHABILITACION INTEGRAL y extrae estado actual del proceso.
    """
    datos = {}
    try:
        for selector in S.POS_REHAB_INTEGRAL["tab"]:
            tab = page.locator(selector).first
            if await tab.count() > 0:
                await tab.click()
                await page.wait_for_timeout(4000)
                break

        body = await page.text_content("body") or ""

        estado_match = re.search(r'[Ee]stado[:\s]+([A-Za-záéíóúñ\s]+?)(?:\n|,|\|)', body)
        if estado_match:
            datos["estado_rehab"] = estado_match.group(1).strip()

        fechas = re.findall(r'\d{2}/\d{2}/\d{4}', body)
        if fechas:
            datos["fechas_rehab"] = fechas[:5]

        interv_match = re.search(r'(?:Intervenci[oó]n|Tipo)[:\s]+([A-Za-záéíóúñ\s]+?)(?:\n|,)', body, re.IGNORECASE)
        if interv_match:
            datos["tipo_intervencion"] = interv_match.group(1).strip()

    except Exception:
        pass
    return datos


async def _extraer_autorizaciones(page: Page) -> list:
    """
    Navega a GESTION AUTORIZACIONES y extrae autorizaciones activas.
    """
    autorizaciones = []
    try:
        for selector in S.POS_AUTORIZACIONES["tab"]:
            tab = page.locator(selector).first
            if await tab.count() > 0:
                await tab.click()
                await page.wait_for_timeout(4000)
                break

        filas = await page.query_selector_all("table tbody tr")
        for fila in filas:
            celdas = await fila.query_selector_all("td")
            if len(celdas) >= 3:
                textos = [(await c.text_content() or "").strip() for c in celdas]
                if any(t for t in textos if len(t) > 2):
                    autorizaciones.append({
                        "numero": textos[0] if textos else "",
                        "descripcion": textos[1] if len(textos) > 1 else "",
                        "estado": textos[2] if len(textos) > 2 else "",
                    })
    except Exception:
        pass
    return autorizaciones[:5]


async def get_paciente_completo(page: Page, cc: str) -> Dict:
    """
    Funcion principal. Extrae datos del paciente desde Positiva.
    """
    datos = {"cc_buscado": cc, "fuente": "positiva"}

    encontrado = await _buscar_en_consulta_integral(page, cc)
    if not encontrado:
        datos["_sin_datos_clinicos"] = True
        datos["_advertencia"] = "Paciente no encontrado en Consulta Integral de Positiva"
        datos["error_busqueda"] = "Paciente no encontrado en Consulta Integral"
        return datos

    visible = await _extraer_datos_visibles(page)
    datos.update(visible)

    datos_asegurado = await _extraer_datos_asegurado(page)
    if datos_asegurado:
        datos["datos_asegurado"] = datos_asegurado

    siniestros = await _extraer_siniestros_tabla(page)
    if siniestros:
        datos["siniestros"] = siniestros
        datos["siniestro_id"] = siniestros[0]["id"]

    rehab = await _extraer_rehab_integral(page)
    if rehab:
        datos["rehabilitacion"] = rehab

    autorizaciones = await _extraer_autorizaciones(page)
    if autorizaciones:
        datos["autorizaciones"] = autorizaciones

    tiene_cie10 = (
        datos.get("diagnosticos") or
        datos.get("cie10_candidatos") or
        any(s.get("diagnosticos_detalle") for s in siniestros if isinstance(s, dict))
    )
    if not tiene_cie10:
        rhi_data = await _buscar_en_rhi(page, cc)
        datos["rhi"] = rhi_data

    campos_criticos = ["siniestro_id", "datos_asegurado"]
    datos["_campos_extraidos_pos"] = [c for c in campos_criticos if datos.get(c)]
    datos["_completo_pos"] = bool(datos.get("siniestro_id"))

    return datos
