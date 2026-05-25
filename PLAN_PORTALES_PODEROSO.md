# PLAN_PORTALES_PODEROSO.md — Portal Extraction Like a Human

**Creado:** 2026-05-24  
**Objetivo:** Hacer que el módulo `playwright_real/` extraiga información de Medifolios y Positiva con la misma profundidad que un humano revisando la página manualmente — nada de regex en body text, nada de columnas hardcodeadas, nada de pasar de largo si no encontró datos.

**Archivos a modificar:**
- `backend/playwright_real/selectores.py`
- `backend/playwright_real/medifolios.py`
- `backend/playwright_real/positiva.py`
- `backend/playwright_real/session.py` (solo infraestructura de screenshots)

---

## ESTADO ACTUAL — Qué falla y por qué

### Medifolios — 3 fallas críticas

| # | Función | Falla actual |
|---|---------|-------------|
| M-1 | `_extraer_siniestro_de_agenda` | Lee `body` entero con regex. Si el siniestro está en el campo `observaciones` del popup de una cita individual, NUNCA lo encuentra porque ese campo solo carga al abrir la cita. |
| M-2 | `_extraer_siniestro_de_agenda` | Solo intenta hacer click en `tr:has-text('{cc}')` — esto es demasiado frágil; la agenda típicamente no muestra el CC en las filas, muestra el nombre. |
| M-3 | No existe | No navega a Historia Clínica ni a ninguna otra sección — solo extrae el formulario de datos personales. |

### Positiva — 5 fallas críticas

| # | Función | Falla actual |
|---|---------|-------------|
| P-1 | `_extraer_datos_asegurado` | Usa regex sobre `body` completo → captura "Usuario Acciones" del header de navegación (el usuario logueado), no la empresa del paciente. |
| P-2 | `_extraer_siniestros_tabla` | Columnas hardcodeadas: `col_siniestro=1, col_fecha=2, col_diagnostico=8`. Si el portal reordena columnas, todo falla silenciosamente. |
| P-3 | `_extraer_siniestros_tabla` | No abre el detalle de cada siniestro. El número de siniestro, CIE-10 completo, segmento corporal, y PCL están en la página de detalle, no en la tabla. |
| P-4 | `get_paciente_completo` | No navega: REHABILITACIÓN INTEGRAL, GESTIÓN AUTORIZACIONES, EVOLUCIONES, BITÁCORAS. |
| P-5 | `_buscar_en_rhi` | Solo extrae matrícula y fechas. El RHI tiene diagnóstico de ingreso, plan de manejo, y número de siniestro confirmado. |

### Cross-cutting — 3 fallas de infraestructura

| # | Falla |
|---|-------|
| X-1 | Sin screenshot en fallo: cuando algo sale mal, no hay evidencia visual para depurar. |
| X-2 | Sin retry por función: un timeout de red en un selector descarta toda la extracción. |
| X-3 | Sin verificación de datos mínimos: la función retorna aunque extrajo 0 campos útiles. |

---

## PARTE 1 — Infraestructura compartida (session.py + nuevo helper)

### FIX X-1: Captura de screenshots en fallo

**En `session.py`**, agregar función `capturar_screenshot_error`:

```python
async def capturar_screenshot_error(page: Page, portal: str, contexto: str):
    """Guarda screenshot cuando algo falla. Útil para depurar selectores."""
    debug_dir = Path("./storage/playwright_debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = debug_dir / f"{portal}_{contexto}_{ts}.png"
    try:
        await page.screenshot(path=str(path), full_page=True)
        _log(f"{portal.upper()}: screenshot guardado → {path}")
    except Exception as e:
        _log(f"{portal.upper()}: no se pudo capturar screenshot: {e}")
```

Importar esta función en medifolios.py y positiva.py. Llamarla en cada bloque `except` importante.

### FIX X-2: Helper de retry por función

**En `session.py`**, agregar función `con_reintento`:

```python
import functools

async def con_reintento(coro_fn, reintentos: int = 2, delay_s: float = 5.0):
    """
    Ejecuta coro_fn(). Si lanza excepción, reintenta hasta `reintentos` veces
    con `delay_s` segundos entre intentos. Devuelve resultado o lanza la última excepción.
    """
    ultimo_error = None
    for intento in range(reintentos + 1):
        try:
            return await coro_fn()
        except Exception as e:
            ultimo_error = e
            if intento < reintentos:
                await asyncio.sleep(delay_s)
    raise ultimo_error
```

