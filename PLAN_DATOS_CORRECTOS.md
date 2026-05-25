# RILO SAS — Plan de Datos Correctos (Diagnóstico Forense)

> Auditoría basada en el caso real: CC 36280228 (Maribel Puentes Medina).
> El sistema generó documentos con datos incorrectos a pesar de que Positiva y el workspace
> de Sandra tenían toda la información correcta. Este plan explica por qué y cómo arreglarlo.

---

## Qué pasó exactamente con CC 36280228

**Datos reales de Sandra (de su CR manual):**
- Empresa: **Alcaldía Municipal de Pitalito**
- Cargo: **Técnica Administrativa**
- Tipo siniestro: **Enfermedad Laboral** (no accidente de trabajo)
- Fecha evento: **23/05/2025**
- Segmento: **Codos, muñeca y manos** (por uso de computador repetitivo)
- Siniestro: desconocido (Sandra lo sabe, está en el portal de Positiva)

**Lo que generó el sistema:**
- Empresa: "Alcaldía Municipal de **Pitarentos**" ← error de transcripción acústica
- Cargo actual: "**Obrero de tratamiento roca**" ← del historial laboral anterior, no del cargo actual
- Historia laboral: BOLIVARIANA DE MINERALES, EJÉRCITO NACIONAL ← puede ser correcto como historial previo
- Diagnóstico probable: G56.0 (nervio mediano) ← plausible pero no verificado
- Positiva: **0 datos clínicos extraídos** — siniestro, fecha, tipo, diagnóstico: todos vacíos
- EPS/AFP: [FALTA] — Medifolios los tiene pero el sistema no los extrae (bug N-1)

**Cadena causal del error:**
```
Positiva vacía (falla extractora)
    → LLM solo tiene el audio como fuente clínica
    → Audio menciona historial laboral previo (Bolivariana de Minerales)
    → LLM rellena "proceso_productivo" y "tareas_criticas" con ese historial
    → doc_generator pone eso en sección 4 "Descripción Actividad Laboral Actual"
    → Documentos con cargo y tareas del trabajo ANTERIOR, no del actual
    → Empresa con typo "Pitarentos" porque transcripción Deepgram confundió el audio
    → Ningún dato de Positiva pudo corregir esto porque el extractor retornó vacío
```

---

## FALLA 1 — Positiva: búsqueda sin verificar resultado → extractor retorna vacío silenciosamente

**Archivo:** `backend/playwright_real/positiva.py` líneas 15–37

```python
async def _buscar_en_consulta_integral(page: Page, cc: str) -> bool:
    ...
    await page.wait_for_timeout(8000)
    return True  # ← Siempre retorna True aunque el paciente no se encontró
```

La función retorna `True` sin verificar si la búsqueda devolvió resultados. Si el portal muestra "No se encontraron resultados" o un error, `encontrado = True` igualmente y la extracción procede sobre una página vacía de resultados.

Para CC 36280228, Sandra tiene el archivo `MARIBEL PUENTES MEDINA__._.pdf` descargado de Positiva — el paciente SÍ existe en el portal — pero el extractor no pudo leer los datos porque no verificó si la búsqueda fue exitosa.

**Fix — verificar resultado antes de continuar:**
```python
async def _buscar_en_consulta_integral(page: Page, cc: str) -> bool:
    ...
    await page.wait_for_timeout(8000)
    # Verificar que hay resultados (el CC aparece en la página)
    body = await page.text_content("body") or ""
    # Si el portal muestra el CC en la tabla de resultados, la búsqueda funcionó
    if cc in body:
        return True
    # Intentar con XPath si hay mensaje de error visible
    error_msgs = ["no se encontró", "sin resultados", "no results", "0 registros"]
    body_lower = body.lower()
    if any(msg in body_lower for msg in error_msgs):
        return False
    # Por defecto: asumir que hay algo (puede ser vacío pero no error explícito)
    return True
```

**Además**, en `get_paciente_completo` de `positiva.py`, marcar como parcial si no se extrajo ningún dato clínico:
```python
# Al final de get_paciente_completo, antes de return datos:
datos_clinicos_extraidos = bool(
    datos.get("siniestros") or datos.get("siniestro_id") or
    datos.get("diagnosticos") or datos.get("cie10_candidatos") or
    datos.get("fecha_siniestro")
)
if not datos_clinicos_extraidos:
    datos["_sin_datos_clinicos"] = True
    datos["_advertencia"] = "Positiva no retornó siniestros ni diagnóstico — verificar manualmente"
```

