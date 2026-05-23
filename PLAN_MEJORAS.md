# RILO SAS — Plan Integral de Mejoras

> Análisis exhaustivo del sistema completo. Cada item tiene archivo, línea y descripción exacta del fix.

---

## Índice

1. [Bugs Críticos — Bloquean el sistema](#1-bugs-críticos)
2. [Base de Datos y Persistencia](#2-base-de-datos-y-persistencia)
3. [Sistema de Borrado de Pacientes](#3-sistema-de-borrado-de-pacientes)
4. [Autenticación y Seguridad](#4-autenticación-y-seguridad)
5. [Pipeline de Audio (Tomy Completo)](#5-pipeline-de-audio-tomy-completo)
6. [Generación de Documentos](#6-generación-de-documentos)
7. [Chat e IA](#7-chat-e-ia)
8. [Extractores de Portales](#8-extractores-de-portales)
9. [Notificaciones](#9-notificaciones)
10. [Dashboard — Frontend](#10-dashboard--frontend)
11. [Concurrencia y Race Conditions](#11-concurrencia-y-race-conditions)
12. [Validaciones y Límites](#12-validaciones-y-límites)
13. [Cron Jobs y Operaciones Programadas](#13-cron-jobs-y-operaciones-programadas)
14. [Integridad de Datos](#14-integridad-de-datos)
15. [Orden de Implementación](#15-orden-de-implementación)

---

## 1. Bugs Críticos

Estos bugs hacen que el sistema falle silenciosamente o de forma catastrófica. Son prioritad absoluta.

---

### C-1 · `WORKFLOW_AUDIOS_DIR` definida después de ser usada

**Archivo:** `backend/server.py`  
**Línea problema:** 350 y 1020 (uso) vs 1001 (definición)  
**Severidad:** CRÍTICA

`WORKFLOW_AUDIOS_DIR` se usa en la línea 350 (dentro de `chat_audio`) y en la 1020 (dentro de `procesar_paciente`), pero recién se define en la línea 1001. Python resuelve variables de módulo en tiempo de ejecución, no de definición, así que en condiciones normales funciona. Pero si alguien reorganiza el archivo o hace un import parcial, lanza `NameError`.

**Fix:** Mover las líneas 1001-1002 al bloque de definición de directorios que ya existe (líneas 53-59), junto con `DOCS_DIR`, `PDFS_DIR`, etc.

---

### C-2 · Tabla `chat_history` nunca fue creada

**Archivo:** `backend/task_db.py`  
**Líneas:** 24–40 (schema actual)  
**Severidad:** CRÍTICA

`task_db.py` crea `workflow_tasks` con `CREATE TABLE IF NOT EXISTS`, pero `chat_history` no aparece en ningún `CREATE TABLE` de todo el proyecto. Cualquier operación sobre esa tabla (guardar, leer, listar, borrar historial) lanza `sqlite3.OperationalError: no such table: chat_history`.

Impacto específico: cuando `eliminar_paciente` llega a la línea 570 y ejecuta `DELETE FROM chat_history`, el endpoint explota con 500 — y dado que esa línea está al final, los archivos físicos del paciente SÍ se borran antes del crash, pero el frontend recibe el 500 y no actualiza la UI. Resultado: archivos borrados, pero paciente sigue apareciendo en pantalla.

**Fix:** Agregar en el `SCHEMA` de `task_db.py`:
```sql
CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_cc TEXT NOT NULL,
    rol TEXT NOT NULL,
    contenido TEXT,
    accion TEXT,
    archivo TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chat_cc ON chat_history(paciente_cc);
```

---

### C-3 · Conexiones SQLite sin context manager — database lock bajo carga

**Archivo:** `backend/server.py`  
**Líneas:** 407, 424, 445, 458, 568  
**Severidad:** CRÍTICA

Todas las queries de `chat_history` usan `conn = sqlite3.connect(...)` sin `with` y sin `try/finally`. Si ocurre una excepción entre `connect()` y `close()`, la conexión queda abierta indefinidamente. SQLite solo acepta una writer a la vez — conexiones huérfanas bloquean todas las escrituras posteriores, devolviendo `database is locked` a todos los endpoints.

**Fix:** Cambiar todas las ocurrencias al patrón:
```python
with sqlite3.connect(db_path) as conn:
    # queries aquí
    conn.commit()
```
Esto garantiza que `conn.close()` se llama siempre, incluso si hay excepción.

---

### C-4 · Documentos generados sin firma (falla silenciosa)

**Archivo:** `backend/doc_generator.py`  
**Línea:** ~37 (`FIRMA = ASSETS / "firma_sandra.png"`) y función `_insertar_firma`  
**Severidad:** CRÍTICA

Cuando `firma_sandra.png` no existe, la función que inserta la firma simplemente no la inserta — sin lanzar excepción ni agregar advertencia al resultado. El documento se entrega completo visualmente pero sin firma. En contexto médico-legal esto invalida el documento.

**Fix:** En `_insertar_firma`, si `FIRMA` no existe:
```python
if not FIRMA.exists():
    raise FileNotFoundError(f"Firma no encontrada: {FIRMA}")
```
O como mínimo agregar `"advertencias": ["FIRMA FALTANTE"]` al resultado de `generar_documento`.

---

### C-5 · Race condition en archivos JSON de paciente

**Archivo:** `backend/server.py` — múltiples endpoints  
**Severidad:** CRÍTICA

Varios endpoints leen y escriben `{cc}-completo.json` sin ningún mecanismo de bloqueo. Si dos requests llegan simultáneamente (por ejemplo, el usuario hace clic doble en "Generar"), el segundo overwrite puede borrar los cambios del primero, o peor, producir un JSON corrupto (truncado a mitad de escritura).

**Fix:** Usar el paquete `filelock` (ya está disponible en Python) para bloquear el archivo por CC durante escritura:
```python
from filelock import FileLock
with FileLock(str(data_file) + ".lock", timeout=10):
    with open(data_file, "w") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
```

---

## 2. Base de Datos y Persistencia

---

### D-1 · Sin timeout en conexiones SQLite

**Archivo:** `backend/task_db.py`  
**Líneas:** 50–53  
**Severidad:** ALTA

`sqlite3.connect(str(self.db_path))` sin `timeout` parámetro. Si la DB está bloqueada (ver C-3), el request cuelga indefinidamente. FastAPI no tiene timeout por defecto para handlers síncronos.

**Fix:** `sqlite3.connect(str(self.db_path), timeout=30.0)` — espera máximo 30 segundos antes de lanzar `OperationalError: database is locked`.

---

### D-2 · `database.db` huérfana

**Archivo:** `backend/database.db`  
**Severidad:** BAJA

Hay un archivo `backend/database.db` de 32KB que no es referenciado por ningún código actual. Es un remanente de una versión anterior.

**Fix:** Eliminar el archivo y asegurarse de que no hay ningún `sqlite3.connect("database.db")` en el código.

---

### D-3 · Sin versionado de schema JSON

**Archivos:** `storage/data/*.json`  
**Severidad:** MEDIA

Los JSONs de paciente no tienen campo `_version`. Si la estructura cambia en una versión futura del sistema, los archivos viejos rompen sin mensajes de error claros.

**Fix:** Agregar `"_version": "1.0"` en la raíz de cada JSON generado, y una función de migración en `_cargar_datos_paciente` que normalice el formato al cargarlo.

---

## 3. Sistema de Borrado de Pacientes

Este es el bug del "fantasma". Son 4 bugs encadenados:

---

### B-1 · `eliminar_paciente` crashea en `chat_history` (ya listado como C-2)

**Archivo:** `backend/server.py` línea 570  
**Consecuencia directa del bug C-2.** El endpoint devuelve 500 después de ya haber borrado los archivos físicos. El frontend no actualiza la UI.

---

### B-2 · Frontend no maneja el error 500 del borrado

**Archivo:** `dashboard/app/formatos/page.tsx`  
**Líneas:** 84–94  
**Severidad:** ALTA

```typescript
const eliminarPaciente = async (cc: string) => {
    await fetch(`${API}/api/pacientes/${cc}`, { method: "DELETE" });
    // continúa igual si hubo 500
}
```

No hay `if (!response.ok)`. Si el backend devuelve 500, el modal cierra y la lista se recarga — mostrando al paciente como si nada hubiera pasado. Sandra no ve ningún error.

**Fix:**
```typescript
const res = await fetch(`${API}/api/pacientes/${cc}`, { method: "DELETE" });
if (!res.ok) {
    setError(`Error al eliminar: ${res.status}`);
    return;
}
```

---

### B-3 · Tareas activas del workflow no se cancelan antes de borrar

**Archivo:** `backend/server.py`  
**Líneas:** 553–572  
**Severidad:** ALTA

`eliminar_paciente` borra el registro en `workflow_tasks` en SQLite, pero si hay un `asyncio.Task` corriendo en memoria para ese CC (una transcripción o generación en progreso), ese task sigue ejecutándose. Cuando termina, recrea el JSON del paciente en `storage/data/`. Esto explica por qué el JSON reaparece incluso cuando el borrado físico funcionó.

**Fix:** Al inicio de `eliminar_paciente`, consultar `task_db.listar_activos()` y cancelar los tasks del CC antes de borrar archivos. La lógica de cancelación ya existe en `POST /api/tasks/{task_id}/cancelar` — invocarla internamente.

---

### B-4 · `eliminar_formatos` no limpia `workflow_audios`

**Archivo:** `backend/server.py`  
**Línea:** 531  
**Severidad:** MEDIA

El endpoint `DELETE /api/pacientes/{cc}/formatos` itera `[DOCS_DIR, PDFS_DIR, AUDIO_DIR]` pero omite `WORKFLOW_AUDIOS_DIR`. Los audios `.m4a` del paciente quedan en `storage/workflow_audios/`.

**Fix:** Cambiar línea 531 a:
```python
for d in [DOCS_DIR, PDFS_DIR, AUDIO_DIR, WORKFLOW_AUDIOS_DIR]:
```

---

## 4. Autenticación y Seguridad

---

### S-1 · Cookie de sesión sin flag `secure`

**Archivo:** `backend/server.py`  
**Línea:** ~1130  
**Severidad:** CRÍTICA

`response.set_cookie("rilo_session", token)` no tiene `secure=True` ni `samesite="lax"`. Sin `secure`, el navegador puede enviar la cookie en HTTP plano. Sin `samesite`, es vulnerable a CSRF.

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

### S-2 · PIN por defecto hardcodeado como fallback

**Archivo:** `backend/auth_simple.py`  
**Línea:** ~20  
**Severidad:** ALTA

Si `.env` no tiene `AUTH_PIN`, el sistema acepta "1234" sin avisar. Si el `.env` se pierde o no se carga, el sistema queda protegido solo por el PIN por defecto.

**Fix:** Si `AUTH_PIN` no está en el entorno, lanzar excepción al iniciar — nunca usar fallback:
```python
AUTH_PIN = os.getenv("AUTH_PIN")
if not AUTH_PIN:
    raise RuntimeError("AUTH_PIN no configurado en .env — el servidor no puede iniciar")
```

---

### S-3 · Tokens de sesión sin expiración

**Archivo:** `backend/auth_simple.py`  
**Líneas:** 27–34  
**Severidad:** MEDIA

Los tokens generados no llevan timestamp de expiración. Si alguien obtiene el token (p.ej. de un log, del historial del navegador), tiene acceso permanente.

**Fix:** Incluir `exp: datetime.now() + timedelta(days=30)` en el payload del token y validarlo al verificar.

---

### S-4 · Path traversal en descarga de archivos

**Archivo:** `backend/server.py`  
**Línea:** ~214  
**Severidad:** ALTA

`GET /api/download/{filename}` usa `Path(filename).name` para evitar traversal, lo que está bien. Pero no verifica que el archivo pertenezca al paciente autenticado — cualquier usuario puede descargar documentos de cualquier otro CC si conoce el nombre del archivo.

**Fix:** Requerir `cc` como query param y verificar que `cc` esté contenido en el nombre del archivo antes de devolver.

---

### S-5 · CORS con IPs privadas en wildcard (no funcionan)

**Archivo:** `backend/server.py`  
**Línea:** ~43  
**Severidad:** MEDIA

El `.env` tiene `CORS_ORIGINS=http://192.168.*,http://10.*,...`. FastAPI CORSMiddleware NO soporta wildcards de patrón — trata `192.168.*` como el literal hostname `192.168.*`, que nunca va a coincidir con nada. Las peticiones desde otras IPs de la red local serán bloqueadas silenciosamente.

**Fix:** Listar las IPs concretas: `http://192.168.1.100:3000,http://192.168.1.100:8000` o usar un wildcard de origen completo `*` si la red es confiable.

---

### S-6 · Sin protección CSRF en endpoints POST

**Archivo:** `backend/server.py` — todos los POST  
**Severidad:** MEDIA

No hay validación de tokens CSRF. Un sitio malicioso podría hacer un formulario que envíe una petición POST al backend usando las cookies de Sandra.

**Fix:** Agregar el header `X-Requested-With: XMLHttpRequest` como requisito en endpoints sensibles, o implementar tokens CSRF con `starlette-csrf`.

---

## 5. Pipeline de Audio (Tomy Completo)

---

### A-1 · `ffprobe` falla → duración 0 → audio largo no se chunkea

**Archivo:** `backend/workflow_steps/transcribir.py`  
**Líneas:** 31–33  
**Severidad:** ALTA

Si `ffprobe` no está disponible, `_calcular_duracion_s()` devuelve `0.0`. Eso significa "audio corto, no necesita chunking". Un audio de 1 hora se manda completo a Deepgram en un solo request → timeout → transcripción perdida.

**Fix:** En el `except FileNotFoundError`, asumir el peor caso:
```python
except FileNotFoundError:
    _log("ffprobe no disponible — asumiendo audio largo (3600s)")
    return 3600.0
```

---

### A-2 · Chunk fallido → transcripción incompleta sin aviso

**Archivo:** `backend/workflow_steps/transcribir.py`  
**Líneas:** 110–112  
**Severidad:** ALTA

Si un chunk de los 5 falla, se agrega una advertencia pero el workflow continúa. El texto de transcripción tiene un hueco en el medio, y el documento generado va a tener datos faltantes o inventados por el LLM para rellenar.

**Fix:** Marcar explícitamente en el resultado:
```python
resultado["chunks_fallidos"] = [i for i, c in enumerate(chunks) if c.get("error")]
```
Y en el paso siguiente (`sintetizar_maestro`), incluir ese aviso en el prompt al LLM.

---

### A-3 · Sin límite de tamaño en upload de audio

**Archivo:** `backend/server.py`  
**Líneas:** 465–476  
**Severidad:** MEDIA

`/api/upload-audio` y `/api/procesar-paciente` aceptan archivos de cualquier tamaño. Un archivo de 2GB llenaría el disco de Sandra o crashearía el proceso con OOM.

**Fix:** Verificar tamaño antes de guardar:
```python
contenido = await audio.read()
if len(contenido) > 200 * 1024 * 1024:  # 200 MB
    raise HTTPException(413, "Audio demasiado grande (máximo 200 MB)")
```

---

### A-4 · Sin validación de tipo de archivo en upload

**Archivo:** `backend/server.py`  
**Línea:** ~465  
**Severidad:** MEDIA

El endpoint acepta cualquier archivo como "audio". Si se sube un PDF o una imagen por error, Deepgram falla con un error críptico.

**Fix:** Verificar extensión o content-type:
```python
EXTENSIONES_AUDIO = {".mp3", ".m4a", ".wav", ".ogg", ".webm", ".mp4"}
if Path(audio.filename).suffix.lower() not in EXTENSIONES_AUDIO:
    raise HTTPException(400, f"Formato no soportado: {Path(audio.filename).suffix}")
```

---

### A-5 · QA no bloquea documentos con placeholders `[VERIFICAR]`

**Archivo:** `backend/workflow_steps/qa_formatos.py`  
**Línea:** ~64  
**Archivo:** `backend/workflow_runner.py`  
**Líneas:** 88–105  
**Severidad:** MEDIA

El QA detecta placeholders `[VERIFICAR]` como advertencia, pero el documento se marca como `listo` de todas formas. Sandra recibe un documento con campos sin completar.

**Fix:** Si QA encuentra `[VERIFICAR]`, cambiar el estado de la tarea a `listo_con_advertencias` y enviar una notificación diferente en Telegram que indique cuáles campos necesitan revisión manual.

---

### A-6 · `resolver_paciente` devuelve datos vacíos sin error explícito

**Archivo:** `backend/workflow_steps/resolver_paciente.py`  
**Líneas:** 45–47  
**Severidad:** MEDIA

Si `FASE_A_ENABLED=false` y no hay datos cacheados del paciente, devuelve un dict vacío con `_vacio=True`. Los pasos siguientes (`sintetizar_maestro`, `generar_formatos`) reciben datos vacíos y generan documentos con toda la información faltante, sin que nadie sepa por qué.

**Fix:** Si los datos están vacíos y Fase A está desactivada, detener el workflow con `estado = "error_sin_datos"` y un mensaje claro: `"No se encontraron datos para CC {cc}. Activate la extracción de portales o carga el JSON manualmente."`.

---

### A-7 · Chunks de audio procesados secuencialmente, no en paralelo

**Archivo:** `backend/workflow_steps/transcribir.py`  
**Severidad:** BAJA

Un audio de 1 hora se chunkea en 3 partes de 25 minutos y se manda a Deepgram de forma secuencial. Con paralelización serían ~25 minutos; sin ella, ~75 minutos.

**Fix:** Usar `asyncio.gather()` para las llamadas a Deepgram en paralelo, luego ordenar los resultados por índice de chunk antes de unir.

---

## 6. Generación de Documentos

---

### G-1 · Template faltante da error genérico

**Archivo:** `backend/doc_generator.py`  
**Líneas:** 584–609  
**Severidad:** ALTA

Si un archivo de plantilla `.docx` no existe, la excepción `FileNotFoundError` es capturada genéricamente. El log no indica qué template faltó, haciendo difícil el diagnóstico.

**Fix:** En el `except`, loguear explícitamente: `logger.error(f"Template faltante: {template_path}")` antes de re-lanzar.

---

### G-2 · `ejemplo prueba de trabajo` está en `.odt`, no `.docx`

**Archivo:** `storage/docs/` (o workspace de Sandra)  
**Severidad:** MEDIA

El Formato 6 (Prueba de Trabajo) tiene su plantilla de ejemplo en `.odt`. Si `doc_generator` intenta abrir un `.odt` con `python-docx`, falla.

**Fix:** Convertir con LibreOffice (ya instalado):
```bash
libreoffice --convert-to docx "ejemplo prueba de trabajo.odt" --outdir storage/docs/
```

---

### G-3 · Detección de celdas fusionadas verticales puede fallar

**Archivo:** `backend/doc_generator.py`  
**Líneas:** 145–160  
**Severidad:** BAJA

La función `_buscar_y_reemplazar` detecta celdas fusionadas comparando `_tc` (elemento XML interno). Si la celda etiqueta está fusionada verticalmente, `value_start` puede no encontrarse, y el valor no se escribe en ningún lugar.

**Fix:** Agregar fallback: si `value_start is None` después de buscar, usar `label_start + 1` como posición por defecto.

---

## 7. Chat e IA

---

### I-1 · Respuesta vacía del LLM no se comunica al usuario

**Archivo:** `backend/chat_handler.py`  
**Líneas:** 469–484  
**Severidad:** ALTA

Si DeepSeek devuelve `finish_reason="length"` (respuesta truncada por tokens), el fallback intenta extraer el razonamiento interno. Si ese también está vacío, devuelve "Estoy procesando tu solicitud" — que es un mensaje falso de carga, no un error real.

**Fix:** Detectar cuando se usó el fallback y devolver un mensaje honesto: "La respuesta fue demasiado larga y fue cortada. Por favor reformulá la pregunta de forma más específica."

---

### I-2 · Sin límite en el historial de conversación enviado al LLM

**Archivo:** `backend/chat_handler.py`  
**Severidad:** MEDIA

Si una conversación tiene 100 mensajes, todos se envían al LLM en cada request. Con DeepSeek v4 (razonador de 8K-15K tokens de pensamiento), el contexto puede crecer hasta agotar el límite, resultando en respuestas truncadas o errores.

**Fix:** Enviar solo los últimos N mensajes (p.ej. 20) al LLM, o resumir el historial viejo con una llamada previa más barata.

---

### I-3 · Sin ping/keepalive en streaming SSE

**Archivo:** `backend/server.py` / `backend/chat_handler.py`  
**Severidad:** MEDIA

Durante los 2-5 minutos que puede tardar DeepSeek en responder, la conexión SSE puede ser cerrada por proxies o por el navegador si no hay datos fluyendo.

**Fix:** Enviar un evento de progreso cada 15 segundos mientras el LLM procesa:
```python
yield 'data: {"tipo":"ping"}\n\n'
```
El frontend ya debe ignorar eventos que no conoce, pero se puede agregar un spinner visual.

---

## 8. Extractores de Portales

---

### E-1 · Sesión Playwright expirada → fallo silencioso

**Archivos:** `backend/extractor_medifolios.py`, `backend/extractor_positiva.py`  
**Severidad:** ALTA

Las cookies de sesión guardadas en `storage/playwright_sessions/` pueden expirar (normalmente 24–72h). Si expiran durante una extracción, el portal redirige al login y el scraper lee datos del formulario de login en lugar de los del paciente — o simplemente falla con un selector no encontrado.

**Fix:** Después de cargar la sesión, verificar que el portal responde con la página correcta (no el login). Si detecta redirección al login, disparar re-autenticación automática usando `MEDIFOLIOS_USER` / `MEDIFOLIOS_PASSWORD` del `.env`.

---

### E-2 · Race condition entre extracción manual y cron

**Archivo:** `backend/cron_pre_extraccion.py`  
**Líneas:** 88–94  
**Severidad:** MEDIA

Si el usuario hace clic en "Extraer ahora" mientras el cron de las 9 PM está corriendo para el mismo CC, dos instancias de Playwright intentan acceder al portal simultáneamente. Esto puede:
- Invalidar la sesión del otro proceso
- Escribir datos corruptos al mismo archivo JSON
- Generar un segundo `workflow_task` duplicado

**Fix:** Usar un lock de archivo por CC: `STORAGE / "locks" / f"{cc}.extraction.lock"`. El segundo proceso que intente obtener el lock espera o falla con "extracción en curso".

---

### E-3 · Cooldown no considera tiempo real de extracción

**Archivo:** `backend/cron_pre_extraccion.py`  
**Línea:** 94  
**Severidad:** BAJA

`sleep(COOLDOWN_S)` espera 30 segundos fijos entre pacientes, sin importar cuánto tardó la extracción anterior. Si una extracción toma 50 segundos, el gap real es 0.

**Fix:** `sleep(max(0, COOLDOWN_S - elapsed_time))`

---

## 9. Notificaciones

---

### N-1 · Fallo de Telegram es silencioso

**Archivo:** `backend/notificador.py`  
**Líneas:** 30–32  
**Severidad:** ALTA

Si `TELEGRAM_BOT_TOKEN` está mal o el servicio está caído, `enviar_telegram()` devuelve `False` sin ningún log de nivel ERROR. El workflow termina marcando el task como `listo`, pero Sandra nunca recibe la notificación.

**Fix:** Loguear como `logging.error(...)` cuando las credenciales falten, y cambiar el estado del task a `listo_sin_notificacion` si Telegram falla después de 3 reintentos.

---

### N-2 · No distingue errores transitorios de permanentes

**Archivo:** `backend/notificador.py`  
**Líneas:** 51–58  
**Severidad:** MEDIA

Telegram puede devolver 401 (token inválido — error permanente) o 429 (rate limit — error transitorio) o 503 (caído — error transitorio). El código trata todos igual con retry exponencial. Un 401 va a reintentar 3 veces inútilmente antes de rendirse.

**Fix:** Solo reintentar en errores 5xx o de red. En 4xx, fallar inmediatamente y alertar al administrador (Manu vía log o email).

---

### N-3 · `except:` desnudo captura `SystemExit` y `KeyboardInterrupt`

**Archivo:** `backend/notificador.py`  
**Línea:** ~214  
**Severidad:** MEDIA

`except:` sin tipo captura todo, incluyendo señales del sistema. Si el usuario intenta detener el servidor con Ctrl+C durante `check_recordatorios`, la señal queda atrapada.

**Fix:** Cambiar a `except Exception as e:`.

---

## 10. Dashboard — Frontend

---

### F-1 · `hermes.ts` no debería llamarse así — renombrar y limpiar referencias

**Archivos:** `dashboard/lib/hermes.ts`, `dashboard/lib/workflow.ts`, `dashboard/lib/auth.ts`  
**Severidad:** CRÍTICA

Este es el error de raíz, no solo un problema de URL. El archivo `dashboard/lib/hermes.ts` está nombrado después de Hermes (el agente de desarrollo Docker) y tiene una constante llamada `HERMES_API` con una variable de entorno `NEXT_PUBLIC_HERMES_API`. Hermes no existe en la WSL de Sandra — el dashboard se conecta al backend FastAPI (Tomy), no a Hermes. Tener el nombre de la herramienta de desarrollo hardcodeado en el código de producción confunde la arquitectura y hace que agentes y desarrolladores asuman que Hermes debe estar presente en producción.

Adicionalmente, `workflow.ts` tiene `const API = "http://localhost:8000"` hardcodeado sin leer ninguna variable de entorno.

**Fix (en orden):**
1. Renombrar `dashboard/lib/hermes.ts` → `dashboard/lib/api.ts`
2. Renombrar la constante `HERMES_API` → `API_URL` dentro del archivo
3. Eliminar la variable de entorno `NEXT_PUBLIC_HERMES_API` — solo usar `NEXT_PUBLIC_API_URL`
4. Actualizar todos los imports del dashboard: `from "@/lib/hermes"` → `from "@/lib/api"`
5. En `workflow.ts` y `auth.ts`, aplicar el mismo patrón:
```typescript
const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");
```
6. En `.env.local` del dashboard, asegurarse de que solo exista `NEXT_PUBLIC_API_URL` (borrar `NEXT_PUBLIC_HERMES_API` si estaba definida)

---

### F-2 · Páginas sin verificación de auth en el cliente

**Archivos:** Varias páginas del dashboard  
**Severidad:** ALTA

No todas las páginas verifican si hay sesión activa antes de renderizar. Si Sandra accede directamente a `/pacientes` sin estar logueada, el backend devuelve 401 pero el frontend no redirige al login — muestra una lista vacía o un error genérico.

**Fix:** Agregar un hook `useAuth()` en cada página (o en el layout raíz) que verifique `GET /api/whoami` y redirija a `/login` si no hay sesión.

---

### F-3 · Sin manejo de errores de red en fetch

**Archivo:** `dashboard/lib/api.ts` (renombrado desde `hermes.ts` — ver F-1)  
**Severidad:** MEDIA

Las funciones de fetch no tienen `try/catch`. Si el backend está caído, el navegador lanza `TypeError: Failed to fetch` que no es capturado — la página congela silenciosamente.

**Fix:** Envolver todos los `fetch` en try/catch y mostrar un mensaje amigable ("El servidor no está disponible. Verificá que el backend esté corriendo.").

---

### F-4 · Sin límite en `localStorage` para historial de chat

**Archivo:** `dashboard/app/chat/page.tsx`  
**Línea:** ~56  
**Severidad:** BAJA

`localStorage.setItem()` puede lanzar `QuotaExceededError` si el almacenamiento local está lleno (límite típico: 5–10MB). En dispositivos con poco espacio o muchas conversaciones largas, el chat falla silenciosamente.

**Fix:** Envolver en `try/catch` y, si falla, truncar el historial local a los últimos 50 mensajes.

---

### F-5 · Filenames en el explorador de archivos sin escapado

**Archivo:** `dashboard/app/archivos/page.tsx`  
**Severidad:** MEDIA

Si un nombre de archivo contiene `<script>` o caracteres especiales HTML, y se renderiza con `dangerouslySetInnerHTML` o sin escapado, hay riesgo de XSS. Verificar que todos los nombres de archivo se rendericen como texto plano (React lo hace por defecto en JSX, pero verificar cualquier uso de `innerHTML`).

**Fix:** Auditar el componente en busca de cualquier `dangerouslySetInnerHTML`. Si no hay ninguno, el riesgo es bajo.

---

## 11. Concurrencia y Race Conditions

---

### R-1 · Pool de conexiones SQLite bajo carga concurrente

**Archivo:** `backend/task_db.py` y `backend/server.py`  
**Severidad:** ALTA

SQLite en modo WAL acepta múltiples lectores simultáneos, pero solo un escritor. Con múltiples endpoints creando conexiones a la vez, los escritores se bloquean. No hay un pool compartido — cada endpoint abre su propia conexión.

**Fix a corto plazo:** Agregar `timeout=30.0` en todos los `sqlite3.connect()`.  
**Fix a largo plazo:** Si el sistema crece, considerar migrar a PostgreSQL con SQLAlchemy.

---

### R-2 · Extracción en background puede solaparse con borrado

**Archivo:** `backend/server.py` y `backend/workflow_runner.py`  
**Severidad:** ALTA (ya explicado en B-3 — cancelar tasks antes de borrar)

Ver sección 3, bug B-3.

---

## 12. Validaciones y Límites

---

### V-1 · Número de cédula no validado

**Archivo:** `backend/server.py` — todos los endpoints con `{cc}`  
**Severidad:** ALTA

Cualquier string puede ser un CC: "", "abc", "999999999999999999". Esto puede:
- Crear archivos con nombres inválidos en el sistema de archivos
- Causar lookups vacíos que tardan tiempo innecesario
- Generar nombres de archivo con caracteres problemáticos

**Fix:** Agregar un validador al inicio de cada endpoint que toque CC:
```python
def _validar_cc(cc: str):
    if not re.match(r'^\d{6,12}$', cc):
        raise HTTPException(400, f"CC inválida: '{cc}'. Debe ser 6-12 dígitos.")
```

---

### V-2 · Normalización inconsistente del CC

**Archivos:** Múltiples — `chat_handler.py`, `server.py`, `extractor_*.py`  
**Severidad:** MEDIA

El CLAUDE.md menciona que los CC colombianos pueden venir con apóstrofes y puntos (`12'130.558`), y que hay que limpiarlos. No está claro si esta limpieza se aplica consistentemente en todos los puntos de entrada (upload, chat, búsqueda).

**Fix:** Centralizar la normalización en una función única `normalizar_cc(cc: str) -> str` y llamarla en todos los endpoints de entrada.

---

### V-3 · Estimación de duración de audio incorrecta

**Archivo:** `backend/server.py`  
**Línea:** ~365  
**Severidad:** ALTA

```python
duracion_min_est = round(audio_path.stat().st_size / (1024 * 1024 * 0.5))
```

Dividir por `0.5` es multiplicar por 2. Para un audio de 100MB esto da 200 minutos estimados en lugar de ~50. Esto afecta los cálculos de tiempo estimado mostrados al usuario.

**Fix:** La fórmula correcta depende del bitrate. Para MP3 a 128kbps (~1MB/min): `st_size / (1024 * 1024)`. O mejor, usar el resultado real de `ffprobe` cuando esté disponible.

---

## 13. Cron Jobs y Operaciones Programadas

---

### CR-1 · APScheduler es in-memory — pierde jobs al reiniciar

**Archivo:** `backend/cron_pre_extraccion.py`  
**Severidad:** MEDIA

APScheduler por defecto guarda los jobs en memoria. Si el servidor se reinicia (o crashea), los jobs del día no se recuperan. Si el servidor cae a las 8 PM y vuelve a las 10 PM, el cron de las 9 PM no se ejecutó y no hay forma de saberlo.

**Fix:** Usar el `SQLAlchemyJobStore` de APScheduler para persistir jobs en SQLite. O, más simple, agregar un chequeo al arrancar: "¿el último cron de hoy ya corrió?" y dispararlo si no.

---

### CR-2 · Sin alerta si backup falla

**Archivo:** `backend/backup_diario.py`  
**Severidad:** MEDIA

Si el backup de las 11 PM falla (disco lleno, error de compresión), no hay notificación. Sandra o Manu no saben que los datos no están respaldados.

**Fix:** Enviar Telegram a Manu si el backup falla, con el mensaje de error específico.

---

### CR-3 · Backup incluye audios temporales (innecesario)

**Archivo:** `backend/backup_diario.py`  
**Severidad:** BAJA

Si el backup comprime todo `storage/`, incluye `workflow_audios/` que puede tener varios `.m4a` pesados. Los audios son temporales y no necesitan respaldo.

**Fix:** Excluir `storage/workflow_audios/` y `storage/audios_temp/` del backup.

---

## 14. Integridad de Datos

---

### DI-1 · `portal_knowledge.json` crece sin límite

**Archivo:** `storage/portal_knowledge.json`  
**Archivo código:** `backend/portal_verificador.py`  
**Severidad:** BAJA

El historial de verificaciones de portales se acumula indefinidamente. En un año de uso diario, este archivo podría pesar varios MB y ralentizar la carga.

**Fix:** Al escribir, mantener solo las últimas 1000 entradas del historial.

---

### DI-2 · Datos de portal desactualizados usados sin advertencia

**Archivos:** `backend/extractor_*.py`, `backend/workflow_steps/resolver_paciente.py`  
**Severidad:** MEDIA

Si el último dato extraído de un paciente tiene más de 30 días, se usa de todas formas sin ningún aviso. En contexto médico, un diagnóstico viejo puede ser un problema.

**Fix:** Al cargar datos de portal, verificar `_meta.fecha_extraccion`. Si es mayor a 30 días, incluir `"_advertencia": "Datos extraídos hace X días — verificar vigencia"` en el JSON del paciente.

---

## 15. Orden de Implementación

### Fase 1 — Estabilizar (hacer que lo básico funcione bien)

| Prioridad | Item | Impacto |
|-----------|------|---------|
| 1 | **C-2** Crear tabla `chat_history` en task_db.py | Desbloquea el borrado y el historial de chat |
| 2 | **B-2** Frontend verifica `response.ok` en eliminarPaciente | Usuario ve errores reales |
| 3 | **C-3** Context managers en SQLite | Evita database lock |
| 4 | **B-3** Cancelar tasks activos antes de borrar | Evita que el workflow recree el fantasma |
| 5 | **F-1** Renombrar hermes.ts → api.ts + limpiar HERMES_API en workflow.ts y auth.ts | Elimina Hermes del código de producción de Sandra |
| 6 | **C-1** Mover WORKFLOW_AUDIOS_DIR al bloque de directorios | Previene NameError potencial |
| 7 | **B-4** Agregar WORKFLOW_AUDIOS_DIR a eliminar_formatos | Borrado completo |

### Fase 2 — Robustez del pipeline de audio

| Prioridad | Item | Impacto |
|-----------|------|---------|
| 8 | **A-1** ffprobe falla → asumir audio largo | Evita timeout en audios largos |
| 9 | **A-3** Límite de tamaño en upload | Evita crashes por archivos grandes |
| 10 | **A-4** Validar tipo de archivo de audio | Errores claros en lugar de crashes |
| 11 | **A-5** QA bloquea documentos con [VERIFICAR] | Sandra no recibe documentos incompletos |
| 12 | **A-6** Workflow no continúa sin datos de paciente | Evita documentos vacíos |

### Fase 3 — Seguridad

| Prioridad | Item | Impacto |
|-----------|------|---------|
| 13 | **S-1** Cookie con `secure=True` y `samesite="lax"` | Seguridad básica de sesión |
| 14 | **S-2** AUTH_PIN obligatorio, sin fallback a 1234 | No hay PIN por defecto si falta .env |
| 15 | **S-4** Download verificar que archivo pertenece al CC | Previene acceso cruzado entre pacientes |
| 16 | **V-1** Validar formato de CC en todos los endpoints | Previene inputs maliciosos |

### Fase 4 — Confiabilidad

| Prioridad | Item | Impacto |
|-----------|------|---------|
| 17 | **N-1** Telegram falla → estado listo_sin_notificacion | Sandra sabe que debe revisar el dashboard |
| 18 | **C-4** Firma faltante → error explícito | No se entregan documentos sin firma |
| 19 | **E-1** Re-autenticación automática en portales | Extracciones no fallan silenciosamente |
| 20 | **CR-1** APScheduler con job store persistente | Crons no se pierden al reiniciar |
| 21 | **C-5** File lock en escritura de JSON de paciente | Evita corrupción de datos |

### Fase 5 — UX y pulido

| Prioridad | Item | Impacto |
|-----------|------|---------|
| 22 | **I-3** Ping/keepalive en streaming SSE | Chat no se corta en respuestas largas |
| 23 | **F-2** Hook useAuth() en todas las páginas | Redirect a login automático |
| 24 | **F-3** Try/catch en todos los fetch del frontend | Mensajes amigables cuando backend está caído |
| 25 | **I-1** Mensaje honesto cuando LLM trunca respuesta | Sandra entiende qué pasó |
| 26 | **A-7** Chunks de Deepgram en paralelo | Transcripción 3x más rápida |

---

## Limpieza manual inmediata (antes de la próxima prueba)

Borrar el fantasma actual a mano mientras se implementan los fixes:

```bash
rm storage/data/36280228-completo.json
rm storage/docs/*36280228*.docx
rm storage/pdfs/*36280228*.pdf
rm storage/workflow_audios/36280228_*.m4a
```

---

*Plan generado el 2026-05-23. Total: 26 items en 5 fases.*