---

## PARTE 2 — Medifolios: extracción completa

### FIX M-1 + M-2: Abrir CADA cita de la agenda y leer observaciones

**El problema raíz:** La agenda carga una lista de citas. El campo `observaciones` (donde está el número de siniestro) solo aparece cuando se abre cada cita individualmente. El código actual solo busca en el body de la lista, nunca abre ninguna cita.

**Estrategia correcta:**
1. Navegar a la agenda
2. Filtrar por la profesional Sandra (select `168-0`)
3. Obtener TODAS las filas de la tabla de citas
4. Para cada fila: extraer el texto visible (puede contener nombre del paciente)
5. Buscar filas que contengan el nombre del paciente o CC
6. Hacer click en el link de la fila → popup o página de detalle
7. Leer el campo `#observaciones` o `textarea[name='observaciones']`
8. Buscar siniestro con regex

**Código completo para `_extraer_siniestro_de_agenda`** — reemplazar completamente:

```python
async def _extraer_siniestro_de_agenda(page: Page, cc: str, nombre_paciente: str = "") -> tuple:
    """
    Navega a Agenda Citas. Itera TODAS las citas visibles.
    Para cada cita que matchee (por CC o nombre), abre el detalle y lee observaciones.
    Retorna (siniestro, fuente) o ("", "").
    """
    from backend.playwright_real.session import capturar_screenshot_error

    # Navegar a la agenda
    try:
        await page.goto(S.MEDI_AGENDA["url"], timeout=30000)
        await page.wait_for_timeout(5000)
    except Exception as e:
        await capturar_screenshot_error(page, "medifolios", "agenda_nav_error")
        return "", ""

    # Seleccionar profesional Sandra para ver sus citas
    try:
        select_el = page.locator(S.MEDI_AGENDA["select_profesional"]).first
        if await select_el.count() > 0:
            await select_el.select_option(S.MEDI_AGENDA["valor_sandra"])
            await page.wait_for_timeout(3000)
    except Exception:
        pass  # Si no hay filtro, igual intentamos buscar

    # Primero: buscar siniestro en body (si está visible directamente)
    body = await page.text_content("body") or ""
    siniestro_match = re.search(r'NO\.?\s*SINIESTRO\s*:?\s*(\d{8,12})', body, re.IGNORECASE)
    if siniestro_match:
        return siniestro_match.group(1), "agenda_body"
    siniestro_match = re.search(r'[Ss]iniestro\s*:?\s*(\d{8,12})', body)
    if siniestro_match:
        return siniestro_match.group(1), "agenda_body"

    # Segundo: iterar filas de la tabla de citas
    terminos_busqueda = [cc]
    if nombre_paciente:
        # Usar apellido y nombre para matching flexible
        partes = nombre_paciente.split()
        if len(partes) >= 2:
            terminos_busqueda.append(partes[0])   # primer nombre o apellido
            terminos_busqueda.append(partes[-1])  # último apellido

    filas = await page.query_selector_all("table tbody tr")
    for fila in filas:
        fila_texto = (await fila.text_content() or "").strip().upper()
        # Verificar si esta fila corresponde al paciente buscado
        if not any(t.upper() in fila_texto for t in terminos_busqueda):
            continue

        # Buscar link clickeable dentro de la fila
        link = await fila.query_selector("a[href], button, td")
        if not link:
            continue

        try:
            await link.click(timeout=8000)
            await page.wait_for_timeout(3000)

            # Leer observaciones en el popup/modal/página de detalle
            for selector_obs in [
                "textarea[name='observaciones']",
                "#observaciones",
                "textarea:near(:text('Observaciones'))",
                ".modal textarea",
                "[class*='modal'] textarea",
            ]:
                try:
                    obs_el = page.locator(selector_obs).first
                    if await obs_el.count() > 0:
                        obs_text = await obs_el.input_value() or await obs_el.text_content() or ""
                        sin_match = re.search(r'(?:NO\.?\s*SINIESTRO|Siniestro)\s*:?\s*(\d{8,12})', obs_text, re.IGNORECASE)
                        if sin_match:
                            # Cerrar modal si hay botón de cierre
                            try:
                                close_btn = page.locator("button:has-text('Cerrar'), button:has-text('Close'), .modal .close, .btn-close").first
                                if await close_btn.count() > 0:
                                    await close_btn.click()
                                    await page.wait_for_timeout(1000)
                            except Exception:
                                pass
                            return sin_match.group(1), "agenda_detalle"
                except Exception:
                    continue

            # Si no encontró en el modal, buscar en página completa
            detail_body = await page.text_content("body") or ""
            sin_match = re.search(r'(?:NO\.?\s*SINIESTRO|Siniestro)\s*:?\s*(\d{8,12})', detail_body, re.IGNORECASE)
            if sin_match:
                await page.go_back()
                await page.wait_for_timeout(2000)
                return sin_match.group(1), "agenda_detalle"

            # Volver a la agenda si navegó a otra página
            current_url = page.url
            if "agenda" not in current_url.lower():
                await page.goto(S.MEDI_AGENDA["url"], timeout=30000)
                await page.wait_for_timeout(3000)

        except Exception as e:
            await capturar_screenshot_error(page, "medifolios", f"cita_click_error")
            continue

    return "", ""
```