---

## FALLA 2 — `_meta.parcial: false` incorrecto cuando Positiva retorna sin datos clínicos

**Archivo:** `backend/playwright_real/orquestador.py` líneas 151–161

```python
fusionado = {
    ...
    "_meta": {
        ...
        "parcial": bool(datos_medi.get("error") or datos_pos.get("error")),
        #          ↑ Solo marca parcial si hay error EXPLÍCITO
    },
}
```

Para CC 36280228: `datos_pos` no tiene `"error"` key, tiene `{"texto_completo_len": 9148, "rhi": {...}}`. Entonces `parcial = False` aunque Positiva no extrajo ningún dato clínico útil.

Consecuencia: `verificar_portales` y `sintetizar_maestro` reciben `parcial: False` y asumen que los datos son completos. No disparan advertencias ni pausas.

**Fix:**
```python
# Verificar que Positiva tiene datos clínicos reales
pos_tiene_datos = bool(
    datos_pos.get("siniestros") or datos_pos.get("siniestro_id") or
    datos_pos.get("diagnosticos") or datos_pos.get("cie10_candidatos") or
    datos_pos.get("fecha_siniestro")
)
medi_tiene_datos = bool(
    datos_medi.get("nombre1") or datos_medi.get("nombre")
)

parcial = (
    bool(datos_medi.get("error") or datos_pos.get("error")) or
    not pos_tiene_datos or  # Positiva sin datos clínicos = parcial
    not medi_tiene_datos    # Medifolios sin nombre = parcial
)

fusionado["_meta"]["parcial"] = parcial
if not pos_tiene_datos:
    fusionado["_meta"]["pos_sin_datos"] = True
    fusionado["_meta"]["advertencia_portales"] = "Positiva no devolvió siniestros ni diagnóstico"
```

---

## FALLA 3 — `leer_notas_crudas` no detecta CC en tablas de DOCX — ignora documentos existentes de Sandra

**Archivo:** `backend/workflow_steps/leer_notas_crudas.py` líneas 96–101

```python
contenido = _leer_texto(path, max_chars=500)  # Solo 500 chars
cc_norm = cc.replace(".","").replace("-","").replace("\x27","")
contenido_limpio = contenido.replace(".","").replace("-","").replace("\x27","")
if cc_norm in contenido_limpio:
```

Y `_leer_texto` para DOCX (línea 27):
```python
text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
```

**Doble bug:** Solo lee párrafos (no tablas) y solo los primeros 500 chars.

Los documentos clínicos de RILO (VOI, CR, CC) guardan el número de documento en la **Tabla 1** de identificación, no en párrafos. Los 500 chars de párrafos son el encabezado, fecha y título del objetivo — nunca llegan al CC en la tabla.

Para el caso de Maribel: Sandra tiene `VOI_MARIBEL PUENTES MEDINA.docx`, `CR_MARIBEL PUENTES MEDINA_TECNICA ADMINISTRATIVA_ALCALDIA MUNICIPAL DE PITALITO.docx` y `CC_ MARIBEL PUENTES MEDINA.docx` en su workspace. Ninguno fue detectado aunque tienen todo el contexto clínico correcto. Si el LLM hubiera visto el CR, habría sabido:
- Cargo: Técnica Administrativa
- Empresa: Alcaldía Municipal de Pitalito (exacto, sin typo)
- Tipo siniestro: Enfermedad Laboral
- Fecha evento: 23/05/2025
- Segmento: Codos, muñeca y manos

**Fix — buscar CC en tablas también, ampliar búsqueda:**
```python
def _leer_texto(path: Path, max_chars: int = 2000) -> str:
    if path.suffix.lower() in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    if path.suffix.lower() == ".docx":
        from docx import Document
        doc = Document(str(path))
        partes = []
        for p in doc.paragraphs:
            if p.text.strip():
                partes.append(p.text.strip())
        # CRÍTICO: incluir texto de tablas
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    t = cell.text.strip()
                    if t:
                        partes.append(t)
        return "\n".join(partes)[:max_chars]
    return ""

def _tiene_cc(path: Path, cc: str) -> bool:
    """Verifica si un archivo contiene la CC (nombre o contenido completo)."""
    cc_norm = cc.replace(".","").replace("-","").replace("'","")
    # Primero: nombre del archivo
    if cc_norm in path.name.replace(".","").replace("-",""):
        return True
    # Segundo: contenido completo hasta 3000 chars
    contenido = _leer_texto(path, max_chars=3000)
    contenido_limpio = contenido.replace(".","").replace("-","").replace("'","").replace(" ","")
    return cc_norm in contenido_limpio
```

