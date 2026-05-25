# RILO SAS — Plan de Perfeccionamiento (Lectura Quirúrgica)

> Auditoría realizada leyendo el código real línea a línea, no por patrones.
> Cada bug tiene el archivo, la línea exacta y por qué causa el síntoma visible.
> Este plan, ejecutado completo, deja el sistema listo para producción.

---

## Por qué el sistema falla hoy — diagnóstico raíz

El pipeline falla por **5 bugs en cascada**, todos en la extracción de portales. El resto del sistema (síntesis, generación, QA, notificación) está bien implementado pero recibe datos vacíos y produce documentos vacíos.

---

## PARTE 1 — Bugs que rompen la extracción de portales (causa raíz de "datos en blanco")

---

### P-1 · `MEDI_AGENDA` definido dos veces — `KeyError: 'url'` → siniestro siempre `[VERIFICAR]`

**Archivo:** `backend/playwright_real/selectores.py` líneas 42–44 y 81–87

```python
# Línea 42 — Primera definición (con URL):
MEDI_AGENDA = {
    "url": "https://www.server0medifolios.net/index.php/SALUD_GESTIONCITAS/agenda_cita",
    "menu_agenda": "a:has-text('Agenda Citas'), [href*='agenda_cita']",
}

# Línea 81 — Segunda definición (SIN URL, sobreescribe la primera):
MEDI_AGENDA = {
    "menu_agenda": "a:has-text('Agenda Citas'), [href*='agenda']",
    "select_profesional": "select",
    "valor_sandra": "168-0",
    "cita_link_template": "a:has-text('{cc}'), tr:has-text('{cc}') a",
    "popup_detalle_observaciones": "textarea[name='observaciones'], #observaciones",
}
```

Python sobreescribe la variable. Cuando `medifolios.py` hace `S.MEDI_AGENDA["url"]` (línea 83), obtiene `KeyError`. El `try/except Exception: return "", ""` del bloque lo silencia. Resultado: `_extraer_siniestro_de_agenda` siempre retorna `("", "")` → `siniestro_medi = "[VERIFICAR]"`.

**Fix:** Fusionar las dos definiciones en una sola con todos los campos:
```python
MEDI_AGENDA = {
    "url": "https://www.server0medifolios.net/index.php/SALUD_GESTIONCITAS/agenda_cita",
    "menu_agenda": "a:has-text('Agenda Citas'), [href*='agenda_cita']",
    "select_profesional": "select",
    "valor_sandra": "168-0",
    "cita_link_template": "a:has-text('{cc}'), tr:has-text('{cc}') a",
    "popup_detalle_observaciones": "textarea[name='observaciones'], #observaciones",
}
```

---

### P-2 · `medifolios.py` línea 49: `.catch()` no existe en Python — form data siempre vacío

**Archivo:** `backend/playwright_real/medifolios.py` línea 49

```python
nombre = await page.input_value(S.MEDI_PACIENTES["nombre1"], timeout=8000).catch(lambda: "")
#                                                                              ↑ NO existe en Python
```

`.catch()` es JavaScript (Promise API). En Python, `page.input_value()` es una coroutine. Llamar `.catch()` sobre ella lanza `AttributeError: 'coroutine' object has no attribute 'catch'`. La excepción sube a `get_paciente_completo` que la captura con `except Exception as e` → `datos["error_form"] = "AttributeError..."` → nombre, teléfono, dirección, EPS, AFP **todo vacío**.

**Fix:** Envolver en try/except:
```python
try:
    nombre = await page.input_value(S.MEDI_PACIENTES["nombre1"], timeout=8000)
except Exception:
    nombre = ""
return bool(nombre)
```

---

### P-3 · `medifolios.py` no usa `MEDI_JS_CARGAR_PACIENTE` — búsqueda puede no dispararse

**Archivo:** `backend/playwright_real/medifolios.py` líneas 23–50  
**Archivo:** `backend/playwright_real/selectores.py` líneas 45–58 (`MEDI_JS_CARGAR_PACIENTE`)

Medifolios usa CodeIgniter con AJAX. El simple `fill()` rellena el input pero puede no disparar los eventos JS que activan la búsqueda. En `selectores.py` ya existe `MEDI_JS_CARGAR_PACIENTE` (un JS que dispara `input`, `change`, `blur`, `keydown Enter` en secuencia) pero `medifolios.py` nunca lo llama.