### FIX M-3: Navegar Historia Clínica para diagnósticos

Agregar nueva función `_extraer_historia_clinica`:

```python
async def _extraer_historia_clinica(page: Page, cc: str) -> dict:
    """
    Navega a la sección Historia Clínica de Medifolios.
    Extrae diagnósticos CIE-10, notas del fisioterapeuta, evoluciones.
    """
    from backend.playwright_real.session import capturar_screenshot_error

    resultado = {}

    # URLs posibles para Historia Clínica
    urls_hc = [
        f"https://www.server0medifolios.net/index.php/SALUD_HOME/historia_clinica",
        f"https://www.server0medifolios.net/index.php/SALUD_HISTORIA/historia",
        f"https://www.server0medifolios.net/index.php/SALUD_HC/hc",
    ]

    # También intentar via menú
    for url in urls_hc:
        try:
            await page.goto(url, timeout=15000)
            await page.wait_for_timeout(3000)
            body = await page.text_content("body") or ""
            # Si llega a una página con contenido clínico, extraer
            if any(kw in body for kw in ["CIE", "Diagnóstico", "Evolución", "Historia"]):
                # Buscar si hay campo para llenar CC y buscar
                try:
                    cc_input = await page.wait_for_selector("#numero_id, input[name='cc'], input[name='numero_id']", timeout=3000)
                    await cc_input.fill(cc)
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(3000)
                    body = await page.text_content("body") or ""
                except Exception:
                    pass

                # Extraer CIE-10
                cie10 = re.findall(r'\b([A-Z]\d{2,3}(?:\.\d)?)\b\s*[-–]?\s*([A-Za-záéíóúñ\s]{5,60})?', body)
                if cie10:
                    resultado["diagnosticos_hc"] = [
                        {"codigo": m[0], "descripcion": (m[1] or "").strip()}
                        for m in cie10[:5] if m[0]
                    ]

                # Extraer notas libres (primeros 1000 chars relevantes)
                notas_match = re.search(r'(?:Nota|Observaci[oó]n|Evoluci[oó]n)[:\s]+(.{50,500})', body, re.DOTALL)
                if notas_match:
                    resultado["notas_hc"] = notas_match.group(1).strip()[:500]

                if resultado:
                    return resultado
        except Exception:
            continue

    # Si no encontró por URL, buscar menú
    try:
        for texto_menu in ["Historia Clínica", "Historia clinica", "HC", "Historias"]:
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
```

### Actualizar `get_paciente_completo` en medifolios.py

La función principal debe:
1. Pasar `datos.get("nombre")` a `_extraer_siniestro_de_agenda` para matching de citas
2. Llamar a `_extraer_historia_clinica` al final
3. Verificar datos extraídos mínimos antes de retornar

```python
async def get_paciente_completo(page: Page, cc: str) -> Dict:
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

    # Agenda: pasar nombre para búsqueda más flexible
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

    # Historia Clínica: diagnósticos y notas
    try:
        hc = await _extraer_historia_clinica(page, cc)
        if hc:
            datos["historia_clinica"] = hc
    except Exception:
        pass

    # Verificación de datos mínimos
    campos_criticos = ["nombre", "fecha_nacimiento", "telefono"]
    datos["_campos_extraidos_medi"] = [c for c in campos_criticos if datos.get(c)]
    datos["_completo_medi"] = len(datos["_campos_extraidos_medi"]) >= 2

    return datos
```

---

## PARTE 3 — Positiva: extracción profunda