**Impacto directo:** Si el sistema hubiera leído el CR de Maribel antes de la síntesis, habría tenido todos los datos correctos y no habría inventado "Pitarentos" ni el cargo de obrero.

---

## FALLA 4 — El workflow no pausa cuando la verificación de portales es insuficiente

**Archivo:** `backend/workflow_steps/verificar_portales.py` líneas 194–211

El resultado del workflow para Maribel fue:
```json
"verificacion": {
    "confirmados": 4,
    "pendientes_portal": 8,
    "discrepancias": 1,
    "faltantes": 1
}
```

Estado: `"listo"` — a pesar de que:
- Siniestro: **discrepancia** (síntesis dice 503375273, portal dice [VERIFICAR])
- Empresa, cargo, diagnóstico, fecha, EPS, AFP, tipo: **todos "pendientes_portal"** (Positiva vacía)

La lógica actual en `verificar_portales`:
```python
ok = resumen["discrepancias"] == 0 and resumen["faltantes"] <= 3
```

Con 8 campos "pendientes_portal" y 1 discrepancia en el siniestro, `ok = False`. Pero `workflow_runner` solo chequea `ok` para `transcribir`, `sintetizar_maestro`, `generar_formatos`, `convertir_pdf` — **NO para `verificar_portales`**. El workflow continúa sin importar el `ok` de la verificación.

**Fix en `workflow_runner.py`:**
```python
if step_name == "verificar_portales":
    verif = resultado_step
    pendientes = verif.get("resumen", {}).get("pendientes_portal", 0)
    discrepancias = verif.get("resumen", {}).get("discrepancias", 0)
    total = verif.get("resumen", {}).get("total", 1)
    # Si más del 50% de campos están sin verificar, requerir confirmación
    if pendientes > total * 0.5 or discrepancias >= 2:
        contexto["_requiere_confirmacion"] = True
        contexto["_requiere_confirmacion_motivo"] = (
            f"Positiva no devolvió datos ({pendientes} campos sin verificar, "
            f"{discrepancias} discrepancia(s)). "
            f"Los documentos pueden tener información incorrecta."
        )
        _log(f"ADVERTENCIA: verificación incompleta — se requiere confirmación de Sandra")
```

Así el workflow completa (genera documentos) pero el estado final es `"listo_con_advertencias"` y Sandra recibe la alerta por Telegram antes de usar los documentos.

---

## FALLA 5 — La síntesis mezcla historia laboral PREVIA con el cargo ACTUAL

**Archivo:** `backend/workflow_steps/sintetizar_maestro.py` líneas 100–136 (prompt)

El prompt de síntesis pide:
```
"proceso_productivo": "...",
"apreciacion_trabajador": "...",
"tareas_criticas": [{"tarea":"...","observacion":"...","desempeno":"..."}],
```

Sin instrucción explícita de que estos campos deben ser del **cargo actual**. Cuando el audio menciona historial laboral (trabajos anteriores), el LLM puede llenar `proceso_productivo` con el trabajo anterior y `tareas_criticas` con las tareas de ese trabajo.

Para Maribel: el audio probablemente mencionó "antes trabajé en Bolivariana de Minerales" y el LLM lo interpretó como el trabajo actual al llenar `proceso_productivo` y `tareas_criticas`. El `empresa.cargo` sí quedó correcto ("Técnica Administrativa") pero el proceso productivo y las tareas críticas son del trabajo anterior.

**Fix — clarificar en el prompt:**
```
REGLAS ADICIONALES:
- "proceso_productivo", "tareas_criticas", "apreciacion_trabajador": SOLO del cargo actual
  (empresa.nombre + empresa.cargo). Si el audio menciona trabajos anteriores, ponlos 
  en "metodologia" como historia laboral, NO en tareas_criticas.
- Si hay contradicción entre el proceso_productivo y el empresa.cargo, resolver a favor
  del empresa.cargo (es el cargo oficial en el sistema de riesgos laborales).
- Si una tarea no corresponde al cargo actual, omitirla o marcarla como historial previo.
```

---

## FALLA 6 — Positiva: pestaña SINIESTROS puede no cargarse antes de leer la tabla

**Archivo:** `backend/playwright_real/positiva.py` líneas 83–122

En `_extraer_siniestros_tabla`, después de hacer click en la pestaña SINIESTROS:
```python
await page.wait_for_timeout(5000)  # espera fija de 5s
```