**Fix:** Después del fill, ejecutar el JS helper:
```python
await page.fill(S.MEDI_PACIENTES["numero_id_input"], cc)
await page.evaluate(S.MEDI_JS_CARGAR_PACIENTE, cc)
await page.wait_for_timeout(4000)
```

---

### P-4 · `medifolios.py` no usa `MEDI_JS_EXTRAER_FORM` — empresa/EPS/AFP nunca se extraen

**Archivo:** `backend/playwright_real/medifolios.py` líneas 53–77  
**Archivo:** `backend/playwright_real/selectores.py` líneas 62–79 (`MEDI_JS_EXTRAER_FORM`)

`_extraer_form_pacientes` itera solo campos de texto (`input`). Los selectores de empresa, EPS, AFP, ARL son `<select>` que no se extraen con `input_value()`. En `selectores.py` ya existe `MEDI_JS_EXTRAER_FORM` que lee TODOS los campos incluyendo los `<select>` y retorna un dict completo. Nunca se usa.

**Fix:** Reemplazar el loop de `_extraer_form_pacientes` con una sola llamada al JS helper:
```python
async def _extraer_form_pacientes(page: Page) -> dict:
    try:
        return await page.evaluate(S.MEDI_JS_EXTRAER_FORM)
    except Exception:
        return {}
```

---

### P-5 · `positiva.py` línea 75: regex captura "MARIA GREIDY RODRIGUEZ" (usuario logueado)

**Archivo:** `backend/playwright_real/positiva.py` líneas 75–78

```python
nombre_match = re.search(r"([A-ZÁÉÍÓÚÑ]{3,30}\s+[A-ZÁÉÍÓÚÑ]{3,30}\s+[A-ZÁÉÍÓÚÑ]{3,30})", body)
if nombre_match:
    datos["nombre_detectado"] = nombre_match.group(1)
```

La página de Positiva muestra el nombre del usuario autenticado (`MARIA GREIDY RODRIGUEZ`, del account `1075209386MR`) en el header de navegación. Este es el PRIMER nombre todo-mayúsculas de 3 palabras en `body`. El regex lo captura como el nombre del paciente buscado, sin importar a quién se buscó.

Además, `POS_LOGIN["post_login_heartbeat"] = "text=MARIA GREIDY"` en `selectores.py` línea 103 confirma que MARIA GREIDY es el usuario de la cuenta, no el paciente.

**Fix:** No extraer `nombre_detectado` del body. El nombre del paciente debe venir de Medifolios. En Positiva, solo extraer datos clínicos objetivos (siniestro, CIE-10, diagnóstico):
```python
# ELIMINAR las líneas 75-78 de positiva.py completamente
# El nombre siempre viene de Medifolios
```

---

### P-6 · `sintetizar_maestro._formatear_portales` usa `nombre1+apellido1` pero ignora `nombre` combinado

**Archivo:** `backend/workflow_steps/sintetizar_maestro.py` línea 37

```python
nombre = " ".join([medi.get("nombre1", ""), medi.get("apellido1", "")]).strip()
```

Si el extractor guardó `nombre` (campo ya combinado: "MARIBEL FUENTES MEDINA") pero no guardó `nombre1` y `apellido1` separados, el formatter devuelve `""` como nombre. El LLM de síntesis no ve el nombre del paciente y puede inventarlo o dejarlo vacío.

**Fix:**
```python
nombre = (
    " ".join(filter(None, [medi.get("nombre1",""), medi.get("nombre2",""), medi.get("apellido1",""), medi.get("apellido2","")])).strip()
    or medi.get("nombre", "")
)
```

---

## PARTE 2 — Bugs que rompen la gestión de tareas

---

### T-1 · `tiene_task_activo` bloquea reintentos — errores previos impiden nuevas ejecuciones

**Archivo:** `backend/task_db.py` líneas 130–136

```python
def tiene_task_activo(self, paciente_cc: str) -> bool:
    ...WHERE paciente_cc = ? AND estado NOT IN ('listo','cancelado')
```

Excluye solo `listo` y `cancelado`. Los estados `error_en_paso_N` NO están excluidos. Si el workflow falló en el paso 2 (resolver_paciente) con `error_en_paso_2`, `tiene_task_activo(cc)` retorna `True` bloqueando cualquier reintento.

Sandra no puede volver a procesar un paciente después de cualquier error sin que alguien borre la tarea manualmente de la DB.

**Fix:**
```python
WHERE paciente_cc = ? AND estado NOT IN ('listo','cancelado') AND estado NOT LIKE 'error_%'
```

---

### T-2 · `listar_activos` excluye `error_%` pero `tiene_task_activo` no — inconsistencia

