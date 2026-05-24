# RILO SAS — Plan Integral de Mejoras v6

> Auditoría quirúrgica completa. 6 rondas de análisis paralelo.
> Cada item tiene archivo, línea exacta y descripción del fix real.
> Agente de implementación: **OpenCode**.

---

## Índice

- [🔴 CRÍTICOS — 9 items](#-críticos)
- [🟠 ALTOS — 14 items](#-altos)
- [🟡 MEDIOS — 12 items](#-medios)
- [🟢 BAJOS — 6 items](#-bajos)
- [💬 Chat y progreso del workflow — 9 items](#-chat-y-progreso-del-workflow)
- [📄 Generador de documentos — 10 items](#-generador-de-documentos)
- [🔌 Extractores Playwright — 8 items](#-extractores-playwright)
- [🛠️ Backend core — 12 items](#️-backend-core)
- [🖥️ Dashboard frontend — 10 items](#️-dashboard-frontend)
- [🚀 Deployment y configuración — 10 items](#-deployment-y-configuración)
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

## 💬 Chat y Progreso del Workflow

El bug reportado: el chat muestra "Paso 1/9 — Transcribiendo audio" y nunca avanza. El fix parcial del agente (cambiar `/9` por `/10`, agregar "Progreso:" al mensaje inicial) solo arregla la presentación visual. Hay **9 causas raíz** reales.

---

### P-1 · La causa raíz: el polling cada 10s salta pasos enteros (CRÍTICO)

**Archivo:** `dashboard/app/chat/page.tsx` líneas 160–239

El polling pregunta el estado de la tarea cada 10 segundos. Si el workflow pasa de paso 1 a paso 3 en 8 segundos (normal — resolver_paciente y leer_notas_crudas son rápidos), el primer poll ve paso 3 directamente. El usuario nunca ve "Paso 2/10". Si el workflow completa los pasos 1–4 en menos de 10 segundos, el primer poll puede encontrar el sistema ya en paso 5. Desde la perspectiva del usuario: el chat se queda congelado en "Paso 1/10" por 10 segundos, luego salta directamente a "Paso 5/10 — Sintetizando".

**Fix:** Reducir el intervalo de polling a 3 segundos durante los primeros pasos (rápidos) y mantenerlo en 10s durante el paso 5 (síntesis LLM que tarda 5+ minutos). O mejor: implementar SSE desde el backend para que los updates sean push, no pull.

```typescript
// Intervalo adaptativo según el paso actual
const delay = task.paso_actual <= 4 ? 3000 : 10000;
```

---

### P-2 · `catch {}` vacío silencia todos los errores del polling

**Archivo:** `dashboard/app/chat/page.tsx` línea 236

```typescript
} catch {}  // silencia todo: errores de red, 500s, timeouts
```

Si el servidor se cae mientras hay un workflow corriendo, el polling falla silenciosamente y sigue intentando cada 10 segundos indefinidamente. Sandra no ve ningún mensaje de error.

**Fix:**
```typescript
} catch (e) {
  erroresConsecutivos++;
  if (erroresConsecutivos >= 3) {
    clearInterval(intervalo);
    setMensajes(prev => [...prev, {
      rol: "asistente",
      contenido: "No puedo contactar al servidor. Revisá que el backend esté corriendo.",
      timestamp: new Date().toISOString(),
    }]);
  }
}
```

---

### P-3 · El split de string para editar el progreso es frágil

**Archivo:** `dashboard/app/chat/page.tsx` líneas 224–229

```typescript
contenido: (nuevo[i].contenido.includes("*Progreso:*") 
  ? nuevo[i].contenido.split("*Progreso:*")[0]   // toma todo ANTES de la PRIMERA ocurrencia
  : nuevo[i].contenido) +
  `\n\n*Progreso:* Paso ${task.paso_actual}/10 — ${pasoLabel}`,
```

Si el mensaje tiene más de una ocurrencia de `"*Progreso:*"` (o si el usuario escribió esa palabra en el chat), el split toma solo la primera parte y borra el resto del mensaje — incluyendo el ID de tarea.

**Fix:** Usar el índice de la **última** ocurrencia en lugar de `split`:
```typescript
const markerIndex = nuevo[i].contenido.lastIndexOf("\n\n*Progreso:*");
const base = markerIndex >= 0
  ? nuevo[i].contenido.slice(0, markerIndex)
  : nuevo[i].contenido;
nuevo[i] = { ...nuevo[i], contenido: base + `\n\n*Progreso:* Paso ${task.paso_actual}/10 — ${pasoLabel}` };
```

---

### P-4 · El polling no para en estados desconocidos — loop infinito

**Archivo:** `dashboard/app/chat/page.tsx` líneas 191–235

El polling solo para en: `"listo"`, `estado?.startsWith("error")`, `"esperando_datos"`. Cualquier otro estado (incluyendo `"cancelado"`, `"listo_incompleto"`, `"listo_con_advertencias"` que se proponen en este plan) hace que el polling corra **para siempre**.

**Fix:** Invertir la lógica — definir explícitamente los estados que CONTINÚAN el polling, no los que lo paran:

```typescript
const ESTADOS_EN_PROGRESO = new Set([
  "transcribiendo", "resolviendo_paciente", "leyendo_notas",
  "leyendo_formatos", "sintetizando", "verificando_portales",
  "generando", "qa", "pdf", "notificando"
]);

if (!ESTADOS_EN_PROGRESO.has(task.estado)) {
  clearInterval(intervalo);  // para en cualquier estado final, conocido o no
  // luego decide qué mostrar según el estado
}
```

---

### P-5 · `paso_actual` se actualiza en DB ANTES de ejecutar el paso

**Archivo:** `backend/workflow_runner.py` líneas 57–62

```python
db.actualizar_paso(task_id, paso=paso_num, estado=estado_label)  # ← se escribe antes
resultado_step = modulo.ejecutar(**kwargs)                          # ← recién acá corre
```

Si el frontend pollea entre estas dos líneas, ve `paso_actual = 2` pero el paso 2 aún no terminó (ni siquiera empezó a ejecutar). Si el paso 2 falla 1 segundo después, la DB ya decía que estaba en paso 2 cuando en realidad falló.

Esto es aceptable para mostrar "qué está haciendo ahora", pero el estado debe reflejar "ejecutando" no "completado". El problema es que no hay distinción entre "iniciando paso N" y "paso N completado".

**Fix:** Agregar `paso_completado` como campo separado en `workflow_tasks`, o usar estados diferenciados: `"iniciando_transcripcion"` vs `"transcripcion_completa"`.

---

### P-6 · Sin timeout por paso — el workflow puede congelarse para siempre

**Archivo:** `backend/workflow_runner.py` línea 62

```python
resultado_step = modulo.ejecutar(**kwargs)  # sin timeout
```

Si `sintetizar_maestro` se cuelga esperando respuesta del LLM (timeout de red, DeepSeek caído), la tarea queda en `"sintetizando"` indefinidamente. No hay mecanismo que la desbloquee.

**Fix:** Ejecutar cada paso con timeout usando `concurrent.futures`:
```python
import concurrent.futures
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
    future = executor.submit(modulo.ejecutar, **kwargs)
    try:
        resultado_step = future.result(timeout=TIMEOUT_POR_PASO.get(step_name, 300))
    except concurrent.futures.TimeoutError:
        db.marcar_error(task_id, paso=paso_num, error=f"Timeout en {step_name} (>{TIMEOUT_POR_PASO.get(step_name, 300)}s)")
        return
```

Tiempos razonables por paso:
- `transcribir`: 600s (audio largo)
- `sintetizar_maestro`: 300s (LLM)
- `generar_formatos`: 120s
- Resto: 60s

---

### P-7 · Threading + SQLite sin WAL mode — posibles locks bajo carga

**Archivo:** `backend/server.py` líneas 382–387  
**Archivo:** `backend/task_db.py` líneas 61–64

El workflow corre en un `threading.Thread` daemon. La conexión SQLite se abre y cierra en cada operación sin pooling. Bajo carga concurrente (múltiples workflows, frontend polleando), SQLite puede retornar `database is locked` que el workflow captura como excepción y marca el paso como fallido.

**Fix:**
1. Activar WAL mode al crear la DB: `conn.execute("PRAGMA journal_mode=WAL")`
2. Agregar `timeout=30` a todas las conexiones: `sqlite3.connect(path, timeout=30)`
3. El WAL mode permite lecturas concurrentes sin bloquear al escritor

---

### P-8 · Error message hardcodeado con `/9` en lugar de `/10`

**Archivo:** `dashboard/app/chat/page.tsx` línea 207

```typescript
contenido: `Hubo un problema en el paso ${task.paso_actual}/9: ...`
//                                                           ↑ debería ser /10
```

**Fix:** Cambiar a `/10` o mejor, usar una constante `TOTAL_PASOS = 10` definida una sola vez.

---

### P-9 · El frontend no maneja el estado `"listo_con_advertencias"` ni `"listo_incompleto"`

**Archivo:** `dashboard/app/chat/page.tsx` líneas 191–200

El frontend solo conoce `"listo"` como estado final exitoso. Los nuevos estados propuestos en este plan (`"listo_con_advertencias"`, `"listo_incompleto"`, `"listo_sin_notificacion"`) caerían en el `else` del polling y mostrarían el label de progreso en lugar del mensaje de finalización.

**Fix:** Ampliar la detección de estados finales:
```typescript
const ESTADOS_LISTOS = ["listo", "listo_con_advertencias", "listo_incompleto", "listo_sin_notificacion"];
if (ESTADOS_LISTOS.includes(task.estado)) {
  clearInterval(intervalo);
  // mostrar resultados con badge según el estado
}
```

---

## 📄 Generador de Documentos

Esta sección cubre el bug de celdas alargadas y todos los problemas relacionados encontrados en `doc_generator.py`, los templates y la conversión a PDF.

---

### G-1 · Celdas alargadas: texto largo se inserta sin truncar ni dividir (BUG REPORTADO)

**Archivo:** `backend/doc_generator.py` líneas 50–99 (`_poner_texto`), 694–744 (`_poner_texto_multiparrafo`), y múltiples llamadas en líneas ~806, 866, 879, 884, 890, 931, 937

**Causa raíz — dos problemas combinados:**

**Problema A — Sin truncamiento de longitud:** `_poner_texto()` inserta el valor tal como viene del JSON sin ningún límite de caracteres. Si el diagnóstico del paciente es una cadena de 400+ caracteres ("ESGUINCE GRADO I / FRACTURA OBLICUA / TENDINITIS..."), se inserta completa en una celda de ancho fijo. Word expande la celda verticalmente pero también puede distorsionar el ancho de la columna cuando el texto no tiene espacios donde partir.

**Problema B — Separador de párrafos incorrecto:** `_poner_texto_multiparrafo()` busca `"\n\n"` (doble salto) para dividir en párrafos, pero los datos del JSON llegan con `"\n"` (simple). Resultado: todo el texto queda como un bloque único sin dividir.

```python
# línea 694 — busca \n\n pero los datos tienen \n
parrafos = texto.split("\n\n")   # nunca divide si el texto usa \n simple
```

**Fix:**
```python
def _poner_texto(celda, valor, bold=False, font_size=None, max_chars=300):
    texto = str(valor) if valor is not None else ""
    if len(texto) > max_chars:
        # truncar en el último espacio antes del límite
        texto = texto[:max_chars].rsplit(" ", 1)[0] + "…"
    # ... resto igual

def _poner_texto_multiparrafo(celda, texto, ...):
    # normalizar: aceptar \n y \n\n como separadores
    parrafos = [p for p in texto.replace("\n\n", "\n").split("\n") if p.strip()]
```

`max_chars` por defecto 300, configurable por campo. Para campos narrativos largos (apreciaciones, recomendaciones) usar 800.

---

### G-2 · `format_selector.py`: detección de "Prueba de Trabajo" NUNCA funciona — bug de sintaxis Python

**Archivo:** `backend/format_selector.py` líneas ~151–154

Este es un bug de Python silencioso. El código hace algo así:

```python
es_prueba = (
    "PRUEBA DE TRABAJO", "prueba de trabajo" in metodologia
    or "PRUEBA DE TRABAJO" in concepto
)
```

Python interpreta la primera línea como una **tupla** `("PRUEBA DE TRABAJO", resultado_del_in)`, que siempre es truthy (una tupla no vacía). La detección automática de casos de "Prueba de Trabajo" **nunca funciona correctamente** — o siempre detecta, o nunca detecta, dependiendo de cómo esté escrita exactamente.

**Fix:**
```python
KEYWORDS_PRUEBA = ["prueba de trabajo", "prueba funcional", "prueba laboral", "evaluacion de desempe"]
es_prueba = any(kw in metodologia.lower() for kw in KEYWORDS_PRUEBA) \
         or any(kw in concepto.lower() for kw in KEYWORDS_PRUEBA)
```

---

### G-3 · Índices hardcodeados de tabla/fila/celda — silencian errores cuando cambia el template

**Archivo:** `backend/doc_generator.py` líneas 780–781, 823–824, 834–835, 1567, 1578, 1698, 1777

```python
_poner_texto(doc.tables[0].rows[9].cells[17], str(edad_val))   # línea 781
_poner_texto(doc.tables[0].rows[28].cells[12], ant_cargo)      # línea 824
_poner_texto(doc.tables[1].rows[6].cells[3], valor)            # línea ~934
```

Todos están envueltos en `except (IndexError, AttributeError): pass`. Si el template tiene una fila menos (p.ej. alguien lo editó), el campo simplemente no se escribe. Sin log, sin advertencia, el documento queda incompleto.

**Fix a corto plazo:** Cambiar `pass` por log:
```python
except (IndexError, AttributeError) as e:
    _log(f"⚠️ Celda no encontrada ({e}) — campo omitido en {template_name}")
```

**Fix a largo plazo:** Implementar búsqueda de celda por contenido de etiqueta en lugar de índice:
```python
def _buscar_celda_por_etiqueta(doc, etiqueta):
    for tabla in doc.tables:
        for fila in tabla.rows:
            for i, celda in enumerate(fila.cells):
                if etiqueta.lower() in celda.text.lower():
                    # la celda valor es la siguiente
                    if i + 1 < len(fila.cells):
                        return fila.cells[i + 1]
    return None
```

---

### G-4 · `_convertir_a_pdf()` retorna `None` si LibreOffice no está — el caller nunca lo verifica

**Archivo:** `backend/doc_generator.py` líneas ~542–578 y llamadas en ~1037, 1085

```python
def _convertir_a_pdf(docx_path):
    if not soffice:
        print(f"⚠️ LibreOffice no encontrado")
        return None   # ← retorna None silenciosamente

# Caller (línea ~1037):
doc.save(str(dst))
_convertir_a_pdf(str(dst))   # ← retorno ignorado
return str(dst)              # ← devuelve ruta al DOCX, no al PDF
```

El workflow de QA y el endpoint de descarga esperan que haya un PDF. Si LibreOffice falla, no hay PDF pero tampoco hay error — el sistema dice "listo" con documentos sin PDF.

**Fix:**
```python
pdf_path = _convertir_a_pdf(str(dst))
if pdf_path is None:
    raise RuntimeError(f"Conversión PDF falló para {dst.name} — LibreOffice no disponible o error")
return str(pdf_path)
```

---

### G-5 · Tablas buscadas por índice global frágil (`doc.tables[2]`)

**Archivo:** `backend/doc_generator.py` líneas ~841, 934, 953

```python
tabla1 = doc.tables[1]   # asume que la tabla 1 es siempre la correcta
t2 = doc.tables[2]
t3 = doc.tables[3]
```

Si alguien agrega una tabla al inicio del template (para un encabezado, por ejemplo), todos los índices se desplazan y se escriben datos en las tablas equivocadas sin ningún error.

**Fix:** Buscar tablas por un texto identificador único que esté en su primera celda, no por índice.

---

### G-6 · Valor vacío inconsistente: a veces `[VERIFICAR]`, a veces `""`

**Archivo:** `backend/doc_generator.py` líneas 128 y 468

```python
# línea 128:
valor_str = str(valor) if valor is not None else "[VERIFICAR]"

# línea 468:
nuevo = str(nuevo) if nuevo is not None else ""
```

Dos funciones distintas del mismo archivo tienen comportamiento distinto para "campo vacío". Dependiendo de cuál se llame, el campo queda como `[VERIFICAR]` (visible y fácil de encontrar) o como `""` (invisible, parece que está correcto pero está vacío).

**Fix:** Centralizar la decisión en una función `_normalizar_valor(v)` que use siempre `[VERIFICAR]` para campos que debieran tener contenido.

---

### G-7 · Templates tienen archivos `.bak` — posible corrupción anterior

**Archivo:** `backend/templates/formatos/*.bak`

Existen archivos `.bak` para cada template, lo que sugiere que hubo corrupción o edición accidental en el pasado y se hicieron backups. Los `.bak` no son usados por el código pero su presencia indica que los templates actuales pueden ser versiones modificadas que difieren de los originales diseñados para los índices hardcodeados del código.

**Fix:** Comparar los templates actuales contra los `.bak` para ver si cambiaron estructura de tablas. Si sí cambiaron, los índices de G-3 están desactualizados.

---

### G-8 · Deepgram: audio en silencio o confianza 0.0 no se maneja

**Archivo:** `backend/workflow_steps/transcribir.py`

Si el audio está en silencio (grabación fallida, micrófono apagado), Deepgram devuelve `{"alternatives": []}` o un resultado con `confidence: 0.0`. El código no valida esto y propaga un texto vacío o de muy baja calidad al LLM, que luego inventa los datos del paciente.

**Fix:** Después de recibir la respuesta de Deepgram:
```python
if not texto_transcripcion.strip():
    return {"ok": False, "error": "Transcripción vacía — el audio puede estar en silencio o ser inaudible"}
if confianza_global < 0.4:
    resultado["advertencias"].append(f"Confianza de transcripción baja ({confianza_global:.0%}) — revisar calidad del audio")
```

---

### G-9 · `POST /api/archivos/sync` puede reportar éxito aunque `git push` falle

**Archivo:** `backend/server.py` endpoint `POST /api/archivos/sync`  
**Archivo:** `dashboard/app/archivos/page.tsx` líneas 80–93

El frontend muestra "Sincronizado con GitHub" si `data.ok` es `True`. Si el backend ejecuta `git push` y falla (sin permisos, conflicto de rama, sin conectividad), el error puede quedar en stderr sin cambiar `ok`. Sandra cree que los documentos están en GitHub cuando no lo están.

**Fix en backend:** Capturar el código de retorno de `git push` y propagar el stderr al frontend si es distinto de 0.

---

### G-10 · Inconsistencia en el total de pasos reportado (9 vs 10)

**Archivo:** `dashboard/app/chat/page.tsx` línea 207  
**Archivo:** `backend/server.py` línea ~399  
**Archivo:** `backend/workflow_runner.py` línea ~23

El fix parcial del agente cambió algunas referencias de `/9` a `/10` pero al menos una instancia quedó:

```typescript
// chat/page.tsx línea 207
contenido: `Hubo un problema en el paso ${task.paso_actual}/9: ...`  // ← sigue siendo /9
```

**Fix:** Definir `TOTAL_PASOS = 10` como constante compartida en ambos lados (backend y frontend) y no hardcodear el número en ningún mensaje.

---

## 🔌 Extractores Playwright

Los extractores son el punto de entrada de todos los datos clínicos. Si fallan aquí, todo el pipeline genera basura.

---

### X-1 · Medifolios no une `nombre1 + nombre2 + apellido1 + apellido2` en un campo `nombre`

**Archivo:** `backend/playwright_real/medifolios.py` líneas 47–68

El extractor guarda los campos de nombre por separado: `nombre1`, `nombre2`, `apellido1`, `apellido2`. Pero el orquestador y el fusionador hacen `datos_medi.get("nombre", "")` esperando un campo unificado — obtienen `""`. La síntesis del LLM recibe el paciente sin nombre.

**Fix:** Al final de la extracción, agregar:
```python
partes = [campos.get(k, "") for k in ("nombre1", "nombre2", "apellido1", "apellido2") if campos.get(k)]
if partes:
    campos["nombre"] = " ".join(partes)
```

---

### X-2 · Positiva extrae solo el primer siniestro — ignora pacientes con múltiples

**Archivo:** `backend/playwright_real/positiva.py` líneas 38–64, 99–140

El extractor usa regex sobre el HTML plano y guarda `datos["siniestro_id"]` (singular). Positiva puede tener múltiples siniestros por paciente (uno activo, uno cerrado). El código ignora todos excepto el primero encontrado.

**Documentado en `skills/flujo-browser/`:** Positiva tiene una tabla de siniestros — debe parsearse como lista.

**Fix:** Usar `page.query_selector_all()` sobre las filas de la tabla de siniestros en lugar de regex, y guardar `datos["siniestros"] = [...]` como lista. El fusionador ya tiene lógica para lista de siniestros — solo falta que lleguen.

---

### X-3 · RHI de Positiva falla silenciosamente con `except: pass`

**Archivo:** `backend/playwright_real/positiva.py` líneas 67–96

```python
async def _buscar_en_rhi(page: Page, cc: str) -> Dict:
    try:
        await page.goto("...rhi/consultarCaso/init", timeout=30000)
        # ...
    except Exception:
        pass  # falla silenciosa
    return rhi  # retorna {} sin indicar error
```

El caller no puede distinguir entre "RHI no tiene datos para este paciente" y "la consulta falló". Si falla, el workflow continúa sin los datos de rehabilitación del paciente.

**Fix:** Retornar `{"_error": "RHI no disponible", "_rhi_ok": False}` en el except, y que el orquestador lo marque como advertencia.

---

### X-4 · Siniestro de Medifolios (extraído de agenda) falla sin error si la cita no está en pantalla

**Archivo:** `backend/playwright_real/medifolios.py` líneas 71–92

El siniestro se extrae buscando en el body de la página de agenda. Si la cita del paciente no aparece (es antigua, o está filtrada), `body` no contiene el número → retorna `""` sin ningún indicador de fallo.

**Fix:** Si no se encuentra siniestro en la agenda, intentar buscarlo en la sección de "Observaciones" o "Historia Clínica" como fallback, y marcar `siniestro_fuente = "agenda"` o `"historia"` para rastrear la calidad del dato.

---

### X-5 · Detección de discrepancias genera falsos positivos por normalización incompleta

**Archivo:** `backend/playwright_real/orquestador.py` líneas 36–40

```python
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s).lower().strip())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.split())
```

"JUAN CARLOS DURAN NARVAEZ" (Medifolios) vs "JUAN C. DURAN" (Positiva) → se detecta como discrepancia aunque sea el mismo paciente. Esto genera alertas falsas de discrepancia que Sandra ve en Telegram y no sabe qué hacer.

**Fix:** Implementar similitud de Jaccard o distancia de Levenshtein para nombres: si similitud > 80%, no marcar como discrepancia sino como "probable match".

---

### X-6 · CIE-10: regex demasiado amplio captura etiquetas no relevantes

**Archivo:** `backend/playwright_real/positiva.py` línea 51

```python
cie10_matches = re.findall(r'([A-Z]\d{2,3}(?:\.\d)?)\s*[-–]\s*([A-Za-záéíóúñ ]{5,60})', body)
```

Captura cualquier patrón `X00 - Descripción` del HTML, incluyendo etiquetas de navegación, categorías de menú, etc. El código toma el primero encontrado como diagnóstico principal.

**Fix:** Buscar el diagnóstico solo dentro del contexto de la sección "Diagnóstico" o tabla de datos clínicos usando selectores CSS, no regex sobre todo el body.

---

### X-7 · Timeout de Playwright (30s) insuficiente para Positiva bajo carga

**Archivo:** `backend/playwright_real/session.py` + `.env` `PLAYWRIGHT_TIMEOUT_MS=30000`

ARL Positiva puede tardar 40–60s en cargar. Con 30s de timeout la extracción falla sistemáticamente en conexiones lentas o cuando el servidor del gobierno está lento.

**Fix:** `PLAYWRIGHT_TIMEOUT_MS=60000` para Positiva específicamente, con 2 reintentos automáticos antes de marcar error.

---

### X-8 · Sesión de portal: backup del state se sobreescribe antes de verificar el nuevo login

**Archivo:** `backend/playwright_real/session.py` líneas 92–174

Si la sesión expiró y el re-login falla, el `storage_state` anterior ya fue sobreescrito con un state inválido. La próxima extracción también falla porque no hay sesión válida guardada.

**Fix:** Guardar backup antes de sobreescribir: `state_path.rename(str(state_path) + ".bak")`. Si el nuevo login falla, restaurar el backup.

---

## 🛠️ Backend Core

Bugs encontrados en `server.py`, `chat_handler.py`, `correction_loop.py`, `notificador.py`, `email_reader.py`, `backup_diario.py` y `fusionador.py`.

---

### BC-1 · Race condition crítica: dos uploads del mismo CC corren en paralelo y se sobreescriben

**Archivo:** `backend/server.py` línea 1060

Si Sandra sube dos audios del mismo CC rápidamente (o hace doble clic), se crean dos `threading.Thread` que corren el workflow simultáneamente. Ambos escriben en el mismo `{cc}-completo.json`. El último que termine gana; los datos del primero se pierden silenciosamente.

**Fix:**
1. Al recibir un request de procesamiento, verificar si ya hay un task activo para ese CC: si sí, rechazar con `409 Conflict` y mensaje claro.
2. Usar file lock en la escritura del JSON (ver C-5 del plan principal).

---

### BC-2 · `chat_handler.py`: `max()` sobre fechas en formato string causa TypeError

**Archivo:** `backend/chat_handler.py` línea 210

```python
best = max(cand, key=lambda x: x[1])  # x[1] es "31/05/2026" (string dd/mm/yyyy)
```

`max()` sobre strings en formato `dd/mm/yyyy` ordena lexicográficamente, no cronológicamente. "31/05/2026" < "01/06/2026" en orden léxico → selecciona el archivo incorrecto como "más reciente".

**Fix:**
```python
from datetime import datetime
best = max(cand, key=lambda x: datetime.strptime(x[1], "%d/%m/%Y") if x[1] else datetime.min)
```

---

### BC-3 · `chat_handler.py`: variable `resp` puede no estar inicializada antes de usarse

**Archivo:** `backend/chat_handler.py` línea 443

Si el primer request al LLM lanza excepción antes de asignar `resp`, y luego el código intenta `resp.status_code` en el manejo del error, lanza `UnboundLocalError`.

**Fix:** Inicializar `resp = None` antes del bloque try, y verificar `if resp is not None` antes de acceder a sus atributos.

---

### BC-4 · `correction_loop.py`: valor extraído puede ser parcial o de tipo incorrecto

**Archivo:** `backend/correction_loop.py` líneas 210–243

Los regex de extracción de valor capturan el primer match numérico o string, pero:
- "ponle el teléfono 3182675427 y el correo es x@mail.com" → captura "3182675427", ignora el correo
- No valida que el tipo del valor coincida con el campo: puede poner un teléfono en el campo "empresa.nombre"

**Fix:** Después de extraer el valor, validar el tipo esperado del campo (definido en `json_validator.py`) antes de aplicar la corrección.

---

### BC-5 · `correction_loop.py`: si `campo_detectado` es `None`, pregunta "¿cuál es el valor para 'None'?"

**Archivo:** `backend/correction_loop.py` línea 391

```python
# Si no se identificó el campo, la pregunta generada contiene literalmente "None"
pregunta = f"¿cuál es el valor correcto para '{campo_detectado}'?"  # campo_detectado es None
```

**Fix:** Verificar `if campo_detectado is None` antes de construir la pregunta. Si es None, pedir aclaración: "No entendí qué campo querés corregir. ¿Podés ser más específica? Ejemplo: 'el teléfono es...' o 'la empresa es...'"

---

### BC-6 · `notificador.py`: chunks de mensajes largos pierden formato Markdown

**Archivo:** `backend/notificador.py` líneas 41–54

Telegram tiene límite de 4096 caracteres. El notificador parte el mensaje por líneas, pero solo aplica `parse_mode="Markdown"` al primer chunk. Los siguientes chunks se envían como texto plano — el formato se rompe a mitad del mensaje.

**Fix:** Aplicar `parse_mode="Markdown"` a todos los chunks, y asegurarse de que ningún chunk rompa un bloque de markdown a mitad (e.g., no partir un `*negrita*` entre dos chunks).

---

### BC-7 · `email_reader.py`: mes en mayúsculas no se detecta → citas asignadas a enero

**Archivo:** `backend/email_reader.py` línea 189

```python
MESES = {"enero": "01", "febrero": "02", ..., "mayo": "05"}
mes_nombre.lower()  # OK, convierte a minúsculas
```

Aparentemente está bien, pero si el email de Medifolios envía el mes con tildes distintas o encoding diferente (p.ej. "Mayo" con encoding latin-1 que no se convierte correctamente a lowercase), el lookup falla y retorna `"01"` (enero). Citas en cualquier mes quedan agendadas para enero.

**Fix:** Normalizar el string antes del lookup eliminando acentos: `unicodedata.normalize("NFD", mes_nombre.lower())`.

---

### BC-8 · `email_reader.py`: citas sin teléfono se pierden silenciosamente

**Archivo:** `backend/email_reader.py` línea 194

El regex principal espera exactamente: FECHA HORA, NOMBRE, TELÉFONO, SERVICIO. Si una línea del email de Medifolios no tiene teléfono (campo opcional), el regex no coincide y esa cita se pierde.

**Fix:** Hacer el teléfono opcional en el regex con `(?:\s*,\s*[\d\-\+]+)?`.

---

### BC-9 · `backup_diario.py`: hace backup de SQLite mientras está en uso — puede corromperse

**Archivo:** `backend/backup_diario.py` líneas 20–31

`workflow.db` puede estar siendo escrito por el workflow runner exactamente cuando el backup corre a las 23:00. `tarfile.add()` copia el archivo tal como está en disco, incluyendo el WAL journal, pero si la transacción no estaba committed, el backup contiene datos corruptos.

**Fix:** Usar el comando de SQLite `VACUUM INTO '/tmp/backup.db'` para hacer una copia limpia antes de comprimir. Esto hace flush de WAL y produce un snapshot consistente.

---

### BC-10 · `fusionador.py`: construcción de nombre puede quedar incompleta con strings vacíos

**Archivo:** `backend/fusionador.py` líneas 98–104

```python
partes = [paciente.get("nombre1"), paciente.get("nombre2"), ...]
partes_validas = [p for p in partes if p]  # filtra None
nombre_completo = " ".join(partes_validas)
```

Si algún campo es `""` (string vacío, no None), no se filtra y el nombre queda con espacios dobles: `"JUAN  DURAN"`. Además, después de construir el nombre, hace `pop()` de los campos individuales — si luego algún código accede a `paciente["nombre1"]`, lanza `KeyError`.

**Fix:** Filtrar también strings vacíos: `[p for p in partes if p and p.strip()]`, y no eliminar los campos originales con `pop()`.

---

### BC-11 · `fusionador.py`: paciente con múltiples siniestros solo conserva el último

**Archivo:** `backend/fusionador.py` líneas 162–169

Si `todos` (lista de todos los siniestros) tiene múltiples entradas y ninguna es tipo "AT", selecciona la primera. El campo `"todos"` luego se hace `pop()` y se pierde. Si el paciente tiene un siniestro activo y uno cerrado, solo llega uno al fusionado.

**Fix:** En lugar de descartar `todos`, guardarlo en `siniestro["historial"]` para que el LLM pueda verlo en el contexto.

---

### BC-12 · `server.py`: stream de chat no se cancela cuando el cliente desconecta

**Archivo:** `backend/server.py` líneas 327–349

```python
resp = requests.post(..., stream=True, timeout=300)
for line in resp.iter_lines():
    yield data
```

Si Sandra cierra el tab o navega a otra página, el generador sigue consumiendo la respuesta del LLM durante hasta 5 minutos. En un servidor con varios usuarios simultáneos, esto acumula N conexiones abiertas al LLM.

**Fix:** Envolver el stream en un try/except que capture `GeneratorExit` (lanzado cuando FastAPI detecta que el cliente cerró):
```python
try:
    for line in resp.iter_lines():
        yield data
except GeneratorExit:
    resp.close()
```

---

## 🖥️ Dashboard Frontend

---

### D-1 · Chat: memory leak de intervals — se acumulan con cada audio procesado

**Archivo:** `dashboard/app/chat/page.tsx` líneas 160–255

`iniciarPollingTarea` crea un `setInterval` al inicio de cada workflow. Si el delay cambia (de 3s a 10s), crea un nuevo interval sin garantizar que el anterior fue cancelado. Después de procesar 10 audios, hay 10+ intervals corriendo en paralelo. El navegador se congela.

**Fix:** Guardar la referencia del interval en un `useRef` y hacer `clearInterval(ref.current)` explícitamente antes de crear uno nuevo en cada iteración del polling.

---

### D-2 · Chat: SSE stream no se cancela si Sandra cambia de página

**Archivo:** `dashboard/app/chat/page.tsx` líneas 331–372

`res.body.getReader()` no tiene `AbortController` vinculado. Si Sandra navega a otra página mientras Tomy está respondiendo, el reader sigue activo en background consumiendo memoria.

**Fix:**
```typescript
const controller = new AbortController();
const res = await fetch(url, { signal: controller.signal, ... });
// En el cleanup del useEffect:
return () => controller.abort();
```

---

### D-3 · Chat: links de descarga rotos si `archivo` es null en el historial

**Archivo:** `dashboard/app/chat/page.tsx` líneas 490–504

Si `msg.formatos[i].archivo` es undefined (p.ej. el formato falló al generarse), el link queda como `href="#"` que no hace nada. Sandra ve el botón "Descargar" pero no pasa nada al hacer clic.

**Fix:** Mostrar el botón de descarga solo si `f.archivo` existe; si no, mostrar un badge "No disponible" en rojo.

---

### D-4 · Chat: race condition — Enter puede enviar mensaje doble durante lag

**Archivo:** `dashboard/app/chat/page.tsx` líneas 606–609

```typescript
onKeyDown={(e) => e.key === "Enter" && enviar()}
// disabled={enviando}  ← se aplica en el siguiente render
```

Entre el keydown y el re-render con `disabled=true`, si Sandra presiona Enter dos veces rápido, se envían dos mensajes.

**Fix:** Usar `useRef` para un flag de "enviando" que se actualiza sincrónicamente, no de forma asíncrona a través del estado:
```typescript
const enviandoRef = useRef(false);
const enviar = async () => {
    if (enviandoRef.current) return;
    enviandoRef.current = true;
    // ...
    enviandoRef.current = false;
};
```

---

### D-5 · subir-audio: sin validación de tipo ni tamaño en el frontend

**Archivo:** `dashboard/app/subir-audio/page.tsx` líneas 85, 103

El input dice `accept="audio/*,.m4a,.mp3,.wav"` pero es solo visual — el navegador no lo impone. La página incluso dice "sin límite de tamaño" pero el backend rechaza >200MB. Sandra puede subir un video de 500MB y solo descubre el error después de esperar la carga completa.

**Fix:**
```typescript
if (!file.type.startsWith("audio/")) {
    setError("Solo se aceptan archivos de audio (.mp3, .m4a, .wav)");
    return;
}
if (file.size > 200 * 1024 * 1024) {
    setError("El archivo es demasiado grande. Máximo 200 MB.");
    return;
}
```

---

### D-6 · formatos: cambiar de paciente no resetea el filtro de formato seleccionado

**Archivo:** `dashboard/app/formatos/page.tsx` líneas 78–82

```typescript
const seleccionarPaciente = (cc: string) => {
    setPacienteSeleccionado(cc);
    cargarFormatos(cc);
    setFiltroFormato("");  // ← resetea el filtro
};
```

Parece que sí resetea, pero si el componente de filtro tiene su propio estado interno (no controlado), puede quedar en el valor anterior. Verificar que el filtro sea completamente controlado.

---

### D-7 · auth.ts: sin refresh automático de sesión expirada

**Archivo:** `dashboard/lib/auth.ts` líneas 25–35

Si la sesión expira mientras Sandra trabaja (token de 30 días, improbable pero posible), los endpoints devuelven 401. El frontend hace las llamadas silenciosamente sin redirigir al login — las páginas muestran datos vacíos o errores genéricos.

**Fix:** En el wrapper de fetch, si cualquier respuesta es 401, redirigir automáticamente a `/login`.

---

### D-8 · archivos: sincronización con GitHub reporta éxito aunque `git push` falle

**Archivo:** `dashboard/app/archivos/page.tsx` línea 106  
**Archivo:** `backend/server.py` endpoint `POST /api/archivos/sync`

El frontend muestra "Sincronizado con GitHub" si `data.ok` es True. Pero el backend puede retornar `ok: True` aunque `git push` haya fallado si el error va a stderr y el código solo verifica el exit code.

**Fix en backend:** Verificar explícitamente el returncode de `git push` y capturar stderr. Si es distinto de 0, retornar `ok: False` con el mensaje del error.

---

### D-9 · pacientes: typo en mensaje de error ("en el servidor en el servidor")

**Archivo:** `dashboard/app/pacientes/page.tsx` línea 43

```typescript
setError("No se pudo conectar con el servidor en el servidor.");
// ↑ "en el servidor" está duplicado
```

---

### D-10 · hoy/paciente: intervals de auto-refresh no se limpian al desmontar rápido

**Archivos:** `dashboard/app/hoy/page.tsx` línea 42, `dashboard/app/paciente/[cc]/page.tsx` líneas 71–72

Si Sandra navega rápidamente entre `/hoy` y `/paciente/CC`, los intervals de refresh anterior pueden quedar activos brevemente. En la mayoría de casos React los limpia en el return del useEffect, pero si el unmount es muy rápido puede haber una llamada extra.

**Fix:** Verificar que todos los `setInterval` tengan su correspondiente `return () => clearInterval(id)` en el useEffect.

---

## 🚀 Deployment y Configuración

---

### DEP-1 · `.env` ESTÁ RASTREADO EN GIT — credenciales expuestas en el historial

**Archivo:** `.env`, `.gitignore`, historial de git

El commit `d50c0bf` agregó `.env` de vuelta al repositorio explícitamente. El archivo contiene credenciales activas: Deepgram, Telegram, OpenCode, Gmail, Medifolios, Positiva, AUTH_SECRET.

**Fix — en orden:**
1. `git rm --cached .env` + commit
2. Verificar que `.env` esté en `.gitignore`
3. Dado que las credenciales ya están en el historial, **rotar todas las keys**:
   - Generar nuevo `DEEPGRAM_API_KEY`
   - Revocar y regenerar `OPENCODE_GO_API_KEY`
   - Regenerar `TELEGRAM_BOT_TOKEN`
   - Cambiar contraseñas de Medifolios y Positiva
   - Revocar `GMAIL_APP_PASSWORD` y generar uno nuevo
4. Limpiar el historial: `git filter-repo --path .env --invert-paths`

---

### DEP-2 · `storage/docs/` y `storage/data/` con datos de pacientes reales están en git

**Archivo:** `.gitignore`, `storage/`

Los directorios `storage/docs/`, `storage/data/`, `storage/pdfs/` contienen documentos clínicos con CC, teléfono, dirección y siniestro de Maribel Fuentes (CC 36280228). Están rastreados por git.

**Fix:**
```bash
git rm -r --cached storage/docs/ storage/data/ storage/pdfs/
echo "storage/docs/" >> .gitignore
echo "storage/data/" >> .gitignore
echo "storage/pdfs/" >> .gitignore
git commit -m "Remove patient data from git tracking"
```

---

### DEP-3 · `docker-compose.yml` usa variables de entorno que no existen

**Archivo:** `docker-compose.yml`

| Variable en compose | Realidad en .env | Problema |
|---------------------|-----------------|----------|
| `OPENROUTER_API_KEY` | No existe | Debería ser `OPENCODE_GO_API_KEY` |
| `MEDIFOLIOS_PASS` | No existe | Debería ser `MEDIFOLIOS_PASSWORD` |
| `POSITIVA_PASS` | No existe | Debería ser `POSITIVA_PASSWORD` |

Además no mapea: `TOMY_COMPLETO_ENABLED`, `WORKFLOW_DB_PATH`, `AUTH_PIN`, `AUTH_SECRET`, `OPENCODE_GO_BASE_URL`. El servicio `browser-use` usa `python:3.11-slim` sin instalar Playwright.

**Fix:** Sincronizar `docker-compose.yml` con `.env` actual. Agregar todos los volúmenes necesarios para `storage/workflow.db`.

---

### DEP-4 · `start.sh` intenta arrancar el dashboard sin hacer `npm run build` primero

**Archivo:** `start.sh` líneas 23–26

```bash
cd dashboard && npx next start -p 3000 &
```

`next start` requiere que `.next/` exista (generado por `npm run build`). Si no se hizo build, arranca con el build anterior o falla. El script no lo verifica ni lo ejecuta.

**Fix:**
```bash
cd dashboard
if [ ! -d ".next" ] || [ "$(find . -name '*.tsx' -newer .next -not -path './node_modules/*' | head -1)" ]; then
    echo "Building dashboard..."
    npm run build
fi
npx next start -p 3000 &
```

---

### DEP-5 · `start-wsl.sh` asume que Docker está corriendo y que hay un contenedor Hermes

**Archivo:** `start-wsl.sh`

```bash
sudo docker exec hermes-... comando
```

Si Docker no está instalado, no está corriendo, o el contenedor no existe, el script falla con error poco descriptivo.

**Fix:** Verificar dependencias al inicio del script:
```bash
command -v docker >/dev/null 2>&1 || { echo "Docker no instalado"; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker no está corriendo"; exit 1; }
```

---

### DEP-6 · `.env.example` incompleto — 6 variables críticas sin documentar

**Archivo:** `.env.example`

Variables que usa el código pero no están en `.env.example`:

| Variable | Usada en | Por qué es crítica |
|----------|----------|-------------------|
| `AUTH_PIN` | `auth_simple.py:19` | Sin ella el servidor no arranca |
| `AUTH_SECRET` | `auth_simple.py:15` | Sin ella los tokens son inseguros |
| `DASHBOARD_URL` | Notificaciones Telegram | URLs en mensajes incorrectas |
| `CORS_ORIGINS` | `server.py:43` | Dashboard no puede conectar |
| `WORKSPACE_DIR` | `server.py`, `chat_handler.py` | Sin ella no encuentra archivos de Sandra |
| `OPENCODE_GO_BASE_URL` | `chat_handler.py:22` | Usa fallback hardcodeado |

**Fix:** Agregar todas al `.env.example` con valores de ejemplo y comentarios de cómo obtenerlas.

---

### DEP-7 · `TOMY_COMPLETO_ENABLED` y `LLM_MODEL_SINTESIS` difieren entre `.env` y `.env.example`

**Archivos:** `.env`, `.env.example`

| Variable | `.env` (producción) | `.env.example` | Riesgo |
|----------|---------------------|----------------|--------|
| `TOMY_COMPLETO_ENABLED` | `true` | `false` | Nuevo deploy arranca con pipeline desactivado |
| `LLM_MODEL_SINTESIS` | `deepseek-v4-flash` | `deepseek-v4-pro` | Modelo distinto sin saberlo |

**Fix:** `.env.example` debe documentar el valor recomendado para producción, no el de desarrollo.

---

### DEP-8 · `playwright install` no se ejecuta automáticamente post-instalación

**Archivo:** `backend/requirements.txt`

`playwright>=1.42.0` instala el paquete Python pero NO los browsers (Chromium, Firefox). Hay que ejecutar `playwright install` manualmente. Si no se hace, todos los extractores fallan con `playwright._impl._errors.Error: Executable doesn't exist`.

**Fix:** Agregar al final de `start.sh` o crear un `setup.sh`:
```bash
python -m playwright install chromium --with-deps
```

---

### DEP-9 · `puente_docker.py` documentado en CLAUDE.md pero no existe

**Archivos:** `CLAUDE.md` línea 43, `backend/puente_docker.py`

CLAUDE.md lista `puente_docker.py` como módulo activo con 192 líneas, pero el archivo no existe en el repositorio. Si algún componente lo intenta importar, falla con `ModuleNotFoundError`.

**Fix:** Eliminar la referencia de CLAUDE.md o restaurar el archivo si era necesario.

---

### DEP-10 · `start.sh`: health check débil con sleep fijo, mata procesos de otros usuarios

**Archivo:** `start.sh` líneas 10–11, 26–31

```bash
fuser -k 8000/tcp 2>/dev/null  # mata CUALQUIER proceso en ese puerto, no solo del usuario
sleep 5                         # espera fija, no health check real
curl -s --max-time 3 ...        # un solo intento, sin reintentos
```

**Fix:**
```bash
# Matar solo procesos propios
lsof -ti:8000 | xargs kill -9 2>/dev/null

# Health check con reintentos
for i in $(seq 1 10); do
    curl -sf http://localhost:8000/api/health && break
    sleep 2
done
```

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

### ⚠️ URGENTE — Hacer ahora, antes de cualquier otra cosa

Credenciales de servicios reales y datos de pacientes están en el historial público de git.

| # | Item | Acción concreta |
|---|------|-----------------|
| U-1 | **DEP-1** `.env` fuera de git + rotar TODAS las credenciales | `git rm --cached .env` → commit → rotar Deepgram, Telegram, OpenCode, Gmail, portales |
| U-2 | **DEP-2** `storage/docs/`, `storage/data/`, `storage/pdfs/` fuera de git | `git rm -r --cached storage/docs/ storage/data/ storage/pdfs/` → agregar a `.gitignore` |
| U-3 | **DEP-1** Limpiar historial con `git filter-repo` | Sin esto las credenciales siguen accesibles en commits anteriores |

### Fase 0 — El chat debe mostrar qué está pasando (sin esto nada es testeable)

Sin progreso visible, no se puede saber si el resto de los fixes funciona.

| # | Item | Por qué primero |
|---|------|-----------------|
| 0.1 | **P-1** Intervalo adaptativo de polling (3s pasos rápidos, 10s lento) | El usuario ve cada paso real |
| 0.2 | **D-1** `useRef` para el interval del polling — evitar memory leak | Sin esto acumula intervals con cada audio |
| 0.3 | **P-4** Polling para en cualquier estado final, no solo los conocidos | No loops infinitos |
| 0.4 | **P-3** `lastIndexOf` en lugar de `split` para editar el progreso | El mensaje no se rompe |
| 0.5 | **P-2** `catch` con contador de errores consecutivos | Sandra sabe si el servidor cayó |
| 0.6 | **P-6** Timeout por paso en `workflow_runner` | El workflow no se congela forever |
| 0.7 | **P-7** WAL mode + timeout=30 en SQLite | Evita locks bajo carga |
| 0.8 | **P-8** Hardcoded `/9` → `/10` | Mensaje de error correcto |
| 0.9 | **P-9** Frontend conoce `listo_con_advertencias` y `listo_incompleto` | Estados nuevos no rompen el chat |

### Fase 1 — Hacer que el sistema genere datos reales (no inventados)

| # | Item | Por qué primero |
|---|------|-----------------|
| 1.1 | **C-5** Crear tabla `chat_history` | Desbloquea el borrado y el historial |
| 1.2 | **BC-1** Rechazar segundo upload del mismo CC con 409 | Sin esto dos threads sobreescriben el mismo JSON |
| 1.3 | **C-1** Reescribir `resolver_paciente` con lógica nuevo/cache/refresh | Sin esto el sistema trabaja con datos vacíos |
| 1.4 | **X-1** Medifolios: unir `nombre1+nombre2+apellido1+apellido2` → `nombre` | Sin esto el paciente llega sin nombre al LLM |
| 1.5 | **X-2** Positiva: parsear tabla de siniestros como lista | Pacientes con múltiples siniestros pierden datos |
| 1.6 | **C-2** `sintetizar_maestro` retorna `ok: False` si JSON es `None` | Sin esto el pipeline sigue con nulos |
| 1.7 | **A-1** Pasos 1–4 del workflow validan output mínimo | Propaga datos reales o para con error claro |
| 1.8 | **C-8** Cancelar tasks activos antes de borrar paciente | Elimina el fantasma |
| 1.9 | **A-11** Frontend verifica `response.ok` en borrado | Usuario ve errores reales |

### Fase 2 — Hacer que los documentos generados sean correctos

| # | Item | Por qué |
|---|------|---------|
| 2.1 | **G-1** Truncar texto largo + normalizar `\n` en celdas | El bug que viste — celdas alargadas |
| 2.2 | **G-2** Arreglar `format_selector.py` bug de tupla Python | Prueba de Trabajo nunca se detectaba |
| 2.3 | **G-3** Loguear excepciones silenciadas en índices de tabla | Saber cuándo un campo no se escribió |
| 2.4 | **G-4** Verificar retorno de `_convertir_a_pdf()` | No hay PDF sin saberlo |
| 2.5 | **C-3** `generar_formatos` es `ok: True` solo si todos generaron | No entregar set incompleto |
| 2.6 | **C-4** `qa_formatos` realmente bloquea con `[VERIFICAR]` críticos | QA que funciona |
| 2.7 | **C-7** Firma faltante = error explícito | Documentos válidos legalmente |
| 2.8 | **G-8** Deepgram: audio en silencio = error explícito | No inventar datos de un audio mudo |
| 2.9 | **X-3** RHI de Positiva: retornar `_error` en vez de `{}` | El orquestador sabe que falló |
| 2.10 | **X-4** Siniestro no encontrado en agenda = buscar fallback en HC | No perder el siniestro |
| 2.11 | **A-2** Chunks fallidos marcados y comunicados al LLM | Transcripción honesta |
| 2.12 | **A-3** Discrepancias de portales visibles en Telegram | Sandra puede verificar |
| 2.13 | **M-2** Campos críticos vs secundarios en validación | QA con prioridades |
| 2.14 | **BC-4** `correction_loop`: validar tipo del campo antes de aplicar | No pone un teléfono en el campo empresa |
| 2.15 | **BC-5** `correction_loop`: campo `None` muestra mensaje de aclaración | No aparece "None" en el chat |
| 2.16 | **G-6** Unificar `[VERIFICAR]` vs `""` para campos vacíos | QA encuentra todos los vacíos |

### Fase 3 — Robustez y recuperación ante fallos

| # | Item | Por qué |
|---|------|---------|
| 3.1 | **C-9** Renombrar `hermes.ts` → `api.ts` | Limpieza arquitectural |
| 3.2 | **A-10** Context managers en SQLite | Evita database lock |
| 3.3 | **A-14** Limpiar tasks en limbo al arrancar | No fantasmas en el dashboard |
| 3.4 | **X-8** / **A-6** Backup de sesión Playwright antes de sobreescribir | No perder sesiones válidas |
| 3.5 | **X-7** / **A-7** Timeout Positiva a 60s + 2 reintentos | Extracción que funciona en conexión lenta |
| 3.6 | **X-5** Comparación de nombres con similitud de Jaccard | Menos alertas de discrepancia falsas |
| 3.7 | **X-6** CIE-10: buscar por selector CSS, no regex sobre todo el body | Diagnóstico correcto |
| 3.8 | **BC-2** `max()` sobre fechas string → `datetime.strptime` | Selecciona el archivo realmente más reciente |
| 3.9 | **BC-3** Inicializar `resp = None` antes del try en `chat_handler` | Evita `UnboundLocalError` |
| 3.10 | **BC-6** Telegram chunks: `parse_mode` en todos, no solo el primero | Formato correcto en mensajes largos |
| 3.11 | **BC-7** `email_reader`: normalizar encoding del mes antes de lookup | Citas en mes correcto |
| 3.12 | **BC-8** `email_reader`: teléfono opcional en regex | No perder citas sin teléfono |
| 3.13 | **BC-9** `backup_diario`: `VACUUM INTO` en lugar de copiar archivo en uso | Backups no corruptos |
| 3.14 | **BC-10** `fusionador`: filtrar `""` además de `None` en construcción de nombre | No espacios dobles en nombre |
| 3.15 | **BC-11** `fusionador`: guardar historial de siniestros, no descartarlo | LLM ve historial completo |
| 3.16 | **BC-12** Stream de chat: capturar `GeneratorExit` y cerrar conexión LLM | No acumular conexiones abiertas |
| 3.17 | **M-11** APScheduler con job store persistente | Crons sobreviven reinicios |
| 3.18 | **P-5** `paso_completado` separado de `paso_actual` en task_db | Estados de paso más precisos |
| 3.19 | **D-2** `AbortController` en SSE del chat | No reader zombies al cambiar de página |
| 3.20 | **D-4** `useRef` para flag de envío — evitar Enter doble | No mensajes duplicados |

### Fase 4 — Seguridad

| # | Item | Por qué |
|---|------|---------|
| 4.1 | **C-6** `.env` fuera de git + rotar credenciales (si aún no se hizo en U-1) | Urgente si el repo es público |
| 4.2 | **M-7** Cookie `secure` + `samesite` | Sesiones seguras en HTTPS |
| 4.3 | **M-8** PIN sin fallback a 1234 | No acceso por default |
| 4.4 | **M-10** Validar formato de CC | Inputs maliciosos |
| 4.5 | **DEP-6** Completar `.env.example` con las 6 variables faltantes | Nuevo deploy no arranca ciego |
| 4.6 | **DEP-7** `.env.example` con valores recomendados de producción | No diferencias silenciosas entre entornos |
| 4.7 | **D-7** Redirigir a `/login` en cualquier 401 | No páginas vacías con sesión expirada |
| 4.8 | **D-3** Links de descarga: ocultar si `archivo` es null | No botones que no hacen nada |

### Fase 5 — Setup, deployment y calidad

| # | Item | Por qué |
|---|------|---------|
| 5.1 | **DEP-3** Sincronizar `docker-compose.yml` con `.env` actual | Dev no arranca con variables faltantes |
| 5.2 | **DEP-4** `start.sh`: hacer build si no existe `.next` | No arrancar dashboard roto |
| 5.3 | **DEP-5** `start-wsl.sh`: verificar Docker antes de usar | Error descriptivo si falta |
| 5.4 | **DEP-8** `setup.sh` con `playwright install chromium` | Sin esto Playwright falla en deploy limpio |
| 5.5 | **DEP-9** Actualizar CLAUDE.md — `puente_docker.py` no existe | Documentación que miente |
| 5.6 | **DEP-10** `start.sh`: health check con reintentos, no sleep fijo | Arranque robusto |
| 5.7 | **D-5** Validar tipo y tamaño de archivo en `/subir-audio` antes de cargar | No esperar 5 min para enterarse del error |
| 5.8 | **D-8** `archivos/sync`: verificar returncode de `git push` | No reportar éxito si falló |
| 5.9 | **D-9** Typo en mensaje de error ("en el servidor en el servidor") | Calidad del texto |
| 5.10 | **D-10** Verificar que todos los intervals tienen `clearInterval` en cleanup | No leaks al navegar rápido |
| 5.11 | **🗑️** Auditar y eliminar archivos muertos | Código claro |
| 5.12 | **B-1** Hardcoding a `.env` | Fácil configurar para otros casos |
| 5.13 | **A-4** Patrones de detección de estado del caso | Menos falsos positivos |
| 5.14 | **M-4** Normalizar CC en búsqueda de notas | Encuentra todas las notas |
| 5.15 | **B-3** Backup: notificar a Manu por Telegram si falla | Sin puntos ciegos en backups |
| 5.16 | **G-7** Comparar templates actuales contra `.bak` | Detectar si índices G-3 están desactualizados |

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

*Plan v6 — 2026-05-24 — 9 críticos · 14 altos · 12 medios · 6 bajos · 9 chat/progreso · 10 generador docs · 8 extractores Playwright · 12 backend core · 10 dashboard frontend · 10 deployment/config · 17 archivos muertos — Total: 117 items*