Si el portal tarda más de 5s en cargar la tabla (carga AJAX), el extractor lee una tabla vacía. Luego:
```python
filas = await page.query_selector_all(S.POS_TABLA_SINIESTROS["filas"])
# S.POS_TABLA_SINIESTROS["filas"] = "table.siniestros tbody tr, [data-tab='siniestros'] tbody tr"
```

Si la tabla se llama diferente (sin clase `.siniestros`), no se encuentra. Para CC 36280228 con `texto_completo_len: 9148` (página con contenido), el problema es que los selectores CSS no hacen match con la tabla real de Positiva.

**Fix — espera dinámica + selectores alternativos:**
```python
# Esperar a que aparezca alguna tabla con contenido en lugar de timeout fijo
try:
    await page.wait_for_selector("table tbody tr", timeout=10000)
except Exception:
    pass

# Intentar con múltiples estrategias para encontrar la tabla
selectores_tabla = [
    "table.siniestros tbody tr",
    "[data-tab='siniestros'] tbody tr",
    "table tbody tr",  # cualquier tabla
    "#siniestros tbody tr",
    ".siniestros-table tbody tr",
]
filas = []
for sel in selectores_tabla:
    filas = await page.query_selector_all(sel)
    if filas:
        break
```

**Fix adicional — extraer del texto visible si la tabla falla:**
Si la tabla no se puede parsear pero el body tiene el número de siniestro, extraerlo con regex como última opción:
```python
if not siniestros:
    # Fallback: buscar número de siniestro en el texto de la página
    body = await page.text_content("body") or ""
    siniestro_match = re.search(r'\b(5\d{8})\b', body)  # Siniestros Positiva empiezan con 5
    if siniestro_match:
        siniestros = [{"id": siniestro_match.group(1), "fecha": "", "tipo": "AT"}]
```

---

## FALLA 7 — El extractor de Positiva no lee los datos del asegurado (nombre, empresa, cargo)

**Archivo:** `backend/playwright_real/positiva.py` + `backend/playwright_real/selectores.py`

`POS_TABS["datos_asegurado"] = "a:has-text('DATOS ASEGURADO'), [data-tab='datos']"` está definido pero **nunca se hace click en esta pestaña ni se extraen sus datos**.

La pestaña "DATOS ASEGURADO" de Positiva contiene: nombre completo oficial, empresa, NIT, cargo, EPS, AFP — exactamente los datos que están fallando.

`orquestador.py` línea 70 intenta leer `datos_pos.get("datos_asegurado", {}).get("nombre", "")` pero nunca se navega a esa pestaña.

**Fix — agregar extracción de la pestaña DATOS ASEGURADO:**
```python
async def _extraer_datos_asegurado(page: Page) -> dict:
    """Extrae datos de la pestaña DATOS ASEGURADO en Positiva."""
    try:
        tab = page.locator(S.POS_TABS["datos_asegurado"])
        if await tab.count() > 0:
            await tab.first.click()
            await page.wait_for_timeout(4000)
    except Exception:
        pass
    
    body = await page.text_content("body") or ""
    datos = {}
    
    # Empresa
    empresa_match = re.search(r"[Ee]mpresa[:\s]+([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ\s,\.]+?)(?:\n|CC|NIT|\d{5})", body)
    if empresa_match:
        datos["empresa"] = empresa_match.group(1).strip()
    
    # NIT
    nit_match = re.search(r"NIT[:\s]*(\d{6,12}[-]?\d?)", body)
    if nit_match:
        datos["nit"] = nit_match.group(1)
    
    # Cargo
    cargo_match = re.search(r"[Cc]argo[:\s]+([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ\s]+?)(?:\n|CC|$)", body)
    if cargo_match:
        datos["cargo_asegurado"] = cargo_match.group(1).strip()
    
    return datos
```

Y llamarlo en `get_paciente_completo` después de la búsqueda inicial.

---

## FALLA 8 — El nombre de empresa con error de transcripción no se detecta

**"Alcaldía Municipal de Pitarentos"** (transcripción Deepgram de "Pitalito") pasa sin ninguna advertencia.

"Pitalito" es un municipio de Colombia. Deepgram lo transcribió como "Pitarentos" (error fonético). El LLM mantuvo el error.

El sistema no tiene ningún mecanismo para:
1. Verificar que el nombre de empresa es un municipio/empresa real
2. Detectar que el nombre de empresa en el audio difiere del nombre en el portal de Positiva