**Archivo:** `backend/task_db.py` líneas 123–128 vs 130–136

`listar_activos` tiene `AND estado NOT LIKE 'error_%'`. `tiene_task_activo` no. Dos funciones del mismo módulo con lógica contradictoria para decidir qué es "activo".

**Fix:** Unificar: ambas deben excluir `error_%` y `esperando_datos` además de `listo` y `cancelado`.

---

### T-3 · El workflow no puede reiniciarse desde el paso 2 — siempre empieza desde el paso 1

**Archivo:** `backend/workflow_runner.py` líneas 50–65

Si el audio ya fue transcrito (paso 1 completado) pero el workflow falló en resolver_paciente (paso 2), la próxima ejecución vuelve a transcribir desde el principio (~5-8 minutos de transcripción desperdiciados).

No hay lógica de resume: si un task_id existe con `paso_actual = 2`, no se salta los pasos 1-2 ya completados.

**Fix:** Al inicio de `ejecutar_workflow`, si hay un `task_id_existente` con `paso_actual > 0`, empezar desde el paso siguiente al último completado. Restaurar `contexto` del JSON serializado en `resultado` (si existe).

---

## PARTE 3 — Bugs que afectan la generación de documentos

---

### G-1 · `generar_formatos._merge_paciente_con_llm` busca `pos.get("siniestro_id")` pero Positiva guarda en `pos.get("siniestros")[0]["id"]`

**Archivo:** `backend/workflow_steps/generar_formatos.py` línea 79

```python
siniestro = medi.get("siniestro_medi") or pos.get("siniestro_id") or ...
```

`positiva.py` guarda `datos["siniestro_id"] = siniestros[0]["id"]` (línea 178 de positiva.py). Esto sí coincide con `pos.get("siniestro_id")`. OK, este sí funciona.

PERO: `pos` en `_merge_paciente_con_llm` viene de `json_paciente.get("positiva", {})`, que es el JSON guardado por el orquestador. La clave `siniestro_id` sí existe ahí. ✓

Problema real: si `siniestro_medi = "[VERIFICAR]"` (por bug P-1), la condición `or` pasa a `pos.get("siniestro_id")`. Si Positiva tampoco lo encontró (todos los selectores de tabla fallaron), el siniestro queda vacío en los documentos.

**Fix:** Agregar `siniestros[0]["id"]` como fallback adicional en la búsqueda de siniestro:
```python
siniestros_pos = pos.get("siniestros", [])
siniestro_pos = siniestros_pos[0].get("id", "") if siniestros_pos else ""
siniestro = (medi.get("siniestro_medi") if medi.get("siniestro_medi") != "[VERIFICAR]" else "") \
         or pos.get("siniestro_id", "") \
         or siniestro_pos
```

---

### G-2 · `qa_formatos.py` línea 65: lógica incorrecta — `all()` con lista vacía es True

**Archivo:** `backend/workflow_steps/qa_formatos.py` línea 65

```python
qa_ok = len(warnings) == 0
```

(Esto ya parece correcto en la versión actual). Pero si `texto` extrae solo párrafos y los datos están en tablas (`doc.paragraphs` no incluye texto de celdas), todos los documentos de RILO fallarían el check `len(texto) < 100` aunque tengan contenido.

**Fix:** Incluir texto de tablas en `texto`:
```python
texto_parrafos = " ".join(p.text for p in doc.paragraphs if p.text.strip())
texto_tablas = " ".join(
    cell.text for table in doc.tables
    for row in table.rows
    for cell in row.cells
    if cell.text.strip()
)
texto = texto_parrafos + " " + texto_tablas
```

---

### G-3 · `convertir_pdf.py`: `--convert-to pdf` no genera PDF/A — documentos legalmente inválidos

**Archivo:** `backend/workflow_steps/convertir_pdf.py` línea 27

```python
cmd = [bin_lo, "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), docx_path]
```

Para archivo legal (ARL, Colombia), los documentos deben ser PDF/A. LibreOffice soporta PDF/A con el flag correcto.

**Fix:**
```python
cmd = [bin_lo, "--headless", "--convert-to", 
       "pdf:writer_pdf_Export:{\"SelectPdfVersion\":{\"type\":\"long\",\"value\":\"2\"}}",
       "--outdir", str(output_dir), docx_path]
```

O más simple, usando el perfil de exportación:
```python
cmd = [bin_lo, "--headless", "--convert-to", "pdf", 
       "--infilter=impress_pdf_Export",
       "--outdir", str(output_dir), docx_path]
```

