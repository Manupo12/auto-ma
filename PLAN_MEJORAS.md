# RILO SAS — Plan Integral de Mejoras v3

> Auditoría quirúrgica completa. 3 pasadas anteriores no encontraron esto.
> Cada item tiene archivo, línea exacta y descripción del fix real.
> Agente de implementación: **OpenCode**.

---

## Índice por severidad

- [🔴 CRÍTICOS — 9 items](#-críticos)
- [🟠 ALTOS — 14 items](#-altos)
- [🟡 MEDIOS — 12 items](#-medios)
- [🟢 BAJOS — 6 items](#-bajos)
- [🗑️ Código muerto — 17 archivos](#️-código-muerto)
- [📋 Orden de implementación](#-orden-de-implementación)

---

## 🔴 CRÍTICOS

Estos bugs producen datos falsos, documentos vacíos o pérdida silenciosa de información. Son los más peligrosos porque el sistema parece funcionar pero genera basura.

---

### C-1 · Playwright para paciente nuevo: la regla de negocio NO EXISTE en el código

**Archivo:** `backend/workflow_steps/resolver_paciente.py` líneas 36–56  
**Archivo:** `.env` línea con `FASE_A_ENABLED=false`

La regla acordada es: paciente nuevo = Playwright obligatorio siempre. Lo que hay en el código es completamente distinto:

```python
# Línea 40: acepta cache de HASTA 1 AÑO (horas_max=8760)
if _es_reciente(path):
    return json.load(f), "cache"

# Línea 45: si FASE_A está apagado, devuelve vacío sin error
if os.getenv("FASE_A_ENABLED", "false").lower() != "true":
    return {"cc": cc, "_vacio": True, "razon": "FASE_A_ENABLED=false"}, "sin_datos"
```

`FASE_A_ENABLED=false` en el `.env` actual. Resultado: **para cualquier paciente sin cache previo, el sistema genera documentos con todos los datos vacíos, sin lanzar ningún error.**

**Fix:** Reescribir `resolver_paciente.py` con la lógica real:
```
cache_path = storage/data/{cc}-completo.json
edad_cache = ahora - fecha_modificacion(cache_path)

SI NO existe cache:
    → Playwright OBLIGATORIO (Medifolios + Positiva)
    → Si falla Playwright: estado = "error_extraccion", DETENER workflow

SI existe cache Y edad < 24h:
    → Usar cache, no abrir portales

SI existe cache Y edad >= 24h:
    → Playwright para refrescar
    → Si falla Playwright: usar cache viejo + advertencia en notificación
```

`FASE_A_ENABLED` como flag no tiene sentido con esta lógica — la extracción Playwright debe ser la ruta principal, no opcional.

---

### C-2 · `sintetizar_maestro` devuelve `ok: True` aunque el JSON clínico sea `None`

**Archivo:** `backend/workflow_steps/sintetizar_maestro.py` líneas 139–193

```python
match = re.search(r'```json\s*(\{.*?\})\s*```', respuesta_texto, re.DOTALL)
datos_clinicos = None
if match:
    try:
        datos_clinicos = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        _log(f"JSON clinico inválido: {e}")  # solo log

return {
    "ok": True,          # SIEMPRE True aunque datos_clinicos sea None
    "datos_clinicos": datos_clinicos,  # puede ser None
}
```

El paso siguiente (`generar_formatos`) recibe `datos_clinicos=None`, intenta hacer merge con el JSON del portal, y genera los 7 documentos con `[VERIFICAR]` en todos los campos.

**Fix:**
```python
if datos_clinicos is None:
    return {
        "ok": False,
        "error": "LLM no devolvió JSON clínico válido — respuesta truncada o mal formateada",
        "respuesta_cruda": respuesta_texto[:500]
    }
```

---

### C-3 · `generar_formatos` dice `ok: True` si al menos 1 de 7 formatos se generó

**Archivo:** `backend/workflow_steps/generar_formatos.py` líneas 122–147

```python
return {
    "ok": len(generados) > 0,  # ok=True si solo 1 de 7 se generó
    "generados": generados,
    "errores": errores,
}
```

Sandra puede recibir 1 documento de 7 y el sistema dice "listo".

**Fix:** `ok` debe ser `True` solo si `len(errores) == 0`. Si hay errores, el estado del task debe ser `listo_incompleto` con la lista de formatos que fallaron visible en el Telegram.

---

### C-4 · `qa_formatos` siempre retorna `ok: True` — nunca bloquea nada

**Archivo:** `backend/workflow_steps/qa_formatos.py` líneas 34–79

```python
def ejecutar(formatos_generados):
    return {
        "ok": True,     # SIEMPRE True, independientemente de lo que encuentre
        "resultados": resultados,
    }
```

La lógica interna detecta `[VERIFICAR]`, documentos vacíos y campos faltantes, pero esa información nunca llega a cambiar el flujo. El QA es decorativo.

**Fix:** 
- Si algún formato tiene `[VERIFICAR]` en campos críticos (nombre, CC, siniestro, diagnóstico): `ok = False`, estado `listo_con_advertencias`
- Notificación Telegram diferenciada: "✅ Listo" vs "⚠️ Listo con campos por verificar: [lista]"

---

### C-5 · La tabla `chat_history` no existe en ningún `CREATE TABLE`

**Archivo:** `backend/task_db.py` líneas 24–40

El schema de `task_db.py` crea `workflow_tasks` pero nunca `chat_history`. Cualquier operación de chat (guardar, leer, listar, borrar) lanza `sqlite3.OperationalError: no such table: chat_history`.

Consecuencia directa: `eliminar_paciente` (server.py línea 570) crashea en la línea del `DELETE FROM chat_history`, retorna HTTP 500 después de ya haber borrado los archivos físicos. El frontend no actualiza la UI — el paciente fantasma.

**Fix:** Agregar al schema de `task_db.py`:
```sql
CREATE TABLE IF NOT EXISTS chat_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_cc TEXT    NOT NULL,
    rol         TEXT    NOT NULL,
    contenido   TEXT,
    accion      TEXT,
    archivo     TEXT,
    timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chat_cc ON chat_history(paciente_cc);
```

---

### C-6 · `.env` con credenciales reales está rastreado por git

**Archivo:** `.env` (raíz del repo)  
**Archivo:** `.gitignore`

El `.env` contiene credenciales activas:
```
DEEPGRAM_API_KEY=3888b515e3e95...
TELEGRAM_BOT_TOKEN=8678791933:AAEmEnw...
OPENCODE_GO_API_KEY=sk-eHIeG9D83tfd8...
POSITIVA_PASSWORD=Rilo2026*
GMAIL_APP_PASSWORD=dnjaycuadxcmppao
```

Si este archivo está en el historial de git (aunque se agregue a `.gitignore` después), las credenciales permanecen en `git log` para siempre.

**Fix:**
1. Verificar: `git log --all --full-history -- .env`
2. Si aparece en el historial: rotar TODAS las credenciales (generar nuevas API keys, cambiar contraseñas)
3. Agregar `.env` a `.gitignore` ahora si no está
4. Usar `git filter-branch` o `git-filter-repo` para limpiar el historial

---

### C-7 · Documentos se generan sin firma y nadie lo sabe

**Archivo:** `backend/doc_generator.py` línea ~37 y función `_insertar_firma`

Cuando `firma_sandra.png` no existe, la función simplemente omite la firma sin lanzar excepción ni agregar advertencia al resultado. El documento se entrega completo visualmente pero sin firma. En contexto médico-legal esto puede invalidar el documento.

**Fix:** Si `FIRMA` no existe:
```python
if not FIRMA.exists():
    raise FileNotFoundError(f"Firma faltante: {FIRMA} — documento inválido sin firma")
```
O, si se quiere continuar sin firma: agregar `"advertencia_firma": True` al resultado y mostrarlo en la notificación Telegram.

---

### C-8 · Race condition: tareas activas del workflow recrean el paciente después de borrarlo

**Archivo:** `backend/server.py` líneas 553–572

`eliminar_paciente` borra el registro en `workflow_tasks` en SQLite, pero si hay un `asyncio.Task` corriendo en memoria para ese CC, ese task sigue ejecutándose. Cuando termina, recrea el JSON del paciente en `storage/data/`. El borrado en DB no cancela el asyncio.Task en memoria.

**Fix:** Al inicio de `eliminar_paciente`:
1. Consultar `task_db.listar_activos()` para obtener tasks del CC
2. Para cada task activo: cancelar el asyncio.Task del pool interno antes de borrar archivos
3. Esperar confirmación de cancelación (con timeout de 5s) antes de proceder

---

### C-9 · Renombrar `hermes.ts` → `api.ts` y eliminar `HERMES_API`

**Archivo:** `dashboard/lib/hermes.ts`  
**Archivo:** `dashboard/lib/workflow.ts` línea 1  
**Archivo:** `dashboard/lib/auth.ts`

`hermes.ts` nombra al agente de desarrollo (OpenCode/Hermes) dentro del código de producción de Sandra. La constante se llama `HERMES_API` y la variable de entorno es `NEXT_PUBLIC_HERMES_API`. Hermes no existe en la WSL de Sandra en producción.

Adicionalmente, `workflow.ts` tiene `const API = "http://localhost:8000"` hardcodeado sin leer ninguna variable de entorno.

**Fix (en orden):**
1. Renombrar `dashboard/lib/hermes.ts` → `dashboard/lib/api.ts`
2. Renombrar constante `HERMES_API` → `API_URL`
3. Eliminar `NEXT_PUBLIC_HERMES_API` — solo usar `NEXT_PUBLIC_API_URL`
4. Actualizar todos los imports: `from "@/lib/hermes"` → `from "@/lib/api"`
5. En `workflow.ts` y `auth.ts`:
```typescript
const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");
```
6. En `.env.local` del dashboard: borrar `NEXT_PUBLIC_HERMES_API` si existe

---

## 🟠 ALTOS

Estos bugs degradan la calidad de los documentos generados, producen datos incorrectos o causan fallos que el usuario ve sin saber por qué.

---

### A-1 · Datos vacíos se propagan por todo el pipeline sin bloquear

**Archivo:** `backend/workflow_runner.py` líneas 56–86

Los pasos 1–4 (transcribir, resolver, leer notas, leer formatos subidos) nunca fallan el workflow aunque retornen datos vacíos. Solo los pasos 5 y 6 (`sintetizar_maestro`, `generar_formatos`) pueden detener el flujo. El resultado: un workflow completo que genera documentos con datos mínimos o nulos.

**Fix:** Después de cada paso, verificar que el output tiene contenido mínimo esperado:
- Tras `transcribir`: texto de transcripción no vacío
- Tras `resolver_paciente`: si `_vacio=True` y es paciente nuevo → DETENER con `error_sin_datos`
- Tras `leer_notas_crudas`: puede estar vacío (aceptable si hay portales)

---

### A-2 · Chunks de audio fallidos producen transcripción con huecos silenciosos

**Archivo:** `backend/workflow_steps/transcribir.py` líneas 60–133

Si el chunk 3 de 5 falla, se agrega advertencia pero la transcripción continúa. La confianza promedio mezcla chunks exitosos y fallidos: un audio con chunk 0 de confianza por fallo baja el promedio pero no bloquea.

**Fix:** Marcar qué chunks fallaron en el resultado:
```python
resultado["chunks_fallidos"] = [i for i, c in enumerate(resultados) if c.get("error")]
```
Si más del 20% de chunks falló: `ok = False`. Si menos: `ok = True` pero `warnings` debe incluir los segmentos faltantes para que `sintetizar_maestro` se lo informe al LLM.

---

### A-3 · `fusionador.py`: reconciliación de discrepancias no se muestra a Sandra

**Archivo:** `backend/fusionador.py` líneas 68–316

Cuando Medifolios y Positiva tienen datos distintos (número de siniestro, diagnóstico), el fusionador detecta la discrepancia y la guarda en `_metadata.reconciliacion_siniestro`, pero:
1. La "resolución" es "prevalece Positiva" por orden de update — no hay lógica explícita
2. Ningún formato imprime esas discrepancias
3. La notificación Telegram no las menciona
4. Sandra nunca sabe que hubo conflicto

**Fix:** En `notificar_listo.py`, si `discrepancias` tiene items, incluirlos en el mensaje de Telegram: `"⚠️ Discrepancia detectada: Siniestro Medifolios=503463870, Positiva=503501234 — verificar cuál es correcto."`

---

### A-4 · `format_selector.py`: detección de estado frágil

**Archivo:** `backend/format_selector.py` líneas 113–179

La auto-detección de estado busca literalmente `"PRUEBA DE TRABAJO"` en la metodología. Si la transcripción dice "prueba en el trabajo", "prueba funcional laboral" o "evaluación de trabajo" → no detecta, hace fallback a NUEVO, y genera los formatos equivocados.

**Fix:** Ampliar los patrones de detección:
```python
PATRONES_PRUEBA = ["prueba de trabajo", "prueba funcional", "prueba laboral", "evaluacion de desempe"]
es_prueba = any(p in metodologia for p in PATRONES_PRUEBA)
```

---

### A-5 · `leer_formatos_subidos.py`: lee solo primeras 5000 chars y 3 tablas

**Archivo:** `backend/workflow_steps/leer_formatos_subidos.py` líneas 20–45

```python
texto = texto[:5000]          # documentos de 20 páginas se truncan
for tabla in doc.tables[:3]:  # solo primeras 3 tablas
    for row in tabla.rows[:5]: # solo primeras 5 filas
```

Documentos de referencia largos (formatos anteriores de Sandra) se leen a medias, perdiendo datos clínicos clave del paciente.

**Fix:** Aumentar límites a valores razonables. Para tablas, leer todas las filas pero limitar el texto total a 20000 chars con indicador de truncamiento.

---

### A-6 · Sesión Playwright expira silenciosamente durante extracción

**Archivo:** `backend/playwright_real/session.py` líneas 92–174

La verificación de sesión activa es:
```python
body = await page.text_content("body") or ""
return "Menu Principal" in body or "Bienvenido" in body
```

Si la página muestra un error 403 que incluye la palabra "Bienvenido" en algún banner → retorna sesión válida. Si el re-login falla, el `storage_state` anterior se sobreescribe y se pierde.

**Fix:** 
1. Verificar URL actual después de cargar, no solo el texto
2. Antes de sobreescribir el state, guardar backup: `state_path.rename(state_path + ".bak")`
3. Si re-login falla: restaurar backup, retornar error explícito

---

### A-7 · Timeout de Playwright 30s insuficiente para Positiva

**Archivo:** `backend/playwright_real/session.py`  
**Archivo:** `.env` → `PLAYWRIGHT_TIMEOUT_MS=30000`

Positiva suele tardar más de 40 segundos en cargar sus tablas de datos. Con 30s de timeout, la extracción de Positiva falla sistemáticamente en conexiones lentas.

**Fix:** Aumentar timeout por defecto a 60000ms (`60s`) para Positiva específicamente, y agregar retry automático (2 intentos) antes de declarar fallo.

---

### A-8 · `leer_notas_crudas.py`: escaneo se aborta por timeout sin avisar

**Archivo:** `backend/workflow_steps/leer_notas_crudas.py` líneas 60–94

```python
if _time.time() - start > timeout_s:  # 5 segundos hard
    return  # retorna parcial, sin marcar que está incompleto
```

Si el workspace de Sandra tiene muchas subcarpetas, el escaneo se corta en 5s y retorna las notas encontradas hasta ese momento sin indicar que el escaneo fue incompleto. El LLM sintetiza con información parcial.

**Fix:** Retornar metadata: `{"notas": [...], "escaneo_completo": False, "archivos_escaneados": n}` y pasar esa info al prompt de `sintetizar_maestro` para que el LLM sepa que puede haber notas faltantes.

---

### A-9 · `correction_resolver.py`: LLM puede retornar campo inválido sin validación

**Archivo:** `backend/correction_resolver.py` líneas 56–94

```python
return json.loads(match.group(1))  # crash si JSON malformado
# + no valida que el campo devuelto exista en la estructura del paciente
```

Si el LLM inventa un campo como `"paciente.nombre_secreto"`, el sistema lo ignora silenciosamente. Si el JSON está malformado, crashea sin try/catch.

**Fix:**
```python
try:
    resultado = json.loads(match.group(1))
except json.JSONDecodeError:
    return {"campo": None, "confianza": 0, "error": "JSON malformado"}

CAMPOS_VALIDOS = {"paciente.nombre", "siniestro.id_siniestro", ...}  # lista explícita
if resultado.get("campo") not in CAMPOS_VALIDOS:
    return {"campo": None, "confianza": 0, "error": "campo desconocido"}
```

---

### A-10 · Conexiones SQLite sin context manager — database lock bajo carga

**Archivo:** `backend/server.py` líneas 407, 424, 445, 458, 568

```python
conn = sqlite3.connect(db_path)
# ... queries ...
conn.close()  # no ejecutado si hay excepción entre medio
```

Si ocurre una excepción entre `connect()` y `close()`, la conexión queda abierta. SQLite permite una sola writer — las conexiones huérfanas bloquean todas las escrituras posteriores.

**Fix:** Cambiar a `with sqlite3.connect(db_path, timeout=30) as conn:` en todos los casos.

---

### A-11 · `eliminar_paciente`: frontend no maneja el HTTP 500

**Archivo:** `dashboard/app/formatos/page.tsx` líneas 84–94

```typescript
await fetch(`${API}/api/pacientes/${cc}`, { method: "DELETE" });
// no verifica response.ok
```

Si el backend devuelve 500 (por C-5 u otro error), el modal cierra y la lista recarga mostrando al paciente todavía. Sandra cree que el borrado funcionó.

**Fix:**
```typescript
const res = await fetch(...);
if (!res.ok) {
    setError(`Error al eliminar (${res.status})`);
    return;
}
```

---

### A-12 · `eliminar_formatos` no limpia `workflow_audios`

**Archivo:** `backend/server.py` línea 531

```python
for d in [DOCS_DIR, PDFS_DIR, AUDIO_DIR]:  # falta WORKFLOW_AUDIOS_DIR
```

Los `.m4a` del paciente quedan en `storage/workflow_audios/`.

**Fix:** Agregar `WORKFLOW_AUDIOS_DIR` a la lista.

---

### A-13 · `WORKFLOW_AUDIOS_DIR` definida en línea 1001, usada en líneas 350 y 531

**Archivo:** `backend/server.py` líneas 350, 531, 1001

En Python funciona porque las variables de módulo se resuelven en runtime, pero es frágil. Si alguien divide el archivo, lanza `NameError`.

**Fix:** Mover la definición de `WORKFLOW_AUDIOS_DIR` al bloque de directorios en líneas 53–59 junto con los demás.

---

### A-14 · Estados del workflow pueden quedar en limbo para siempre

**Archivo:** `backend/task_db.py` y `backend/workflow_runner.py`

Si el proceso Python muere (OOM, kill, reinicio del servidor) mientras un task está en estado `transcribiendo` o `sintetizando`, ese estado queda congelado en SQLite. No hay heartbeat ni timeout que lo limpie. El dashboard muestra la tarea "en progreso" indefinidamente.

**Fix:** Al arrancar el servidor (en el `@app.on_event("startup")`), marcar como `error_interrumpido` todos los tasks que tengan estado activo y `iniciado_en` hace más de N horas (ej. 2 horas).

---

## 🟡 MEDIOS

Estos issues degradan la robustez y mantenibilidad del sistema pero no producen datos incorrectos inmediatamente.

---

### M-1 · `fusionador.py`: segmento lesionado falla con variantes de código CIE-10

**Archivo:** `backend/fusionador.py` línea ~259

```python
prefix = str(code)[:2].upper()
if prefix in _CIE10_SEGMENTO:
    return _CIE10_SEGMENTO[prefix]
return ""  # si no coincide → vacío
```

`S611` → detecta `S6` ✓. Pero `S61.1` (con punto) → `S6` ✓. `Z57.5` → `Z5` que puede no estar en el mapa → `""`. Los códigos CIE-10 con letra tienen formatos variados.

**Fix:** Normalizar los códigos antes de buscar: `code.replace(".", "").strip()[:3]` y ampliar el mapa con prefijos de 3 caracteres.

---

### M-2 · `json_validator.py`: placeholder `[VERIFICAR]` no diferencia severidad

**Archivo:** `backend/json_validator.py` líneas 443–524

"Nombre del paciente = [VERIFICAR]" se trata igual que "Nombre del auditor = [VERIFICAR]". No hay jerarquía de campos críticos.

**Fix:** Definir lista de campos bloqueantes (`paciente.nombre`, `paciente.documento`, `siniestro.id_siniestro`, `diagnostico.cie10`) que deben estar presentes para que `qa_formatos` considere el documento aceptable.

---

### M-3 · `correction_loop.py`: patrones de detección de campos manuales e incompletos

**Archivo:** `backend/correction_loop.py` líneas 246–484

100+ patrones de regex mantenidos a mano. "el N° de siniestro" (con símbolo °) no coincide. "el número del caso" tampoco.

**Fix:** Usar el LLM (ya disponible) para clasificar la intención de corrección en lugar de regex manual. El LLM ya está en `correction_resolver.py` — unificar los dos módulos.

---

### M-4 · `leer_notas_crudas.py`: búsqueda de CC en contenido es literal

**Archivo:** `backend/workflow_steps/leer_notas_crudas.py`

```python
if cc in contenido:  # literal
```

Si la nota dice "Paciente: 1.193.143.688" o "CC: 1193-143-688" → no detecta.

**Fix:** Normalizar el CC antes de buscar: `cc_norm = cc.replace(".", "").replace("-", "").replace("'", "")` y buscar esa versión limpia en el contenido también limpio.

---

### M-5 · `orquestador.py` Playwright: discrepancias detectadas pero nunca mostradas

**Archivo:** `backend/playwright_real/orquestador.py` líneas 27–87

Las discrepancias entre Medifolios y Positiva se guardan en `_meta.discrepancias` del JSON, pero ningún paso posterior las lee ni las reporta. Sandra nunca ve que hay conflicto entre portales.

**Fix:** En `workflow_runner.py`, después de `resolver_paciente`, verificar `resultado.get("_meta", {}).get("discrepancias", [])` y agregarlo al contexto que llega a `notificar_listo`.

---

### M-6 · `format_selector.py`: fallback a NUEVO para casos ambiguos

**Archivo:** `backend/format_selector.py` líneas 113–179

Si el estado no se detecta claramente, devuelve `EstadoCaso.NUEVO` por default. Un seguimiento o cierre de caso mal transcrito genera formatos de admisión nueva.

**Fix:** Agregar estado `EstadoCaso.AMBIGUO` y, en ese caso, generar un conjunto de formatos conservador (los más comunes) con advertencia en la notificación: "No se detectó el estado del caso — se generaron formatos de seguimiento estándar. Verificar."

---

### M-7 · Cookies de sesión sin `secure` y sin `samesite`

**Archivo:** `backend/server.py` línea ~1130

```python
response.set_cookie("rilo_session", token)  # sin secure, sin samesite, sin httponly
```

**Fix:**
```python
response.set_cookie(
    "rilo_session", token,
    httponly=True,
    samesite="lax",
    secure=True,
    max_age=86400 * 30
)
```

---

### M-8 · PIN de auth sin expiración de token y con fallback a "1234"

**Archivo:** `backend/auth_simple.py` líneas 20 y 27–34

Si `AUTH_PIN` no está en `.env`, acepta "1234" sin advertencia. Los tokens no tienen timestamp de expiración.

**Fix:**
```python
AUTH_PIN = os.getenv("AUTH_PIN")
if not AUTH_PIN:
    raise RuntimeError("AUTH_PIN no configurado — el servidor no puede iniciar")
```
Agregar `exp` al payload del token.

---

### M-9 · Sin límite de tamaño ni validación de tipo en uploads de audio

**Archivo:** `backend/server.py` líneas 465–476

Acepta archivos de cualquier tamaño y cualquier formato. Un PDF subido por error produce un error críptico de Deepgram.

**Fix:**
```python
EXTENSIONES_VALIDAS = {".mp3", ".m4a", ".wav", ".ogg", ".webm", ".mp4"}
if Path(audio.filename).suffix.lower() not in EXTENSIONES_VALIDAS:
    raise HTTPException(400, "Formato de audio no soportado")
contenido = await audio.read()
if len(contenido) > 200 * 1024 * 1024:
    raise HTTPException(413, "Audio demasiado grande (máximo 200 MB)")
```

---

### M-10 · Número de CC no se valida en ningún endpoint

**Archivo:** `backend/server.py` — todos los endpoints con `{cc}`

Acepta `""`, `"abc"`, `"9999999999999999"`. Puede crear archivos con nombres inválidos o causar lookups infinitos.

**Fix:** Función reutilizable:
```python
def _validar_cc(cc: str):
    if not re.match(r'^\d{6,12}$', cc):
        raise HTTPException(400, f"CC inválida: '{cc}'")
```
Llamar al inicio de cada endpoint que reciba CC.

---

### M-11 · APScheduler pierde todos los jobs al reiniciar el servidor

**Archivo:** `backend/cron_pre_extraccion.py`

Los cron jobs se registran en memoria. Si el servidor se reinicia a las 20:55, el job de las 21:00 no corre.

**Fix:** Usar `SQLAlchemyJobStore` de APScheduler con el mismo `workflow.db`. O: al arrancar, comparar hora del último run guardado en DB contra la hora del cron esperada, y dispararlo si se perdió.

---

### M-12 · Páginas del dashboard sin verificación de sesión activa

**Archivos:** Páginas del dashboard

Si Sandra accede directamente a `/pacientes` sin sesión, el backend devuelve 401 pero el frontend muestra lista vacía o error genérico en lugar de redirigir al login.

**Fix:** Hook `useAuth()` en el layout raíz o en cada página que llame `GET /api/whoami` y redirija a `/login` si la sesión no es válida.

---

## 🟢 BAJOS

---

### B-1 · Datos hardcodeados en código de producción

**Archivo:** `backend/fusionador.py` líneas ~117, 222, 259–260

```python
paciente.setdefault("arl", "POSITIVA COMPANIA DE SEGUROS SA")
paciente.setdefault("ciudad", "Neiva")
visita.setdefault("nombre_profesional", "SANDRA PATRICIA POLANIA OSORIO")
```

**Archivo:** `backend/extractor_medifolios.py` líneas 40–42

```python
MEDIFOLIOS_USER = "55162801-2"
MEDIFOLIOS_PASS = "55162801-2"  # credencial hardcodeada
```

**Fix:** Mover todos estos valores a `.env` con claves descriptivas: `RILO_ARL_NOMBRE`, `RILO_CIUDAD`, `RILO_PROFESIONAL_NOMBRE`, etc.

---

### B-2 · `portal_knowledge.json` crece sin límite

**Archivo:** `storage/portal_knowledge.json`

El historial de verificaciones se acumula indefinidamente.

**Fix:** Al escribir, mantener solo las últimas 500 entradas.

---

### B-3 · `backup_diario.py` no notifica si falla

**Archivo:** `backend/backup_diario.py`

Si el backup de las 23:00 falla, no hay notificación. Manu no sabe.

**Fix:** Enviar Telegram a Manu con el error si el backup falla, y registrar `ultimo_backup_exitoso` en un archivo de estado.

---

### B-4 · Varios `except:` desnudos que capturan `SystemExit`

**Archivos:** `backend/notificador.py` línea ~214, otros

```python
except:  # captura KeyboardInterrupt, SystemExit
```

**Fix:** Cambiar a `except Exception as e:` en todas las ocurrencias.

---

### B-5 · Logs con CC de paciente en texto plano

**Archivo:** `backend/workflow_steps/resolver_paciente.py` línea ~41

```python
_log(f"CC {cc}: usando cache ({path.name})")
```

En sistemas de salud, los identificadores de paciente no deberían aparecer en logs sin enmascarar.

**Fix:** `_log(f"CC ***{cc[-4:]}: usando cache")` o usar un ID de sesión interno.

---

### B-6 · `database.db` huérfana de 32KB

**Archivo:** `backend/database.db`

Remanente de versión anterior, no referenciada por ningún código actual.

**Fix:** Eliminar el archivo después de confirmar que no hay datos importantes.

---

## 🗑️ Código Muerto

Estos 17 archivos existen en `backend/` pero no son importados por ningún otro módulo activo. Crean confusión, hacen que las revisiones pasen de largo errores reales, y agrandan el repo sin valor.

| Archivo | Estado | Acción |
|---------|--------|--------|
| `aplicador_correccion.py` | Nunca importado | Revisar si debe integrarse en `correction_loop.py` |
| `browser_session.py` | Reemplazado por `playwright_real/session.py` | Eliminar |
| `costos_tracker.py` | Nunca llamado | Integrar en `workflow_runner.py` o eliminar |
| `crear_plantillas.py` | Tool offline, no integrada | Mover a `tools/` o eliminar |
| `cron_pre_extraccion.py` | Nunca importado por server.py | Verificar si debe conectarse al startup |
| `custody.py` | Nunca importado | Verificar si reemplazado por `portal_verificador.py` |
| `email_reader.py` | Nunca importado | Conectar al cron o eliminar |
| `extractor_medifolios.py` | Reemplazado por `playwright_real/` | Archivar o eliminar |
| `extractor_positiva.py` | Ídem | Archivar o eliminar |
| `flujo_audio.py` | Importado por server pero pipeline usa `workflow_runner` | Auditar si tiene lógica única |
| `lote_worker.py` | Subprocess helper, nunca importado directo | Documentar cómo se usa |
| `pdf_archivo.py` | Nunca importado | Conectar al paso `convertir_pdf` o eliminar |
| `plantillas_por_etiqueta.py` | Nunca importado | Verificar propósito |
| `portal_verificador.py` | Existe `playwright_real/orquestador.py` | Verificar si es redundante |
| `puente_docker.py` | Solo relevante en dev, no en producción | Mover a `tools/` |
| `verificar_backup.py` | Nunca llamado | Conectar al cron o eliminar |
| `backup_diario.py` | Nunca llamado desde server | Conectar al startup de APScheduler |

**Antes de eliminar cualquiera:** revisar si tiene funcionalidad única que no está replicada en los módulos activos.

---

## 📋 Orden de Implementación

### Fase 1 — Hacer que el sistema genere datos reales (no inventados)

| # | Item | Por qué primero |
|---|------|-----------------|
| 1 | **C-5** Crear tabla `chat_history` | Desbloquea el borrado y el historial |
| 2 | **C-1** Reescribir `resolver_paciente` con lógica nuevo/cache/refresh | Sin esto el sistema trabaja con datos vacíos |
| 3 | **C-2** `sintetizar_maestro` retorna `ok: False` si JSON es `None` | Sin esto el pipeline sigue con nulos |
| 4 | **A-1** Pasos 1–4 del workflow validan output mínimo | Propaga datos reales o para con error claro |
| 5 | **C-8** Cancelar tasks activos antes de borrar paciente | Elimina el fantasma |
| 6 | **A-11** Frontend verifica `response.ok` en borrado | Usuario ve errores reales |

### Fase 2 — Hacer que los documentos generados sean correctos

| # | Item | Por qué |
|---|------|---------|
| 7 | **C-3** `generar_formatos` es `ok: True` solo si todos generaron | No entregar set incompleto |
| 8 | **C-4** `qa_formatos` realmente bloquea con `[VERIFICAR]` críticos | QA que funciona |
| 9 | **C-7** Firma faltante = error explícito | Documentos válidos legalmente |
| 10 | **A-2** Chunks fallidos marcados y comunicados al LLM | Transcripción honesta |
| 11 | **A-3** Discrepancias de portales visibles en Telegram | Sandra puede verificar |
| 12 | **M-2** Campos críticos vs secundarios en validación | QA con prioridades |

### Fase 3 — Robustez y recuperación ante fallos

| # | Item | Por qué |
|---|------|---------|
| 13 | **C-9** Renombrar `hermes.ts` → `api.ts` | Limpieza arquitectural |
| 14 | **A-10** Context managers en SQLite | Evita database lock |
| 15 | **A-14** Limpiar tasks en limbo al arrancar | No fantasmas en el dashboard |
| 16 | **A-6** Sesión Playwright con backup antes de sobreescribir | No perder sesiones |
| 17 | **A-7** Timeout Positiva a 60s + retry | Extracción que funciona |
| 18 | **M-11** APScheduler con job store persistente | Crons sobreviven reinicios |

### Fase 4 — Seguridad

| # | Item | Por qué |
|---|------|---------|
| 19 | **C-6** `.env` fuera de git + rotar credenciales | Urgente si el repo es público |
| 20 | **M-7** Cookie `secure` + `samesite` | Sesiones seguras |
| 21 | **M-8** PIN sin fallback a 1234 | No acceso por default |
| 22 | **M-10** Validar formato de CC | Inputs maliciosos |

### Fase 5 — Calidad y mantenimiento

| # | Item | Por qué |
|---|------|---------|
| 23 | **🗑️** Auditar y eliminar archivos muertos | Código claro |
| 24 | **B-1** Hardcoding a `.env` | Fácil configurar para otros casos |
| 25 | **A-4** Patrones de detección de estado del caso | Menos falsos positivos |
| 26 | **M-4** Normalizar CC en búsqueda de notas | Encuentra todas las notas |

---

## Limpieza manual inmediata (antes de la próxima prueba)

```bash
# Eliminar el fantasma actual
rm storage/data/36280228-completo.json
rm storage/docs/*36280228*.docx
rm storage/pdfs/*36280228*.pdf
rm storage/workflow_audios/36280228_*.m4a

# Verificar que .env no está en git
git check-ignore -v .env
# Si no sale nada: echo ".env" >> .gitignore && git rm --cached .env
```

---

*Plan v3 — 2026-05-23 — 9 críticos · 14 altos · 12 medios · 6 bajos · 17 archivos muertos*