**Fix — cruzar empresa del audio con empresa del portal:**

Si Positiva extrae `datos_asegurado.empresa` y la síntesis extrae `empresa.nombre`, cruzarlos:
```python
# En verificar_portales o sintetizar_maestro:
empresa_portal = pos.get("datos_asegurado", {}).get("empresa", "")
empresa_sintesis = datos_clinicos.get("empresa", {}).get("nombre", "")

if empresa_portal and empresa_sintesis:
    simil = _similitud_palabras(_normalizar(empresa_portal), _normalizar(empresa_sintesis))
    if simil < 0.4:  # menos del 40% de palabras en común
        advertencias.append(
            f"Nombre de empresa en audio ('{empresa_sintesis}') difiere del portal "
            f"('{empresa_portal}'). Verificar nombre correcto."
        )
        # Usar el portal como fuente oficial
        datos_clinicos["empresa"]["nombre"] = empresa_portal
```

---

## FALLA 9 — `_formatear_portales` no incluye empresa, tipo de evento ni segmento corporal

**Archivo:** `backend/workflow_steps/sintetizar_maestro.py` líneas 29–49

El formatter actual pasa al LLM:
- Nombre del paciente
- Teléfono
- Dirección
- Siniestro (Medifolios)
- Siniestros de Positiva (id, fecha, diagnóstico)

**NO incluye (pero los portales los tienen cuando funcionan):**
- Empresa / empleador
- Cargo
- Tipo de evento (accidente laboral vs enfermedad laboral)
- Segmento corporal afectado
- EPS / AFP
- Fecha del evento

Si se incluyen estos en el formatter, el LLM los usa como ancla y no necesita inventarlos del audio.

**Fix — ampliar `_formatear_portales`:**
```python
def _formatear_portales(datos: dict) -> str:
    ...
    if medi:
        ...
        if medi.get("eps_ips"):  bloques.append(f"  EPS: {medi['eps_ips']}")
        if medi.get("afp"):      bloques.append(f"  AFP: {medi['afp']}")
        if medi.get("empresa"):  bloques.append(f"  Empresa (Medi): {medi['empresa']}")
    
    if pos:
        asegurado = pos.get("datos_asegurado", {})
        if asegurado.get("empresa"):  bloques.append(f"  Empresa (Pos): {asegurado['empresa']}")
        if asegurado.get("cargo_asegurado"): bloques.append(f"  Cargo (Pos): {asegurado['cargo_asegurado']}")
        if asegurado.get("nit"):      bloques.append(f"  NIT empresa: {asegurado['nit']}")
        
        for s in pos.get("siniestros", [])[:2]:
            tipo = s.get("tipo", "")
            seg = s.get("segmento", "") or s.get("diagnostico", "")[:40]
            bloques.append(f"  Siniestro: {s.get('id','?')} | {s.get('fecha','?')} | tipo={tipo} | {seg}")
```

---

## Orden de implementación (de mayor a menor impacto)

### Paso 1 — `leer_notas_crudas`: buscar CC en tablas + ampliar a 3000 chars (15 min)

**Máximo impacto.** Si el sistema hubiera leído el CR y el VOI de Sandra para Maribel, habría tenido todos los datos correctos antes de la síntesis. Los documentos existentes de Sandra son la mejor fuente de verdad.

Cambios:
1. `_leer_texto` en `leer_notas_crudas.py`: incluir texto de tablas (idéntico fix a qa_formatos G-2)
2. Ampliar de `max_chars=500` a `max_chars=3000` para la búsqueda de CC en contenido

---

### Paso 2 — Positiva: marcar como parcial cuando no extrae datos clínicos (10 min)

En `orquestador.py`, cambiar el cálculo de `parcial` para que refleje la realidad:
si Positiva no devolvió siniestros ni diagnóstico, `parcial: True` aunque no haya `"error"` explícito.

---

### Paso 3 — Positiva: selectores de tabla alternativos + espera dinámica (20 min)

En `_extraer_siniestros_tabla`: usar múltiples selectores y espera `wait_for_selector` en lugar de timeout fijo.
Añadir fallback: si la tabla falla, buscar número de siniestro en el body con regex `\b5\d{8}\b`.

---

### Paso 4 — Positiva: extraer pestaña DATOS ASEGURADO (30 min)

Añadir función `_extraer_datos_asegurado` que haga click en la pestaña y extraiga empresa, NIT, cargo, EPS, AFP.
Esto proporciona la empresa oficial de Positiva para cruzar con lo del audio.