El estándar mínimo aceptado por ARL es PDF/A-1b. Usar `SelectPdfVersion=1` (PDF/A-1) o `2` (PDF/A-2).

---

### G-4 · `workflow_runner._build_kwargs` para `generar_formatos` puede pasar `datos_clinicos = {}`

**Archivo:** `backend/workflow_runner.py` líneas 177–186

```python
datos_clinicos = verif.get("datos_enriquecidos") or sintesis.get("datos_clinicos") or {}
```

Si `verificar_portales` falla (error en Playwright, red caída), `verif` puede ser `{}`. Entonces cae a `sintesis.get("datos_clinicos")`. Si la síntesis también falló (paso 5 bloqueado), `datos_clinicos = {}`.

El check en líneas 78–81 ya debería atrapar esto:
```python
if dc is None or (isinstance(dc, dict) and len(dc) == 0):
    db.marcar_error(...)
    return
```

Pero hay un edge case: `len({}) == 0` → bien. Sin embargo, `{"_meta": {}}` tiene `len > 0` pero no tiene datos clínicos. Si el LLM devuelve solo el schema vacío con `_meta`, pasa el check pero genera 7 documentos vacíos.

**Fix:** El check debe verificar campos específicos:
```python
if step_name == "generar_formatos":
    dc = kwargs.get("datos_clinicos", {})
    paciente_doc = (dc.get("paciente") or {}).get("documento", "")
    if not paciente_doc:
        db.marcar_error(task_id, paso=paso_num, error="datos_clinicos sin documento del paciente")
        return {"task_id": task_id, "estado": f"error_en_paso_{paso_num}", "error": "Sin CC del paciente en datos_clinicos"}
```

---

## PARTE 4 — Bugs que rompen la interfaz y la experiencia

---

### U-1 · `server.py`: `GET /api/download/{filename}` solo sirve desde `DOCS_DIR` — los PDFs están en `PDFS_DIR`

**Archivo:** `backend/server.py` líneas 244–258

```python
resolved = (DOCS_DIR / safe_name).resolve()
...
return FileResponse(str(resolved), ...)
```

El endpoint solo busca archivos en `DOCS_DIR` (storage/docs/). Los PDFs están en `PDFS_DIR` (storage/pdfs/). No hay endpoint para descargar PDFs. El chat y la lista de formatos solo muestran links a DOCX.

**Fix:** Buscar en ambos directorios:
```python
for base_dir in [DOCS_DIR, PDFS_DIR]:
    candidate = (base_dir / safe_name).resolve()
    if str(candidate).startswith(str(base_dir.resolve())) and candidate.exists() and candidate.is_file():
        mime = "application/pdf" if safe_name.endswith(".pdf") else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return FileResponse(str(candidate), media_type=mime, filename=safe_name)
raise HTTPException(404, "Archivo no encontrado")
```

---

### U-2 · `server.py` línea 438: `url_descarga` usa path relativo — roto si frontend y backend están en puertos distintos

**Archivo:** `backend/server.py` línea 438

```python
"url_descarga": f"/api/download/{f.name}",
```

El frontend está en puerto 3000 y el backend en 8000. Un path relativo `/api/download/...` en el frontend apunta a `localhost:3000/api/...` que Next.js rewrites a `localhost:8000/api/...`. Esto funciona si los rewrites están bien configurados. Si hay algún problema en el rewrite, 404.

**Fix que no depende de Next.js:** Usar el `DASHBOARD_URL` o una URL base explícita:
```python
base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
"url_descarga": f"{base_url}/api/download/{f.name}",
```

O mantener relativo y documentar que depende del rewrite de Next.js.

---

### U-3 · El chat muestra el task_id en el mensaje de inicio — confunde a Sandra

**Archivo:** `backend/server.py` línea ~400 (endpoint `/api/chat/audio`)

El mensaje inicial del workflow incluye el task_id:
```
✅ Recibí el audio de CC 36280228. Empiezo a procesarlo ahora... (task_id: abc123def456)
```

Sandra no sabe qué es un task_id. Solo sirve para debugging.

**Fix:** Ocultar el task_id del mensaje visible. El polling ya usa el task_id internamente.

---

### U-4 · Chat: el mensaje de progreso se sobreescribe pero muestra el nombre del PASO ANTERIOR

**Archivo:** `dashboard/app/chat/page.tsx` líneas 160–260

Durante el polling, el mensaje de progreso muestra el label del paso actual. Pero `db.actualizar_paso()` en `workflow_runner.py` línea 93 se llama DESPUÉS de que el paso ejecuta:

```python
resultado_step = future.result(timeout=timeout)   # ← ejecuta
contexto[step_name] = resultado_step               # ← guarda resultado
db.actualizar_paso(task_id, paso=paso_num, estado=estado_label)  # ← actualiza DESPUÉS
```

Entonces cuando el frontend pollea, ve `paso_actual = N` en el estado del DB, pero el paso N ya terminó y está empezando el N+1. El label mostrado es del paso N aunque ya va en N+1.

Esto no es un error grave pero hace que el progreso parezca desincronizado.

**Fix:** Mover `db.actualizar_paso` a ANTES de ejecutar el paso (para mostrar "está ejecutando esto"), y agregar `db.actualizar_paso` con `estado = f"{estado_label}_ok"` después de completar. O simplemente documentar que el progreso es aproximado.

---

## PARTE 4-B — Bugs encontrados en segunda auditoría (workflow_steps + lote_worker)

---

### N-1 · `MEDI_JS_EXTRAER_FORM` devuelve `slct_eps_paciente` pero `_merge_paciente_con_llm` busca `eps_ips` — EPS/AFP siempre vacíos

**Archivos:** `backend/playwright_real/selectores.py` líneas 71–75 + `backend/workflow_steps/generar_formatos.py` línea 58

El JS helper `MEDI_JS_EXTRAER_FORM` usa los IDs reales del DOM de Medifolios:

```python
['slct_eps_paciente','slct_afp_paciente','slct_arl_paciente','slct_empresa_paciente']
```

Devuelve `{"slct_eps_paciente": "SURA EPS", "slct_afp_paciente": "PORVENIR", ...}`.

Pero `_merge_paciente_con_llm` busca:
```python
for k in ("direccion", "telefono", "email", "edad", "eps_ips", "afp"):
    if not datos_llm["paciente"].get(k):
        val = medi.get(k) or pac.get(k) or ""  # medi.get("eps_ips") → siempre ""
```

`medi.get("eps_ips")` nunca encuentra nada porque la clave es `slct_eps_paciente`. La EPS y AFP del paciente nunca llegan a los documentos aunque estén en Medifolios.

Además, `_formatear_portales` en `sintetizar_maestro.py` no incluye EPS/AFP, así que el LLM tampoco las ve al sintetizar.

**Fix:** En `medifolios.py`, después de llamar `MEDI_JS_EXTRAER_FORM`, remapear los nombres:
```python
REMAP = {
    "slct_eps_paciente": "eps_ips",
    "slct_afp_paciente": "afp",
    "slct_arl_paciente": "arl",
    "slct_empresa_paciente": "empresa",
}
campos = await page.evaluate(S.MEDI_JS_EXTRAER_FORM)
return {REMAP.get(k, k): v for k, v in campos.items()}
```

Y añadir en `_formatear_portales`:
```python
if medi.get("eps_ips"): bloques.append(f"  EPS: {medi['eps_ips']}")
if medi.get("afp"):     bloques.append(f"  AFP: {medi['afp']}")
if medi.get("empresa"): bloques.append(f"  Empresa: {medi['empresa']}")
```

**Impacto:** Sin este fix, los 7 documentos salen sin EPS, AFP ni empresa, aunque Medifolios los tiene.

---

### N-2 · `sintetizar_maestro.py` línea 197 — check demasiado estricto bloquea workflow cuando siniestro es desconocido

**Archivo:** `backend/workflow_steps/sintetizar_maestro.py` líneas 196–204

```python
if not paciente.get("documento") or not siniestro.get("id_siniestro"):
    return {"ok": False, "error": "Datos clinicos incompletos: falta documento del paciente o id_siniestro", ...}
```

Si el LLM omite la clave `id_siniestro` completamente (no la pone ni como `[FALTA]`), `siniestro.get("id_siniestro")` retorna `None` → `not None` → falla con `ok: False`.

Esto puede ocurrir cuando el modelo tiene dificultades con el JSON o cuando el siniestro genuinamente no se conoce. El workflow para en el paso 5 aunque el paciente, empresa, diagnóstico y todo lo demás estén completos.

**Fix:** Permitir que `id_siniestro` sea `[FALTA]` o un placeholder sin detener el workflow:
```python
doc = (paciente.get("documento") or "").strip()
sin = (siniestro.get("id_siniestro") or "").strip()
if not doc:
    return {"ok": False, "error": "Falta documento (CC) del paciente en datos_clinicos"}
# Siniestro puede ser [FALTA] — el workflow continúa con advertencia
if not sin:
    datos_clinicos.setdefault("siniestro", {})["id_siniestro"] = "[VERIFICAR EN PORTAL]"
    _log("Warning: siniestro no encontrado - marcado como [VERIFICAR EN PORTAL]")
```