### FIX P-1: `_extraer_datos_asegurado` — parsear CELDAS de tabla, no body regex

**El bug raíz:** La regex `r"[Ee]mpresa[:\s]+([A-ZÁÉÍÓÚÑ]..."` captura el header de navegación de Positiva que dice "Empresa: Usuario Acciones" (el usuario logueado). Necesitamos parsear la tabla real de datos del asegurado.

**Código completo para `_extraer_datos_asegurado`** — reemplazar completamente:

```python
async def _extraer_datos_asegurado(page: Page) -> Dict:
    """
    Navega a pestaña DATOS ASEGURADO y extrae datos parseando celdas de tabla.
    NO usa regex sobre body completo — eso captura el header del usuario logueado.
    """
    from backend.playwright_real.session import capturar_screenshot_error

    datos = {}

    # 1. Navegar a la pestaña
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

    # 2. Parsear tablas celda a celda (NO regex sobre body)
    # Buscar todas las tablas de la página
    tablas = await page.query_selector_all("table")
    for tabla in tablas:
        filas = await tabla.query_selector_all("tr")
        for fila in filas:
            celdas = await fila.query_selector_all("td, th")
            textos = [(await c.text_content() or "").strip() for c in celdas]

            # Patrón: primera celda = label, segunda = valor
            if len(textos) >= 2:
                label = textos[0].lower().rstrip(":").strip()
                valor = textos[1].strip()

                if not valor or len(valor) < 2:
                    continue
                # Filtrar valores que claramente son del usuario logueado
                if valor in ("Usuario Acciones", "MARIA GREIDY", "1075209386"):
                    continue

                if label in ("empresa", "razon social", "razón social", "empleador"):
                    datos["empresa"] = valor
                elif label in ("nit", "nit empresa"):
                    datos["nit"] = valor
                elif label in ("cargo", "cargo asegurado", "ocupación", "ocupacion"):
                    datos["cargo_asegurado"] = valor
                elif label in ("eps", "eps del trabajador"):
                    datos["eps"] = valor
                elif label in ("afp", "fondo de pensiones"):
                    datos["afp"] = valor
                elif label in ("tipo de vinculación", "tipo vinculacion", "tipo contrato"):
                    datos["tipo_vinculacion"] = valor
                elif label in ("salario", "ibc"):
                    datos["salario"] = valor

    # 3. Fallback: si tabla vacía, intentar leer labels con locator semántico
    if not datos.get("empresa"):
        try:
            # Buscar "Empresa:" como texto label seguido de su valor en el DOM
            empresa_label = page.locator("td:has-text('Empresa'), th:has-text('Empresa'), label:has-text('Empresa')").first
            if await empresa_label.count() > 0:
                # El valor suele estar en el siguiente hermano o celda
                empresa_valor = await page.evaluate("""(el) => {
                    const next = el.nextElementSibling;
                    return next ? next.textContent.trim() : '';
                }""", await empresa_label.element_handle())
                if empresa_valor and empresa_valor not in ("Usuario Acciones", "MARIA GREIDY"):
                    datos["empresa"] = empresa_valor
        except Exception:
            pass

    return datos
```

### FIX P-2 + P-3: Detección dinámica de columnas + detalle de siniestro

**El bug raíz:** Las columnas están hardcodeadas. El detalle del siniestro (CIE-10 completo, segmento corporal, PCL exacto) solo está en la página de detalle, no en la tabla.

**Código completo para `_extraer_siniestros_tabla`** — reemplazar completamente:

```python
async def _extraer_siniestros_tabla(page: Page) -> list:
    """
    Extrae siniestros leyendo headers de tabla para detectar columnas dinámicamente.
    Para cada siniestro, abre la página de detalle y extrae datos completos.
    """
    from backend.playwright_real.session import capturar_screenshot_error
    siniestros = []

    # 1. Navegar a la pestaña SINIESTROS
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

    # 2. Esperar que cargue la tabla
    try:
        await page.wait_for_selector("table tbody tr", timeout=10000)
    except Exception:
        await capturar_screenshot_error(page, "positiva", "siniestros_tabla_no_carga")

    # 3. Detectar columnas por headers de tabla
    col_map = {}  # "nombre_campo" → índice 0-based
    try:
        headers = await page.query_selector_all("table thead th, table tr:first-child th, table tr:first-child td")
        for i, h in enumerate(headers):
            texto = (await h.text_content() or "").strip().lower()
            if any(kw in texto for kw in ["siniestro", "no.", "número", "numero"]):
                col_map["siniestro"] = i
            elif any(kw in texto for kw in ["fecha", "ocurrencia"]):
                if "siniestro" not in col_map or i != col_map.get("siniestro"):
                    col_map["fecha"] = i
            elif any(kw in texto for kw in ["tipo", "evento", "clase"]):
                col_map["tipo"] = i
            elif any(kw in texto for kw in ["diagnóstico", "diagnostico", "cie", "dx"]):
                col_map["diagnostico"] = i
            elif "pcl" in texto or "pérdida" in texto or "perdida" in texto:
                col_map["pcl"] = i
            elif any(kw in texto for kw in ["estado", "estatus"]):
                col_map["estado"] = i
    except Exception:
        pass

    # Defaults si no se detectaron headers (fallback a valores conocidos)
    col_map.setdefault("siniestro", 0)
    col_map.setdefault("fecha", 1)
    col_map.setdefault("tipo", 2)
    col_map.setdefault("diagnostico", 7)

    # 4. Leer filas con columnas detectadas
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

            def get_celda(col_name: str, default_idx: int = -1) -> str:
                idx = col_map.get(col_name, default_idx)
                if idx < 0 or idx >= len(celdas):
                    return ""
                # No podemos usar await aquí directamente, se resuelve afuera
                return idx

            # Extraer texto de celdas clave
            idx_sin = col_map.get("siniestro", 0)
            idx_fecha = col_map.get("fecha", 1)
            idx_tipo = col_map.get("tipo", 2)
            idx_dx = col_map.get("diagnostico", 7)

            sin_id = (await celdas[idx_sin].text_content() or "").strip() if idx_sin < len(celdas) else ""
            fecha = (await celdas[idx_fecha].text_content() or "").strip() if idx_fecha < len(celdas) else ""
            tipo = (await celdas[idx_tipo].text_content() or "").strip() if idx_tipo < len(celdas) else ""
            diagnostico = (await celdas[idx_dx].text_content() or "").strip() if idx_dx < len(celdas) else ""

            # Validar que sea un siniestro real (número >= 7 dígitos)
            sin_limpio = re.sub(r'\D', '', sin_id)
            if not sin_limpio or len(sin_limpio) < 7:
                continue

            siniestro = {
                "id": sin_limpio,
                "fecha": fecha,
                "tipo": tipo,
                "diagnostico": diagnostico,
            }

            # 5. Abrir detalle del siniestro para datos completos
            try:
                link = await fila.query_selector("a[href]")
                if link:
                    href = await link.get_attribute("href") or ""
                    await link.click()
                    await page.wait_for_timeout(5000)
                    detalle_body = await page.text_content("body") or ""

                    # Extraer CIE-10 del detalle
                    cie10_matches = re.findall(r'([A-Z]\d{2,3}(?:\.\d)?)\s*[-–]\s*([A-Za-záéíóúñ\s,\.]{5,80})', detalle_body)
                    if cie10_matches:
                        siniestro["diagnosticos_detalle"] = [
                            {"codigo": m[0], "descripcion": m[1].strip()}
                            for m in cie10_matches[:3]
                        ]

                    # Extraer segmento corporal
                    seg_match = re.search(r'(?:segmento|región|zona)[:\s]+([A-Za-záéíóúñ\s,]+?)(?:\n|\.)', detalle_body, re.IGNORECASE)
                    if seg_match:
                        siniestro["segmento"] = seg_match.group(1).strip()

                    # Extraer PCL
                    pcl_match = re.search(r'PCL[:\s]+(\d+(?:\.\d+)?)\s*%', detalle_body, re.IGNORECASE)
                    if pcl_match:
                        siniestro["pcl"] = pcl_match.group(1) + "%"

                    # Extraer fecha exacta del siniestro
                    fecha_match = re.search(r'[Ff]echa\s+[Ss]iniestro[:\s]+(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})', detalle_body)
                    if fecha_match:
                        siniestro["fecha_siniestro_exacta"] = fecha_match.group(1)

                    # Volver a la lista de siniestros
                    await page.go_back()
                    await page.wait_for_timeout(3000)
                    # Re-hacer click en pestaña siniestros por si volvió al inicio
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
                pass  # Detalle falló, igual guardamos datos básicos de la tabla

            siniestros.append(siniestro)
        except Exception:
            continue

    # 6. Fallback: número de siniestro en body si tabla vacía
    if not siniestros:
        body = await page.text_content("body") or ""
        match = re.search(r'\b(5\d{8})\b', body)
        if match:
            siniestros = [{"id": match.group(1), "fecha": "", "tipo": "AT", "_fuente": "regex_fallback"}]

    return siniestros
```