---

### Paso 5 — `_formatear_portales`: incluir empresa, cargo, EPS, AFP (5 min)

Ampliar el formatter para que el LLM vea todos los datos del portal, no solo nombre/teléfono/siniestro.

---

### Paso 6 — Verificar portales: pausar cuando verificación es muy incompleta (10 min)

En `workflow_runner`, si `pendientes_portal > total * 0.5`, activar `_requiere_confirmacion = True`.
Estado final será `"listo_con_advertencias"` y Sandra recibe alerta por Telegram antes de usar los documentos.

---

### Paso 7 — Prompt de síntesis: separar cargo actual de historia laboral (10 min)

Agregar al prompt de síntesis las reglas para no mezclar historial laboral con el cargo actual.
Si el audio menciona trabajos anteriores, van en un campo distinto, no en `tareas_criticas`.

---

### Paso 8 — Positiva: verificar que búsqueda retornó resultados (10 min)

En `_buscar_en_consulta_integral`, verificar que el CC aparece en la respuesta antes de retornar `True`.

---

## Tabla resumen de fixes

| # | Fix | Archivo | Impacto | Tiempo |
|---|-----|---------|---------|--------|
| 1 | Leer CC en tablas DOCX + 3000 chars | `leer_notas_crudas.py` | **Crítico** | 15 min |
| 2 | `parcial: True` cuando Positiva sin datos | `orquestador.py` | **Crítico** | 10 min |
| 3 | Selectores tabla siniestros + espera dinámica | `positiva.py` | **Crítico** | 20 min |
| 4 | Extraer pestaña DATOS ASEGURADO | `positiva.py` | **Crítico** | 30 min |
| 5 | Empresa/EPS/AFP/cargo en `_formatear_portales` | `sintetizar_maestro.py` | **Alto** | 5 min |
| 6 | Pausar workflow si verificación muy incompleta | `workflow_runner.py` | **Alto** | 10 min |
| 7 | Prompt síntesis: separar historial vs cargo actual | `sintetizar_maestro.py` | **Alto** | 10 min |
| 8 | Verificar resultado de búsqueda en Positiva | `positiva.py` | **Medio** | 10 min |

**Total estimado: ~2 horas de trabajo de OpenCode.**

---

## Lo que debería pasar después de estos fixes (caso Maribel)

```
1. leer_notas_crudas: encuentra VOI_MARIBEL PUENTES MEDINA.docx y CR_MARIBEL... (tabla con CC 36280228)
2. Carga el CR: "Cargo: Técnica administrativa | Empresa: Alcaldía Municipal de Pitalito | Fecha: 23/05/2025"
3. Positiva extrae pestaña DATOS ASEGURADO: empresa = "Alcaldía Municipal de Pitalito", cargo, NIT
4. Positiva extrae siniestros tabla: siniestro ID, tipo Enfermedad Laboral, fecha, segmento
5. _formatear_portales muestra al LLM: empresa (Positiva), cargo, EPS, AFP, siniestro
6. LLM sintetiza con 4 fuentes: audio + portal Medifolios + portal Positiva + notas de workspace
7. LLM ve "empresa.nombre = Pitalito" en 3 fuentes distintas → no inventa "Pitarentos"
8. LLM ve "cargo = Técnica Administrativa" en portal + notas → no confunde con historial previo
9. Documentos generados con datos correctos
10. verificar_portales confirma 12/14 campos (vs 4/14 actual)
```

---

## Relación con PLAN_PERFECCIONAMIENTO.md

Los bugs de Parte 1 (extractores Playwright: P-1, P-2, P-3, P-4, P-5) siguen siendo prerequisito.
Sin esos fixes, este plan no puede funcionar completamente porque:
- Si MEDI_AGENDA sigue definido doble (P-1) → siniestro de Medifolios siempre [VERIFICAR]
- Si `.catch()` Python sigue (P-2) → nombre/teléfono/dirección de Medifolios siempre vacíos
- Si MEDI_JS no se usa (P-3, P-4) → búsqueda puede no dispararse, EPS/AFP nunca extraídos

**Orden de ejecución recomendado:**
1. Primero: todos los fixes de `PLAN_PERFECCIONAMIENTO.md` (bugs raíz Playwright + task_db)
2. Después: todos los fixes de este archivo `PLAN_DATOS_CORRECTOS.md` (calidad de datos)

---

*Plan de Datos Correctos — 2026-05-24 — Diagnóstico forense caso CC 36280228*