**Impacto:** Sin este fix, cualquier audio de paciente nuevo sin siniestro conocido falla en el paso 5.

---

### N-3 · `generar_formatos.py` línea 144 — 1 formato fallido para el workflow completo

**Archivo:** `backend/workflow_steps/generar_formatos.py` línea 144

```python
return {
    "ok": len(errores) == 0,  # ← 1 error de 7 = ok=False → workflow para
    ...
}
```

`workflow_runner.py` línea 96 chequea:
```python
if step_name in ("transcribir", "sintetizar_maestro", "generar_formatos", "convertir_pdf") and not resultado_step.get("ok"):
    db.marcar_error(...)
    return {"task_id": ..., "estado": f"error_en_paso_{paso_num}", ...}
```

Si el `doc_generator` lanza una excepción en 1 de 7 formatos (e.g., `firma_sandra.png` no existe y solo afecta la VOI), los otros 6 formatos generados se pierden y Sandra no recibe nada.

**Fix:** Umbral de éxito parcial: ok si al menos 5 de 7 formatos se generaron:
```python
ok = len(generados) >= max(1, len(formatos) - 2)
```

O añadir un campo `ok_parcial` y no detener el workflow si hay al menos 1 formato:
```python
return {
    "ok": len(errores) == 0,
    "ok_parcial": len(generados) > 0,
    ...
}
```

Y en `workflow_runner.py`:
```python
if step_name == "generar_formatos" and not resultado_step.get("ok"):
    if resultado_step.get("ok_parcial"):
        _log(f"Warning: {len(resultado_step.get('errores',[]))} formatos fallaron pero continúa con parciales")
    else:
        db.marcar_error(...)
        return ...
```

**Impacto:** Un error en cualquier formato (firma faltante, template roto) deja a Sandra sin documentos aunque los demás estuvieran bien.

---

### N-4 · `lote_worker.py` líneas 180–184 — fallback de respuesta vacía produce texto no-JSON que rompe síntesis

**Archivo:** `backend/lote_worker.py` líneas 180–184

```python
if not resultado["content"] and resultado["reasoning"]:
    fallback = "🤔 " + " ".join(resultado["reasoning"].split("\n")[-3:])[:300]
    return {"ok": True, "tipo": "sintetizar", ..., "respuesta": fallback, "fallback": True}
```

Cuando el LLM de razonamiento devuelve contenido vacío (pasó el tiempo de razonamiento pero no generó respuesta final), el worker crea un fallback con texto plano del reasoning.

`sintetizar_maestro.py` recibe `resultado.get("respuesta", "")` = `"🤔 Analizando el caso..."` y busca ````json...````. No encuentra JSON → retorna `ok: False, error: "LLM no devolvio JSON clinico valido"`. El workflow para en el paso 5.

**Fix:** El fallback no debe retornar `ok: True` para una síntesis. Retornar error para que el caller pueda manejar el reintento:
```python
if not resultado["content"] and resultado["reasoning"]:
    return {
        "ok": False,
        "tipo": "sintetizar",
        "error": "LLM devolvio solo reasoning sin respuesta final (posible timeout interno del modelo)",
        "tokens": resultado["tokens"],
        "tiempo_s": resultado["tiempo_s"],
    }
```

**Impacto:** Cuando DeepSeek v4-pro excede su tiempo interno de razonamiento (ocurre con contextos muy largos), el workflow para en paso 5 aunque con el mensaje de error correcto.

---

## PARTE 5 — Dependencias del sistema faltantes

Estos no son bugs de código sino dependencias que deben instalarse en la WSL de Sandra:

---

### DEP-1 · LibreOffice no instalado → 0 PDFs siempre

```bash
sudo apt-get update && sudo apt-get install -y libreoffice
```

Verificar después:
```bash
libreoffice --version
# LibreOffice 7.x.x
```

---

### DEP-2 · ffmpeg no instalado → transcripción de audios largos falla

```bash
sudo apt-get install -y ffmpeg
```

Verificar:
```bash
ffprobe -version
```

---

### DEP-3 · `firma_sandra.png` no existe → documentos sin firma

```bash
ls backend/templates/assets/firma_sandra.png
# Si no existe: mkdir -p backend/templates/assets
# Luego copiar la foto de la firma
```