### FIX P-4: Navegar TODAS las pestañas de Positiva

Agregar función `_extraer_rehab_integral`:

```python
async def _extraer_rehab_integral(page: Page) -> Dict:
    """
    Navega a REHABILITACIÓN INTEGRAL y extrae estado actual del proceso.
    """
    datos = {}
    try:
        for selector in [
            "a:has-text('REHABILITACIÓN INTEGRAL')",
            "a:has-text('Rehabilitación Integral')",
            "a:has-text('REHABILITACION INTEGRAL')",
        ]:
            tab = page.locator(selector).first
            if await tab.count() > 0:
                await tab.click()
                await page.wait_for_timeout(4000)
                break

        body = await page.text_content("body") or ""

        # Estado del proceso
        estado_match = re.search(r'[Ee]stado[:\s]+([A-Za-záéíóúñ\s]+?)(?:\n|,|\|)', body)
        if estado_match:
            datos["estado_rehab"] = estado_match.group(1).strip()

        # Fechas de tratamiento
        fechas = re.findall(r'\d{2}/\d{2}/\d{4}', body)
        if fechas:
            datos["fechas_rehab"] = fechas[:5]

        # Tipo de intervención
        interv_match = re.search(r'(?:Intervenci[oó]n|Tipo)[:\s]+([A-Za-záéíóúñ\s]+?)(?:\n|,)', body, re.IGNORECASE)
        if interv_match:
            datos["tipo_intervencion"] = interv_match.group(1).strip()

    except Exception:
        pass
    return datos
```

Agregar función `_extraer_autorizaciones`:

```python
async def _extraer_autorizaciones(page: Page) -> list:
    """
    Navega a GESTIÓN AUTORIZACIONES y extrae autorizaciones activas.
    """
    autorizaciones = []
    try:
        for selector in [
            "a:has-text('GESTIÓN AUTORIZACIONES')",
            "a:has-text('Gestión Autorizaciones')",
            "a:has-text('GESTION AUTORIZACIONES')",
        ]:
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
```

### FIX P-5: RHI — extracción completa

**Código completo para `_buscar_en_rhi`** — reemplazar completamente:

```python
async def _buscar_en_rhi(page: Page, cc: str) -> Dict:
    """
    Busca en RHI Consultar Caso. Extrae siniestro confirmado, diagnóstico,
    plan de manejo, fechas de tratamiento.
    """
    rhi = {}
    try:
        await page.goto("https://positivacuida.positiva.gov.co/web/rhi/consultarCaso/init", timeout=30000)
        await page.wait_for_timeout(5000)

        # Llenar CC
        for selector_cc in ["#numeroDocumento", "input[name='numeroDocumento']", "input[placeholder*='documento']"]:
            try:
                doc_input = await page.wait_for_selector(selector_cc, timeout=3000)
                await doc_input.fill(cc)
                break
            except Exception:
                continue

        # Buscar
        for b in await page.query_selector_all("button"):
            t = (await b.text_content() or "").strip().lower()
            if "buscar" in t or "consultar" in t:
                await b.click()
                break
        else:
            await page.keyboard.press("Enter")

        await page.wait_for_timeout(8000)
        body = await page.text_content("body") or ""

        # Matrícula RHI
        matriculas = re.findall(r"[Mm]atr[ií]cula[:\s]*(\d+)", body)
        if matriculas:
            rhi["matricula"] = matriculas[0]

        # Número de siniestro en RHI (más confiable que Consulta Integral)
        sin_match = re.search(r'\b(5\d{8})\b', body)
        if sin_match:
            rhi["siniestro_rhi"] = sin_match.group(1)

        # Diagnóstico CIE-10
        cie10 = re.findall(r'\b([A-Z]\d{2,3}(?:\.\d)?)\b\s*[-–]?\s*([A-Za-záéíóúñ\s,\.]{5,60})?', body)
        if cie10:
            rhi["diagnosticos_rhi"] = [
                {"codigo": m[0], "descripcion": (m[1] or "").strip()}
                for m in cie10[:3]
            ]

        # Fechas de atención
        fechas = re.findall(r"\d{2}/\d{2}/\d{4}", body)
        if fechas:
            rhi["fechas_encontradas"] = list(dict.fromkeys(fechas))[:8]  # deduplicar

        # Plan de manejo
        plan_match = re.search(r'[Pp]lan[:\s]+(.{30,300}?)(?:\n\n|\.\s)', body, re.DOTALL)
        if plan_match:
            rhi["plan_manejo"] = plan_match.group(1).strip()[:300]

        # Estado del caso
        estado_match = re.search(r'[Ee]stado[:\s]+([A-Za-záéíóúñ\s]+?)(?:\n|,)', body)
        if estado_match:
            rhi["estado_caso"] = estado_match.group(1).strip()

    except Exception as e:
        return {"_error": f"RHI no disponible: {e}", "_rhi_ok": False}

    rhi["_rhi_ok"] = bool(rhi.get("siniestro_rhi") or rhi.get("matricula"))
    return rhi
```