---

### DEP-4 · `python-magic` no instalado → validación MIME de uploads no funciona (silencioso)

**Archivo:** `backend/server.py` líneas 78–83 — el `except ImportError: pass` silencia la ausencia

```bash
pip install python-magic && sudo apt-get install -y libmagic1
```

---

## PARTE 6 — Fixes ya aplicados por OpenCode (no repetir)

| Problema | Estado |
|----------|--------|
| Chat polling pegado en paso 1 | ✅ Corregido (AbortController manual) |
| Conversaciones no cambian | ✅ Corregido (authFetch con cookies) |
| 54 mensajes no aparecen | ✅ Corregido (DELETE+INSERT, no acumulación) |
| Download con `<a>` tags sin cookies | ✅ Corregido (authFetch + blob) |
| `convertir_pdf` saltaba formatos con `qa_ok: False` | ✅ Corregido (convierte todos con `archivo`) |
| Click en paciente de agenda — más robusto | ✅ Mejorado (timeout 5s + fallback Enter) |
| `chat_history` tabla no existía | ✅ Corregido (en task_db.py) |
| Siniestro en agenda — fallback mejorado | ✅ Mejorado (aunque P-1 aún causa el KeyError) |

---

## PARTE 7 — Orden de implementación (de mayor a menor impacto)

### Paso 0 — Instalar dependencias (sin código, solo comandos)

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg libreoffice libmagic1
pip install python-magic
```

Estas son bloqueantes. Sin ffmpeg: no hay transcripción. Sin LibreOffice: no hay PDFs.

---

### Paso 1 — Arreglar `selectores.py` (10 minutos, máximo impacto)

Fusionar las dos definiciones de `MEDI_AGENDA` en una sola. Es 1 edición de archivo.

**Impacto:** Siniestro deja de ser siempre `[VERIFICAR]`.

---

### Paso 2 — Arreglar `medifolios.py` (20 minutos)

1. Línea 49: Reemplazar `.catch()` con `try/except` — **causa el form data en blanco**
2. En `_cargar_paciente_en_form`: usar `MEDI_JS_CARGAR_PACIENTE` para disparar la búsqueda correctamente
3. En `_extraer_form_pacientes`: usar `MEDI_JS_EXTRAER_FORM` para extraer todos los campos incluyendo dropdowns

**Impacto:** Nombre, teléfono, dirección, empresa, EPS, AFP dejan de estar en blanco.

---

### Paso 3 — Arreglar `positiva.py` (5 minutos)

Eliminar las líneas 75–78 que capturan "MARIA GREIDY" como nombre del paciente. El nombre viene de Medifolios, no de Positiva.

**Impacto:** Positiva deja de reportar la persona equivocada.

---

### Paso 4 — Arreglar `sintetizar_maestro._formatear_portales` (5 minutos)

Línea 37: usar `nombre` combinado como fallback cuando `nombre1`/`apellido1` están vacíos.

**Impacto:** El LLM ve el nombre del paciente en el contexto de síntesis.

---

### Paso 5 — Arreglar `task_db.tiene_task_activo` (2 minutos)

Agregar `AND estado NOT LIKE 'error_%'` a la query. Sandra puede reintentar después de un error.

**Impacto:** No más bloqueos después de workflows fallidos.

---

### Paso 6 — Arreglar `generar_formatos._merge_paciente_con_llm` (10 minutos)

Mejorar la búsqueda del siniestro para incluir `siniestros[0]["id"]` como fallback. Arreglar lógica de `[VERIFICAR]`.

**Impacto:** Siniestro aparece en documentos aunque Medifolios falló.

---

### Paso 7 — Arreglar `qa_formatos` — texto de tablas (10 minutos)

Incluir texto de celdas de tablas en el análisis de calidad. Los formatos de RILO son mayormente tablas.

**Impacto:** QA no falla en documentos que tienen datos en tablas pero no en párrafos.

---

### Paso 8 — Arreglar `server.py` — endpoint download sirve PDFs también (10 minutos)

Buscar en `PDFS_DIR` además de `DOCS_DIR`.

**Impacto:** Los PDFs se pueden descargar desde el dashboard.

---

### Paso 9 — `generar_formatos` check de CC vacío + tolerancia a errores parciales (10 minutos)

Dos cambios:
1. Verificar que `paciente.documento` esté presente antes de generar.
2. Umbral de éxito parcial: no parar si falla 1 de 7 formatos (N-3).

**Impacto:** Error claro en lugar de 7 documentos "sin_cc". Sandra recibe 6 formatos aunque 1 falle.

---

### Paso 10 — `convertir_pdf`: PDF/A real (15 minutos)

Cambiar flag de conversión de LibreOffice para generar PDF/A.

**Impacto:** Documentos legalmente válidos para ARL.

---

### Paso 11 — Remapear nombres de campos de MEDI_JS_EXTRAER_FORM (10 minutos) — HACER CON PASO 2

Al implementar el fix P-4 (usar `MEDI_JS_EXTRAER_FORM`), agregar el remapeo de nombres en `medifolios.py`:
`slct_eps_paciente → eps_ips`, `slct_afp_paciente → afp`, `slct_empresa_paciente → empresa`.
Y añadir EPS/AFP/empresa al `_formatear_portales` en `sintetizar_maestro.py`.

**Impacto:** EPS, AFP y empresa del paciente aparecen en los documentos (ahora siempre vacíos).

---

### Paso 12 — Relajar check de `id_siniestro` en síntesis (5 minutos)

`sintetizar_maestro.py` línea 197: permitir que síntesis continue aunque `id_siniestro` sea desconocido.

**Impacto:** Pacientes nuevos con siniestro desconocido ya no bloquean el workflow en paso 5.

---

### Paso 13 — Corregir fallback vacío en `lote_worker.py` (3 minutos)

Línea 180-184: retornar `ok: False` en lugar de fake respuesta cuando LLM devuelve solo reasoning.

**Impacto:** Error claro en lugar de fallo silencioso con mensaje confuso en síntesis.

---

## Verificación end-to-end después de aplicar los fixes

Secuencia de prueba mínima:

```
1. Subir audio de 2-3 minutos del paciente CC 36280228
2. Verificar en logs (terminal) que:
   - resolver_paciente: "Playwright completo" (no "parcial")
   - medifolios: campos nombre, telefono, direccion presentes
   - positiva: siniestro extraído (no [VERIFICAR])
   - sintetizar_maestro: "ok: True" con datos_clinicos.paciente.nombre = nombre real
   - generar_formatos: "7/7 formatos generados"
   - convertir_pdf: "7/7 PDFs convertidos"