### Actualizar `get_paciente_completo` en positiva.py

```python
async def get_paciente_completo(page: Page, cc: str) -> Dict:
    datos = {"cc_buscado": cc, "fuente": "positiva"}

    encontrado = await _buscar_en_consulta_integral(page, cc)
    if not encontrado:
        datos["_sin_datos_clinicos"] = True
        datos["_advertencia"] = "Paciente no encontrado en Consulta Integral de Positiva"
        datos["error_busqueda"] = "Paciente no encontrado en Consulta Integral"
        return datos

    # Extraer datos visibles generales
    visible = await _extraer_datos_visibles(page)
    datos.update(visible)

    # Navegar DATOS ASEGURADO (empresa, cargo, NIT — parse por celdas)
    datos_asegurado = await _extraer_datos_asegurado(page)
    if datos_asegurado:
        datos["datos_asegurado"] = datos_asegurado

    # Navegar SINIESTROS con detección dinámica + detalle por siniestro
    siniestros = await _extraer_siniestros_tabla(page)
    if siniestros:
        datos["siniestros"] = siniestros
        datos["siniestro_id"] = siniestros[0]["id"]

    # Navegar REHABILITACIÓN INTEGRAL
    rehab = await _extraer_rehab_integral(page)
    if rehab:
        datos["rehabilitacion"] = rehab

    # Navegar GESTIÓN AUTORIZACIONES
    autorizaciones = await _extraer_autorizaciones(page)
    if autorizaciones:
        datos["autorizaciones"] = autorizaciones

    # RHI solo si no se encontró CIE-10 en las pestañas anteriores
    tiene_cie10 = (
        datos.get("diagnosticos") or
        datos.get("cie10_candidatos") or
        any(s.get("diagnosticos_detalle") for s in siniestros if isinstance(s, dict))
    )
    if not tiene_cie10:
        rhi_data = await _buscar_en_rhi(page, cc)
        datos["rhi"] = rhi_data

    # Verificación de datos mínimos
    campos_criticos = ["siniestro_id", "datos_asegurado"]
    datos["_campos_extraidos_pos"] = [c for c in campos_criticos if datos.get(c)]
    datos["_completo_pos"] = bool(datos.get("siniestro_id"))

    return datos
```

---

## PARTE 4 — selectores.py: agregar selectores faltantes

Agregar al final de `selectores.py`:

```python
# ═══════════════════════════════════════════════════════════════════════
# MEDIFOLIOS — Historia Clínica
# ═══════════════════════════════════════════════════════════════════════

MEDI_HC = {
    "urls_posibles": [
        "https://www.server0medifolios.net/index.php/SALUD_HOME/historia_clinica",
        "https://www.server0medifolios.net/index.php/SALUD_HISTORIA/historia",
    ],
    "menu_hc": "a:has-text('Historia Clínica'), a:has-text('Historia clinica'), a:has-text('HC')",
    "tabla_dx": "table:has(th:has-text('Diagnóstico')), table:has(th:has-text('CIE'))",
    "input_cc_hc": "#numero_id, input[name='cc'], input[name='numero_id']",
}

MEDI_AGENDA_DETALLE = {
    "selector_filas": "table.tabla-agenda tbody tr, table tbody tr",
    "campo_observaciones": [
        "textarea[name='observaciones']",
        "#observaciones",
        "textarea:near(:text('Observaciones'))",
        ".modal textarea",
        "[class*='detalle'] textarea",
    ],
    "boton_cerrar_modal": "button:has-text('Cerrar'), button:has-text('Close'), .modal .close, .btn-close",
}

# ═══════════════════════════════════════════════════════════════════════
# ARL POSITIVA — Secciones adicionales
# ═══════════════════════════════════════════════════════════════════════

POS_REHAB_INTEGRAL = {
    "tab": [
        "a:has-text('REHABILITACIÓN INTEGRAL')",
        "a:has-text('Rehabilitación Integral')",
        "a:has-text('REHABILITACION INTEGRAL')",
    ],
}

POS_AUTORIZACIONES = {
    "tab": [
        "a:has-text('GESTIÓN AUTORIZACIONES')",
        "a:has-text('Gestión Autorizaciones')",
    ],
}

POS_RHI_COMPLETO = {
    "url": "https://positivacuida.positiva.gov.co/web/rhi/consultarCaso/init",
    "input_cc": "#numeroDocumento, input[name='numeroDocumento']",
    "buscar": "button:has-text('Buscar'), button:has-text('Consultar')",
}

# Screenshot debug dir
PLAYWRIGHT_DEBUG_DIR = "./storage/playwright_debug"
```

---

## PARTE 5 — sintetizar_maestro.py: pasar todos los datos al LLM

**Este fix es CRÍTICO.** La función `_formatear_portales` que arma el contexto para el LLM actualmente omite campos clave. OpenCode debe modificarla para incluir:

```python
# Datos que DEBEN llegar al LLM (agregar a _formatear_portales):
# - medifolios["fecha_nacimiento"] → pac.fecha_nacimiento
# - medifolios["eps_ips"]          → pac.eps
# - medifolios["afp"]              → pac.afp
# - positiva["datos_asegurado"]["empresa"]    → empresa empleadora
# - positiva["datos_asegurado"]["cargo_asegurado"] → cargo actual
# - positiva["datos_asegurado"]["nit"]        → NIT empresa
# - positiva["siniestros"][0]["fecha_siniestro_exacta"]  → fecha exacta
# - positiva["siniestros"][0]["diagnosticos_detalle"]    → CIE-10 completo
# - positiva["siniestros"][0]["segmento"]     → segmento corporal
# - positiva["rehabilitacion"]["estado_rehab"] → estado actual rehab
```

En `_formatear_portales`, cambiar la sección de empresa/cargo para usar el nuevo campo:
```python
# ANTES (INCORRECTO):
empresa = pos.get("datos_asegurado", {}).get("empresa", "")
# DESPUÉS (CORRECTO — usa datos parseados por celdas, no regex):
empresa = pos.get("datos_asegurado", {}).get("empresa", "")
cargo = pos.get("datos_asegurado", {}).get("cargo_asegurado", "")
nit = pos.get("datos_asegurado", {}).get("nit", "")
# Y agregar al string de contexto que se pasa al LLM
```

---

## Resumen de cambios

| Fix | Archivo | Impacto |
|-----|---------|---------|
| X-1 Screenshot error | session.py | Debug visual cuando falla extracción |
| X-2 Retry helper | session.py | Resiliencia ante timeouts de red |
| M-1+M-2 Agenda profunda | medifolios.py | Encuentra siniestro en observaciones de citas individuales |
| M-3 Historia Clínica | medifolios.py | Diagnósticos CIE-10 de Medifolios |
| P-1 Datos asegurado tabla | positiva.py | Elimina bug "Usuario Acciones", extrae empresa real |
| P-2 Columnas dinámicas | positiva.py | No se rompe si portal reordena columnas |
| P-3 Detalle siniestro | positiva.py | CIE-10 completo, segmento corporal, PCL exacto |
| P-4 Rehab + Autorizaciones | positiva.py | 2 pestañas más extraídas |
| P-5 RHI completo | positiva.py | Siniestro confirmado, diagnóstico, plan |
| S-1 Selectores nuevos | selectores.py | HC Medifolios, debug dir, Positiva tabs |
| LLM-1 Contexto completo | sintetizar_maestro.py | Empresa, cargo, NIT, CIE-10, segmento al LLM |

**Estimado OpenCode:** ~90 minutos  
**Prioridad de ejecución:** P-1 primero (bug empresa), luego M-1+M-2 (siniestro agenda), luego P-2+P-3 (siniestros completos), luego el resto.