3. Verificar en dashboard: 7 DOCX descargables + 7 PDFs descargables
4. Abrir 1 DOCX: debe tener nombre del paciente, teléfono, siniestro, diagnóstico CIE-10
5. Telegram: debe llegar notificación a Sandra con el nombre correcto del paciente
```

---

## Resumen ejecutivo

| Fix | Archivo | Líneas | Tiempo |
|-----|---------|--------|--------|
| Fusionar `MEDI_AGENDA` doble | `selectores.py` | 42-87 | 5 min |
| `.catch()` → `try/except` | `medifolios.py` | 49 | 2 min |
| Usar `MEDI_JS_CARGAR_PACIENTE` | `medifolios.py` | 23-50 | 10 min |
| Usar `MEDI_JS_EXTRAER_FORM` + remapeo nombres | `medifolios.py` | 53-77 | 10 min |
| Añadir EPS/AFP/empresa a `_formatear_portales` | `sintetizar_maestro.py` | 36-49 | 5 min |
| Eliminar regex MARIA GREIDY | `positiva.py` | 75-78 | 2 min |
| Fallback `nombre` en formatter | `sintetizar_maestro.py` | 37 | 2 min |
| Relajar check `id_siniestro` síntesis | `sintetizar_maestro.py` | 197-204 | 5 min |
| Fallback inválido en lote_worker | `lote_worker.py` | 180-184 | 3 min |
| `tiene_task_activo` excluye errores | `task_db.py` | 131-134 | 2 min |
| Texto de tablas en QA | `qa_formatos.py` | 43 | 5 min |
| Download sirve PDFs también | `server.py` | 244-258 | 10 min |
| Tolerancia a 1 formato fallido | `generar_formatos.py` | 144 | 5 min |
| Check CC vacío en generar | `workflow_runner.py` | 78-81 | 5 min |
| `apt-get install ffmpeg libreoffice` | — | — | 10 min |

**Total estimado: ~85 minutos de trabajo de OpenCode.**

Después de esto el pipeline completo (audio → 7 DOCX + 7 PDFs + Telegram) debe funcionar de extremo a extremo sin intervención manual, incluyendo EPS, AFP, empresa y siniestro en todos los documentos.

---

*Plan de Perfeccionamiento — 2026-05-24 — v2 — Lectura directa de todos los módulos del pipeline*
