# RILO SAS — Plan de Mejoras v2 (Ronda 7)

> Segunda auditoría completa. 4 agentes en paralelo.
> Módulos cubiertos: workflow steps, módulos de soporte, server.py completo, dashboard completo.
> Todos los items son NUEVOS — no duplican PLAN_MEJORAS.md.
> Agente de implementación: **OpenCode**.

---

## Índice

- [🔴 Seguridad — autenticación y autorización (9 items)](#-seguridad--autenticación-y-autorización)
- [🔴 Integridad de datos — fallos silenciosos críticos (10 items)](#-integridad-de-datos--fallos-silenciosos-críticos)
- [🟠 Altos — funcionalidad incorrecta (16 items)](#-altos--funcionalidad-incorrecta)
- [🟡 Medios — robustez y calidad (14 items)](#-medios--robustez-y-calidad)
- [🟢 Bajos — UX, limpieza y menores (9 items)](#-bajos--ux-limpieza-y-menores)
- [📋 Orden de implementación](#-orden-de-implementación)

---

## 🔴 Seguridad — autenticación y autorización

Estos bugs permiten a cualquier persona sin credenciales acceder a datos médicos de pacientes reales o comprometer la autenticación del sistema.

---

### S-1 · ~40 endpoints de datos de pacientes sin autenticación — el agujero más grande del sistema

**Archivo:** `backend/server.py`

Los siguientes endpoints devuelven datos clínicos, documentos o historial de pacientes sin verificar ninguna cookie de sesión:

| Endpoint | Línea aprox. | Qué expone |
|----------|-------------|-----------|
| `GET /api/pacientes/{cc}` | 543 | JSON completo del paciente |
| `GET /api/pacientes/{cc}/formatos` | 549 | Lista de DOCX/PDFs |
| `GET /api/archivos/paciente/{cc}` | 415 | Archivos del workspace de Sandra |
| `GET /api/chat/historial/{cc}` | 450 | Historial de chat médico |
| `GET /api/pacientes/buscar` | 812 | Búsqueda libre de pacientes |
| `GET /api/tasks/paciente/{cc}` | 1099 | Tareas activas del paciente |
| `DELETE /api/chat/historial/{cc}` | 482 | Borrado sin auth |
| `DELETE /api/pacientes/{cc}/formatos` | 554 | Borrado sin auth |
| `DELETE /api/pacientes/{cc}` | 580 | Borrado de paciente sin auth |

Cualquiera que conozca un número de cédula colombiana (dato público) puede descargar todos los documentos clínicos de ese paciente.

**Fix:** Agregar dependencia `Depends(verificar_sesion)` a cada uno de estos endpoints. `verificar_sesion` ya existe en `auth_simple.py` — solo falta llamarlo.

---

### S-2 · Chat SSE (`POST /api/chat/stream`) sin autenticación — expone contexto del paciente

**Archivo:** `backend/server.py` líneas 271–359

El endpoint de streaming del chat no valida la cookie de sesión. Un atacante puede:
1. Hacer POST a `/api/chat/stream` con `{"paciente_cc": "XXXXXXXX"}` desde cualquier máquina
2. Recibir el stream de contexto clínico del paciente (siniestro, diagnóstico, historial)
3. El endpoint lee el workspace de Sandra buscando archivos del CC (línea 296) — directorio enumeration incluido

**Fix:** Agregar `verificar_sesion` como dependencia del endpoint.

---

### S-3 · `/api/archivos/sync` sin autenticación — ejecuta `git pull/push` desde internet

**Archivo:** `backend/server.py` líneas 766–809

El endpoint de sincronización con GitHub ejecuta comandos git sin verificar sesión. Expone:
- Todos los archivos del workspace de Sandra (directory listing)
- Posibilidad de disparar git operations desde internet

**Fix:** Agregar `verificar_sesion`. Además, capturar el returncode de `git push` y retornar `ok: False` si es distinto de 0 — el frontend actualmente muestra "Sincronizado" aunque falle.

---

### S-4 · Timing attack en validación de PIN

**Archivo:** `backend/auth_simple.py` línea 23–24

```python
def validar_pin(pin: str) -> bool:
    return pin == AUTH_PIN  # comparación con == es vulnerable a timing
```

Python interrumpe la comparación `==` en el primer carácter que difiere. Un atacante en la red local puede medir microsegundos de latencia para deducir el PIN carácter a carácter. Con un PIN de 4 dígitos, son ~40 intentos en lugar de 10,000.

**Fix:**
```python
from secrets import compare_digest
def validar_pin(pin: str) -> bool:
    return compare_digest(pin, AUTH_PIN)
```

---

### S-5 · `aplicador_correccion.py` puede modificar el paciente equivocado

**Archivo:** `backend/aplicador_correccion.py` líneas 63–96

La función carga el JSON del paciente buscando por glob `*{paciente_cc}*`. Si dos pacientes tienen CCs similares (ej. `1193143688` y `11931436880`), el glob puede cargar datos del **paciente incorrecto**. El código nunca verifica que el CC del JSON cargado coincide con el CC solicitado.

Consecuencia: Sandra le dicta a Tomy "cambia el teléfono del paciente X" y se actualiza el paciente Y.

**Fix:** Después de cargar el JSON, verificar:
```python
cc_en_json = json_data.get("paciente", {}).get("documento", "")
if cc_en_json != paciente_cc:
    return {"ok": False, "error": f"CC en JSON ({cc_en_json}) != CC solicitado ({paciente_cc})"}
```

---

### S-6 · Path traversal en `GET /api/download/{filename}`

**Archivo:** `backend/server.py` líneas 233–243

```python
safe_name = Path(filename).name   # solo el basename
path = DOCS_DIR / safe_name
```

`Path(filename).name` extrae solo el nombre de archivo, lo que parece seguro. Pero si `DOCS_DIR` tiene symlinks, `path.resolve()` puede apuntar fuera del directorio autorizado. El código no verifica que `path.resolve().parent == DOCS_DIR.resolve()`.

**Fix:**
```python
resolved = (DOCS_DIR / safe_name).resolve()
if not str(resolved).startswith(str(DOCS_DIR.resolve())):
    raise HTTPException(403, "Acceso denegado")
```

---

### S-7 · Validación de tipo MIME por extensión — se puede subir cualquier archivo

**Archivo:** `backend/server.py` líneas 67–73

`_validar_audio()` solo verifica que la extensión sea `.mp3`, `.m4a`, `.wav`, etc. No verifica el contenido real del archivo. Un atacante puede renombrar cualquier archivo a `.mp3` y subirlo al servidor donde queda en `storage/workflow_audios/`.

**Fix:** Usar `python-magic` para verificar el tipo MIME real antes de guardar:
```python
import magic
mime = magic.from_buffer(await file.read(2048), mime=True)
if not mime.startswith("audio/"):
    raise HTTPException(400, f"Archivo no es audio: {mime}")
```

---

### S-8 · CORS con `allow_credentials=True` pero solo 5 endpoints validan sesión

**Archivo:** `backend/server.py` líneas 43–50

La configuración CORS tiene `allow_credentials=True` lo que permite cookies cross-origin. Pero ~40 endpoints no validan la cookie. Un atacante puede hacer peticiones CSRF desde cualquier origen y el servidor las procesa.

Además, el string `"http://192.168.*"` en `CORS_ORIGINS` no funciona como wildcard en FastAPI — se toma literalmente como un dominio que nunca coincide. El CORS está mal configurado.

**Fix:** (1) Agregar autenticación a todos los endpoints (S-1 arriba). (2) Usar lista explícita de orígenes: `http://localhost:3000,http://192.168.1.50:3000`.

---

### S-9 · Hash de custodia truncado a 16 hex chars — puede colisionar/falsificarse

**Archivo:** `backend/custody.py` líneas 246–248

```python
"hash_documento": hashlib.sha256(...).hexdigest()[:16]
```

SHA-256 truncado a 16 caracteres = 64 bits de seguridad. Un atacante con acceso a la DB puede encontrar una colisión en ~2³² intentos (minutos en hardware moderno). La "cadena de custodia" puede ser falsificada.

**Fix:** Usar el hash completo de 64 chars: `.hexdigest()` sin slice. O usar HMAC con la `AUTH_SECRET`.

---

## 🔴 Integridad de datos — fallos silenciosos críticos

Estos bugs producen documentos médico-legales inválidos, datos incorrectos o pérdida de información sin ningún error visible.

---

### I-1 · `transcribir.py` nunca retorna campo `ok` — todos sus fallos son silenciosos

**Archivo:** `backend/workflow_steps/transcribir.py` líneas 75–166

`workflow_runner.py` verifica el resultado de cada paso con `resultado_step.get("ok")`. Si el paso no retorna el campo `ok`, la condición falla silenciosamente y el workflow continúa.

`transcribir.py` retorna diccionarios como:
```python
{"texto": "...", "confianza_global": 0.85, "warnings": [...]}  # ← sin "ok"
```

Si la transcripción falla por completo, `workflow_runner` lo trata como éxito y pasa la transcripción vacía a la síntesis.

**Fix:** Agregar `"ok": True` / `"ok": False` a todos los retornos de `transcribir.py`, y agregar el paso a la validación en `workflow_runner.py` línea 89.

---

### I-2 · `convertir_pdf.py` retorna `ok: True` aunque TODOS los PDFs fallen

**Archivo:** `backend/workflow_steps/convertir_pdf.py` línea 51

```python
return {"ok": True, "pdfs": pdfs_generados, "errores": errores}
```

Si `pdfs_generados` es lista vacía (todos fallaron), igual retorna `ok: True`. El workflow termina diciendo "listo" pero no hay ningún PDF. Sandra descarga los archivos y no pasan nada.

**Fix:**
```python
formatos_esperados = len(docx_paths)
ok = len(pdfs_generados) >= formatos_esperados
return {"ok": ok, "pdfs": pdfs_generados, "errores": errores}
```

---

### I-3 · Ausencia de LibreOffice no bloquea el workflow

**Archivo:** `backend/workflow_steps/convertir_pdf.py` línea 34  
**Archivo:** `backend/workflow_runner.py` línea 89

Si LibreOffice no está instalado, `convertir_pdf` retorna `{"ok": False, ...}`. Pero `workflow_runner` solo valida `ok` para los pasos `sintetizar` y `generar` — no para `convertir_pdf`. El workflow termina en estado "listo" sin PDFs.

**Fix:** Agregar `convertir_pdf` a la lista de pasos que detienen el workflow si `ok=False`.

---

### I-4 · Discrepancia de siniestros detectada pero no bloquea la generación

**Archivo:** `backend/fusionador.py` líneas 145–158

Cuando Medifolios y Positiva tienen IDs de siniestro diferentes, el código genera una alerta y elige Positiva automáticamente:
```python
reconciliacion["alerta"] = f"⚠️ DISCREPANCIA: Medifolios={siniestro_med}, Positiva={siniestro_pos}. Se usará Positiva."
# ... y continúa generando documentos
```

Un documento médico-legal con el número de siniestro equivocado puede ser nulo legalmente ante la ARL.

**Fix:** Marcar el resultado con `_requiere_confirmacion: True` y detener el workflow hasta que Sandra confirme qué siniestro usar.

---

### I-5 · PDF/A no es realmente PDF/A — documentos legalmente inválidos

**Archivo:** `backend/pdf_archivo.py` líneas 22–130

La función `convertir_a_pdfa()` afirma generar PDF/A-2b para archivo legal, pero:
- LibreOffice con `--convert-to pdf` genera PDF normal, **no PDF/A**
- El fallback `_convertir_via_python()` usa FPDF, que genera PDF básico, **no PDF/A**
- El último recurso (línea ~130) copia el DOCX y lo renombra `.pdf` — completamente inválido

En Colombia, para documentación médico-laboral de ARL, los archivos de más de 5 años requieren PDF/A-1b o PDF/A-2b. Estos documentos no cumplen el estándar.

**Fix:** Usar el flag correcto de LibreOffice: `--convert-to "pdf/A"` (con /A). Verificar conformidad con `pdftk` o `veraPDF` después de la conversión.

---

### I-6 · `[VERIFICAR]` aparece literalmente en los documentos generados

**Archivo:** `backend/json_validator.py` líneas 494–496

Cuando un campo recomendado está vacío, el validador inserta la cadena `"[VERIFICAR]"` en el JSON:
```python
_set_nested(datos, path, "[VERIFICAR]")
```

Este JSON con `"[VERIFICAR]"` llega a `doc_generator.py` y se inserta en las celdas de las tablas. El paciente o la empresa recibe un documento con `"DIAGNÓSTICO: [VERIFICAR]"` o `"EDAD: [VERIFICAR]"`.

**Fix:** El validador debe reportar el campo faltante como warning pero **no insertarlo en el JSON**. El generador debe manejar valores vacíos visualmente (celda sombreada) sin escribir el placeholder literal.

---

### I-7 · `_build_kwargs` retorna `{}` para paso desconocido — TypeError silencioso

**Archivo:** `backend/workflow_runner.py` línea 186

Si un paso tiene un nombre que no coincide con ningún `if` en `_build_kwargs()`, retorna `{}`. El paso se ejecuta con cero argumentos, lanza `TypeError: ejecutar() missing required positional argument`, que el workflow runner puede capturar como error genérico sin indicar la causa real.

**Fix:**
```python
raise ValueError(f"Paso desconocido en _build_kwargs: '{step_name}'")
```

---

### I-8 · `datos_clinicos` cae a `{}` silenciosamente en `workflow_runner`

**Archivo:** `backend/workflow_runner.py` línea 163

```python
datos_clinicos = verif.get("datos_enriquecidos") or sintesis.get("datos_clinicos") or {}
```

Si `verificar_portales` no tiene `datos_enriquecidos` Y `sintetizar_maestro` falló (ok=False), `datos_clinicos` es `{}`. Se llama a `generar_formatos` con un dict vacío y se producen 7 documentos en blanco.

**Fix:** Verificar explícitamente que `datos_clinicos` no es vacío antes de llamar `generar_formatos`:
```python
if not datos_clinicos:
    db.marcar_error(task_id, paso=6, error="datos_clinicos vacío — síntesis falló")
    return
```

---

### I-9 · `verificar_portales`: campos marcados como "faltante" cuando el portal falló (no el campo)

**Archivo:** `backend/workflow_steps/verificar_portales.py` líneas 137–208

Si `portales._meta.parcial = True` (extracción incompleta porque el portal estaba caído), la verificación marca todos los campos no extraídos como `"faltante"`. Sandra ve una alerta de que faltan datos clínicos cuando en realidad fue el portal el que falló.

**Fix:** Distinguir `"faltante_en_portal"` (dato existe pero no se pudo extraer) de `"faltante_en_datos"` (el dato realmente no existe para este paciente). Incluir la distinción en la notificación a Sandra.

---

### I-10 · CC vacío → archivos guardados como `sin_cc_...` — múltiples pacientes se sobreescriben

**Archivo:** `backend/workflow_steps/generar_formatos.py` líneas 129, 154

```python
cc = datos_clinicos.get("paciente", {}).get("documento", "sin_cc")
```

Si el CC no está en `datos_clinicos`, todos los formatos se guardan con nombres como `analisis_sin_cc_abc123.docx`. Si hay dos workflows con CC vacío corriendo simultáneamente, los archivos se sobreescriben mutuamente.

**Fix:**
```python
cc = datos_clinicos.get("paciente", {}).get("documento", "")
if not cc:
    return {"ok": False, "error": "CC vacío en datos_clinicos — no se generan formatos sin identificador"}
```

---

## 🟠 Altos — funcionalidad incorrecta

---

### A-1 · Dashboard: `fetch` sin `credentials: "include"` en 3 páginas clave

**Archivos:**
- `dashboard/app/pacientes/page.tsx` líneas 22–23
- `dashboard/app/hoy/page.tsx` líneas 32–33
- `dashboard/app/paciente/[cc]/page.tsx` líneas 43–46

Los `fetch` en estas páginas no incluyen `credentials: "include"`. Si la sesión expira o el usuario no está autenticado, el servidor responde 401 pero el código intenta parsear el JSON de error y muestra "Error de conexión" en lugar de redirigir al login.

**Fix:** Usar el wrapper `authFetch()` de `lib/auth.ts` (ya existe) en lugar de `fetch` directo. O agregar `credentials: "include"` + manejo de 401 en todos los fetch.

---

### A-2 · Dashboard: URL del backend hardcodeada en `app/api/` y `next.config.js`

**Archivos:**
- `dashboard/app/api/chat/route.ts` línea 13
- `dashboard/app/api/upload-audio/route.ts` línea 25
- `dashboard/next.config.js` líneas 10–16

URLs hardcodeadas a `http://localhost:8000`. En producción (WSL de Sandra), si el backend no está exactamente en localhost, el dashboard no funciona.

**Fix:** Usar variable de entorno `BACKEND_URL`:
```javascript
// next.config.js
const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
rewrites: () => [{ source: '/api/:path*', destination: `${backendUrl}/api/:path*` }]
```

---

### A-3 · QA: lógica `all()` incorrecta — documentos con warnings pasan QA

**Archivo:** `backend/workflow_steps/qa_formatos.py` línea 65

```python
qa_ok = len(warnings) == 0 or all("Placeholders" not in w for w in warnings)
```

Esta expresión es truthy si hay warnings pero NINGUNO menciona "Placeholders". Ejemplo: si el documento tiene warning "Sin tablas detectadas", `qa_ok = True` aunque el documento esté incompleto.

La intención era: OK si no hay warnings de placeholders críticos. El resultado real es: OK si no hay warnings O si los warnings no son de placeholders.

**Fix:**
```python
# Solo pasa si no hay ningún warning
qa_ok = len(warnings) == 0
```
O, si se quiere ser selectivo, definir explícitamente qué warnings son bloqueantes.

---

### A-4 · `sintetizar_maestro`: `datos_clinicos` con un campo = ok aunque esté casi vacío

**Archivo:** `backend/workflow_steps/sintetizar_maestro.py` línea 187

El código retorna `ok: False` solo si `datos_clinicos` es `None` o `{}` (dict vacío). Si el LLM devuelve `{"paciente": {}}` (dict con una clave pero todos los valores vacíos), pasa la validación y se generan documentos con solo el esqueleto del JSON.

**Fix:** Validar que los campos críticos existen y no están vacíos:
```python
campos_minimos = ["paciente.documento", "siniestro.id_siniestro"]
for campo in campos_minimos:
    partes = campo.split(".")
    val = datos_clinicos
    for parte in partes:
        val = (val or {}).get(parte)
    if not val:
        return {"ok": False, "error": f"Campo crítico faltante: {campo}"}
```

---

### A-5 · `format_selector`: estado PRUEBA_TRABAJO pierde el SEGUIMIENTO cuando hay ambos

**Archivo:** `backend/format_selector.py` líneas 223–226

Si el paciente está en SEGUIMIENTO + PRUEBA_TRABAJO simultáneamente (paciente en rehabilitación que hace prueba funcional de reincorporación), el código detecta PRUEBA_TRABAJO, vuelve a llamar `detectar_estado()`, y si retorna PRUEBA_TRABAJO de nuevo usa `EstadoCaso.NUEVO` como fallback. Se pierde el estado SEGUIMIENTO.

**Fix:** No re-detectar. Analizar directamente si hay datos de seguimiento o cierre en los datos del paciente y elegir el estado combinado correcto.

---

### A-6 · `correction_loop`: regex captura texto de contexto como valor del campo

**Archivo:** `backend/correction_loop.py` línea 219–220

El patrón regex captura todo el texto hasta un punto o coma. Si Sandra dice "Cambia la fecha a 15/05/2026 en el formulario de análisis", captura `"15/05/2026 en el formulario de análisis"` como valor — incluyendo el contexto.

El documento queda con: `"FECHA_EVENTO: 15/05/2026 en el formulario de análisis"`.

**Fix:** Agregar palabras clave clínicas como terminadores del grupo capturado. O usar el LLM para extraer el valor en lugar de regex, ya que el contexto conversacional es ambiguo.

---

### A-7 · `correction_loop`: código dead — else nunca alcanza por condición tautológica

**Archivo:** `backend/correction_loop.py` líneas 424–428

```python
elif tipo == TipoCorreccion.CAMPO_FALTANTE and campo_detectado and not valor_nuevo:
    if campo_detectado is not None:   # ← siempre True aquí (el elif ya verificó `campo_detectado`)
        pregunta = f"...'{campo_detectado}'?"
    else:
        pregunta = "..."   # ← inalcanzable
```

El `else` nunca ejecuta. Si `campo_detectado` es `None`, el `elif` no entra. El mensaje de aclaración genérico está muerto.

**Fix:** Mover la verificación al nivel del `elif`:
```python
elif tipo == TipoCorreccion.CAMPO_FALTANTE and not valor_nuevo:
    if campo_detectado:
        pregunta = f"Sandra, ¿cuál es el valor correcto para '{campo_detectado}'?"
    else:
        pregunta = "Sandra, ¿podés decirme qué campo querés corregir?"
```

---

### A-8 · `json_validator`: `False` validado como campo presente — booleanos siempre pasan

**Archivo:** `backend/json_validator.py` líneas 438–439

`_is_empty()` considera `0` como vacío pero no considera `False` como vacío. Un campo booleano como `siniestro.incapacitado = False` (el paciente NO está incapacitado) se valida como "campo lleno" y no se marca para verificación.

Si el dato correcto era `True` pero quedó `False` por error de extracción, nadie lo detecta.

**Fix:** Tratar `False` como valor que requiere verificación en campos donde `False` tiene significado clínico real. O mejor: diferenciar `None` (no hay dato) de `False` (dato existe y es negativo) en el schema.

---

### A-9 · `leer_notas_crudas`: retorna `([], True)` cuando workspace no existe — engaña al workflow

**Archivo:** `backend/workflow_steps/leer_notas_crudas.py` líneas 62–65

Si el directorio workspace no existe o no es accesible, la función retorna `([], True)` — cero notas pero "escaneo completo". El workflow continúa sin notas pensando que el escaneo fue exhaustivo.

**Fix:** Retornar `([], False)` con un mensaje de advertencia si el workspace no existe o no es accesible.

---

### A-10 · `leer_notas_crudas`: race condition en el sort — `stat()` puede fallar si el archivo se borró

**Archivo:** `backend/workflow_steps/leer_notas_crudas.py` línea 97

```python
candidatos.sort(key=lambda d: Path(d["ruta"]).stat().st_mtime, ...)
```

Si Sandra borra o mueve un archivo entre el momento del escaneo (glob) y el sort, `stat()` lanza `FileNotFoundError` y el workflow crashea.

**Fix:**
```python
def _mtime_safe(ruta):
    try:
        return Path(ruta).stat().st_mtime
    except OSError:
        return 0

candidatos.sort(key=lambda d: _mtime_safe(d["ruta"]), reverse=True)
```

---

### A-11 · `workflow_runner`: crash en `notificar_listo` — `portales` puede ser `None`

**Archivo:** `backend/workflow_runner.py` línea 175

```python
nombre = portales.get("medifolios", {}).get("nombre1", "") + " " + portales.get("medifolios", {}).get("apellido1", "")
```

Si `portales` es `None` (porque `resolver_paciente` no lo retornó), `.get()` sobre `None` lanza `AttributeError`. El último paso del workflow (notificación a Sandra) crashea sin que ella reciba el mensaje.

**Fix:**
```python
portales = contexto.get("resolver_paciente", {}).get("datos_portales") or {}
medi = portales.get("medifolios") or {}
nombre = f"{medi.get('nombre1', '')} {medi.get('apellido1', '')}".strip() or cc
```

---

### A-12 · `custodia.py`: validación extra falla pero el campo se marca como válido

**Archivo:** `backend/custody.py` líneas 156–159

```python
elif match and not extra_ok:
    confianza = 50
    mensaje = f"⚠️ Validación extra falló"
    es_valido = True   # ← FALSE POSITIVO
```

Si la validación extra falla (por ejemplo, el formato del número de siniestro es incorrecto), el campo se marca como `es_valido = True` con confianza 50. Un campo con validación fallida debería ser `es_valido = False`.

**Fix:** Cambiar a `es_valido = False` cuando `extra_ok` es `False`.

---

### A-13 · `flujo_audio.py`: extracción de datos cualitativos con regex falla si Sandra no usa frases exactas

**Archivo:** `backend/flujo_audio.py` líneas 130–197

Los patrones regex para extraer metodología, proceso productivo y apreciación del trabajador requieren frases específicas como "la servidora" o "el trabajador" para delimitar el final del campo. Si Sandra habla de forma diferente (ej. "el paciente hizo..." en lugar de "el trabajador hizo..."), el regex no delimita el campo y todo el texto restante se captura como un único bloque.

**Fix:** Usar el LLM para extracción de datos cualitativos (ya está disponible en el sistema). O ampliar los delimitadores del regex para incluir más variantes del lenguaje clínico colombiano.

---

### A-14 · `json.loads` sin manejo de error en `correction_resolver.py`

**Archivo:** `backend/correction_resolver.py` línea 81

```python
resultado = json.loads(proc.stdout)
```

Si `proc.stdout` no es JSON válido (LLM devolvió error, proceso se interrumpió, encoding roto), lanza `JSONDecodeError` no capturado. El sistema de corrección de documentos crashea y Sandra ve el bot de chat sin respuesta.

**Fix:**
```python
try:
    resultado = json.loads(proc.stdout)
except json.JSONDecodeError as e:
    _log(f"❌ JSON inválido de LLM: {e}")
    return {"campo": None, "confianza": 0, "error": str(e)}
```

---

### A-15 · Stack traces internos expuestos al cliente en errores 500

**Archivo:** `backend/server.py` línea 660–674

```python
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
```

`str(e)` puede incluir paths del servidor, nombres de funciones, nombres de variables — información que ayuda a un atacante a mapear la arquitectura interna.

**Fix:** Loguear `traceback.format_exc()` internamente y retornar un mensaje genérico al cliente:
```python
except Exception as e:
    logger.error(traceback.format_exc())
    raise HTTPException(500, "Error interno del servidor")
```

---

### A-16 · `DELETE` endpoints no verifican existencia antes de borrar

**Archivo:** `backend/server.py` líneas 482, 554, 580

Los endpoints de borrado (historial, formatos, paciente) ejecutan las operaciones sin verificar primero que el recurso existe. Retornan 200 OK aunque no haya nada que borrar. No hay auditoría de qué se borró ni cuándo.

**Fix:** Verificar existencia antes de borrar y retornar 404 si no existe. Agregar registro en logs con timestamp de quién borró qué.

---

## 🟡 Medios — robustez y calidad

---

### M-1 · Timestamps sin zona horaria (datetime.now() local en lugar de UTC)

**Archivos:** `backend/task_db.py` línea 102, `backend/server.py` línea 156, múltiples workflow steps

```python
datetime.now().isoformat()   # ← zona local sin TZ
```

Si el servidor cambia de zona horaria (DST, migración), los timestamps históricos y futuros son incomparables. Las métricas de duración de pasos del workflow serán incorrectas.

**Fix:** `datetime.now(timezone.utc).isoformat()` en todos los sitios.

---

### M-2 · `TaskDB` sin transacciones atómicas — estado puede quedar inconsistente

**Archivo:** `backend/task_db.py` líneas 54–134

Cada `actualizar_paso()`, `marcar_error()`, etc. abre y cierra conexión individualmente sin `BEGIN TRANSACTION`. Si hay una escritura concurrente o un crash entre operaciones relacionadas, la task puede quedar en estado inconsistente (ej. `paso=3` pero `estado="transcribiendo"`).

**Fix:** Usar context manager `with conn:` (que SQLite trata como BEGIN/COMMIT) en todas las funciones que hacen múltiples escrituras.

---

### M-3 · Temp files se acumulan en disco — `except: pass` silencia failures de limpieza

**Archivos:**
- `backend/workflow_steps/sintetizar_maestro.py` línea 164
- `backend/correction_resolver.py` línea 75–76
- `backend/workflow_steps/transcribir.py` línea 141–142

```python
finally:
    try: os.unlink(ctx_file)
    except: pass    # ← fallo silencioso
```

Si el `unlink` falla (permisos, archivo en uso), el archivo temporal queda permanentemente. Después de semanas de uso, `/tmp` se llena y el servidor falla al crear nuevos archivos.

**Fix:** `except Exception as e: _log(f"⚠️ No se pudo eliminar {ctx_file}: {e}")`. Agregar un cron job que limpie archivos temp más viejos de 1 hora.

---

### M-4 · `lote_worker.py`: retries sin exponential backoff — inunda la API bajo carga

**Archivo:** `backend/lote_worker.py` líneas 87–114

Los 3 reintentos tienen esperas fijas de 10s, 20s, 30s. Si la API de DeepSeek está saturada, estos tiempos son demasiado cortos y no dan tiempo al servidor para recuperarse.

**Fix:** Exponential backoff: `2^intento * 10 segundos` + jitter aleatorio.

---

### M-5 · `leer_formatos_subidos.py`: `ImportError` de python-docx retorna lista vacía silenciosamente

**Archivo:** `backend/workflow_steps/leer_formatos_subidos.py` líneas 42–43

Si `python-docx` no está instalado, la función retorna `[]` sin ningún aviso. El workflow continúa sin los formatos de referencia de Sandra, generando documentos que no consideran el trabajo previo.

**Fix:** Retornar advertencia explícita: `_log("⚠️ python-docx no disponible — no se leen formatos subidos")`.

---

### M-6 · `confianza_global` de transcripción es engañosa cuando hay chunks fallidos

**Archivo:** `backend/workflow_steps/transcribir.py` línea 144

Si 3 de 5 chunks transcriben con confianza 0.8 y 2 fallan, la confianza reportada es `0.8` (promedio de los 3 exitosos) en lugar de `0.8 * 3/5 = 0.48` (del total). Sandra ve "confianza alta" cuando el 40% del audio no se transcribió.

**Fix:** Incluir los chunks fallidos en el cálculo con confianza 0.0.

---

### M-7 · API keys no se validan al arrancar el servidor

**Archivo:** `backend/server.py` startup, `backend/flujo_audio.py` líneas 33–34

Si `DEEPGRAM_API_KEY`, `OPENCODE_GO_API_KEY` o `TELEGRAM_BOT_TOKEN` están vacíos, el sistema arranca sin error. Los fallos aparecen horas después durante el procesamiento de audio o al intentar notificar a Sandra.

**Fix:** En el evento de startup de FastAPI, verificar que todas las API keys requeridas existen y no están vacías. Si falta alguna, loguear un error claro al arrancar.

---

### M-8 · `subprocess` con `check=True` inconsistente entre pasos del workflow

**Archivos:** `backend/workflow_steps/convertir_pdf.py` línea 28, `backend/workflow_steps/transcribir.py` línea 55, otros

Algunos pasos usan `check=True` (lanza `CalledProcessError` si subprocess falla), otros no. El manejo de errores de subprocess es diferente en cada paso y dificulta el debugging.

**Fix:** Política uniforme: usar `check=True` en todos los subprocess. Capturar `CalledProcessError` específicamente en el try/except del paso.

---

### M-9 · `lote_worker.py`: fallo en registro de costos silenciado con `except: pass`

**Archivo:** `backend/lote_worker.py` línea 128

Si `costos_tracker.registrar()` falla, se silencia sin log. El tracking de costos del LLM queda incompleto sin que nadie lo sepa.

**Fix:** `except Exception as e: print(f"⚠️ Error en costos_tracker: {e}", file=sys.stderr)`.

---

### M-10 · `paciente/[cc]/page.tsx`: datos del paciente anterior visibles al cambiar de CC

**Archivo:** `dashboard/app/paciente/[cc]/page.tsx` líneas 43–46

El `useEffect` carga datos del nuevo CC pero no resetea `paciente` y `formatos` a `null` antes de hacer el fetch. Durante el tiempo de carga, Sandra ve los datos del paciente anterior en pantalla.

**Fix:**
```typescript
useEffect(() => {
    setPaciente(null);
    setFormatos([]);
    cargarPaciente(cc);
}, [cc]);
```

---

### M-11 · `api/download/{cc}`: CC no se usa para verificar que el archivo pertenece al paciente

**Archivo:** `backend/server.py` línea 233–243

El endpoint de descarga acepta un nombre de archivo directamente. No verifica que el archivo descargado pertenezca al CC del paciente solicitado. Un usuario autenticado podría descargar archivos de otro paciente si conoce el nombre exacto del archivo.

**Fix:** Verificar que `safe_name` contiene el CC del paciente autorizado en el nombre.

---

### M-12 · `hoy/page.tsx` y `paciente/[cc]/page.tsx`: errores van a `console.error` y Sandra no los ve

**Archivos:**
- `dashboard/app/hoy/page.tsx` línea 38
- `dashboard/app/paciente/[cc]/page.tsx` línea 50
- `dashboard/app/archivos/page.tsx` línea 56

Los errores de fetch se loguean con `console.error()` (visible solo en DevTools) pero no se muestran en la UI. Sandra no sabe que la carga falló — la página simplemente queda vacía.

**Fix:** Agregar estado `error` en cada página y mostrarlo con un mensaje descriptivo en la UI.

---

### M-13 · `workflow_runner`: paso marcado como "iniciado" antes de ejecutarse — timestamp impreciso

**Archivo:** `backend/workflow_runner.py` líneas 70, 127

`db.actualizar_paso()` se llama ANTES de ejecutar el paso (línea 70). El timestamp en la DB refleja cuándo el paso fue "anunciado", no cuándo realmente terminó. Para el paso de síntesis (5 minutos), el timestamp puede estar 5 minutos adelantado.

**Fix:** Actualizar el timestamp de completion DESPUÉS de que el paso retorna resultado exitoso.

---

### M-14 · `next.config.js`: sin headers de seguridad HTTP

**Archivo:** `dashboard/next.config.js`

No hay configuración de headers de seguridad: `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`. El dashboard puede ser embebido en otros sitios (clickjacking) y los navegadores no tienen protecciones adicionales.

**Fix:**
```javascript
async headers() {
    return [{
        source: '/(.*)',
        headers: [
            { key: 'X-Frame-Options', value: 'DENY' },
            { key: 'X-Content-Type-Options', value: 'nosniff' },
            { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        ]
    }]
}
```

---

## 🟢 Bajos — UX, limpieza y menores

---

### B-1 · Dashboard: `archivo.split("/")` sin null check — crash si `archivo` es null

**Archivo:** `dashboard/app/chat/page.tsx` líneas 509, 514

```typescript
f.archivo.split("/")  // ← crash si f.archivo es null o undefined
```

Si el backend retorna un formato sin campo `archivo` (porque falló al generarse), el chat crashea con un error de JavaScript.

**Fix:** `f.archivo?.split("/").pop() ?? "Archivo"`

---

### B-2 · Dashboard: tipo `any` en TypeScript — ~15 instancias

**Archivos:** múltiples páginas del dashboard

`any` en líneas clave: `useState<any>`, `map((f: any)`, `(paciente: any)`. Elimina la seguridad de tipos y puede enmascarar bugs de runtime.

**Fix:** Definir interfaces `Paciente`, `FormatoInfo`, `TareaWorkflow` en `lib/types.ts` y usarlas en todas las páginas.

---

### B-3 · `BotonGigante`: el sublabel desaparece durante el procesamiento

**Archivo:** `dashboard/components/BotonGigante.tsx` línea 28

Cuando `loading === true`, el label cambia a "Procesando..." pero el sublabel descriptivo desaparece. Sandra no sabe qué está procesando el botón.

**Fix:** Mantener el sublabel visible durante el estado loading.

---

### B-4 · `PASOS_LABELS[11]` sería `undefined` — off-by-one potencial

**Archivo:** `dashboard/app/paciente/[cc]/page.tsx` líneas 9–20

El array `PASOS_LABELS` tiene índices 1–10. Si el backend retorna `paso_actual = 11` (por un bug de conteo), `PASOS_LABELS[11] = undefined` y la UI muestra `"undefined"`.

**Fix:** `PASOS_LABELS[paso] ?? "Paso desconocido"`.

---

### B-5 · Input CC en `/subir-audio` sin validación de formato

**Archivo:** `dashboard/app/subir-audio/page.tsx` líneas 75–77

El campo de CC acepta cualquier texto. Sandra podría ingresar "Juan Carlos" como CC y el backend procesa silenciosamente.

**Fix:** Agregar `pattern="[0-9]{6,12}"` y validación en `onChange` que solo acepte dígitos.

---

### B-6 · Sidebar: color inconsistente entre desktop y mobile

**Archivo:** `dashboard/components/Sidebar.tsx` línea 20  
**Archivo:** `dashboard/app/layout.tsx`

En desktop, el Sidebar tiene `bg-white border-r`. En el layout tiene `bg-slate-800 text-white`. Inconsistencia visual que se ve extraña en pantallas anchas.

**Fix:** Consolidar el color de fondo del sidebar en un solo lugar.

---

### B-7 · `chat/page.tsx` línea 389: "Error de conexion" sin tilde

**Archivo:** `dashboard/app/chat/page.tsx` línea 389

```typescript
"Error de conexion"   // ← debería ser "conexión"
```

**Fix:** `"Error de conexión"`.

---

### B-8 · `flujo_audio.py`: datos cualitativos extraídos con doble lectura del mismo archivo

**Archivo:** `backend/flujo_audio.py` líneas 88–93

El archivo se lee dos veces: línea 88 lee los primeros 500 chars para buscar el CC, y línea 92 lee el archivo completo si hay match. Si el archivo está siendo modificado entre las dos lecturas, se obtienen dos versiones distintas del contenido.

**Fix:** Leer el archivo completo una sola vez y tomar los primeros 500 chars del buffer en memoria.

---

### B-9 · `backup_diario.py`: éxito/fallo del backup no se registra en ningún archivo de estado

**Archivo:** `backend/backup_diario.py` líneas 20–61

El backup corre a las 23:00 pero no hay ningún archivo `ultimo_backup.json` ni similar que registre cuándo fue el último backup exitoso, cuánto tardó, cuánto pesó el archivo. No hay forma de verificar si el backup está funcionando sin ver los logs directamente.

**Fix:** Escribir `storage/backup_status.json` al final de cada backup con `{"ultimo_ok": "2026-05-24T23:00:00Z", "tamano_bytes": 1234567, "archivo": "..."}`. El dashboard puede mostrar este estado.

---

## 📋 Orden de Implementación

### Fase 0 — Seguridad primero (hacer antes de que el sistema esté accesible en red)

| # | Item | Acción |
|---|------|--------|
| 0.1 | **S-1** Agregar `Depends(verificar_sesion)` a todos los endpoints de datos | ~2h, cambio mecánico repetitivo |
| 0.2 | **S-2** Chat SSE sin auth | 1 línea |
| 0.3 | **S-3** `/api/archivos/sync` sin auth | 1 línea |
| 0.4 | **S-4** Timing attack en PIN → `compare_digest` | 2 líneas |
| 0.5 | **S-5** `aplicador_correccion`: verificar CC antes de aplicar | Evita modificar paciente equivocado |
| 0.6 | **S-6** Path traversal en download → verificar `resolve().parent` | Seguridad del filesystem |
| 0.7 | **S-7** Validación MIME real en upload | Previene archivos maliciosos |
| 0.8 | **S-9** Hash de custodia → 64 chars completos | Custodia legalmente válida |

### Fase 1 — Integridad de documentos (documentos correctos o error claro)

| # | Item | Acción |
|---|------|--------|
| 1.1 | **I-1** `transcribir.py` retorna `"ok"` field | Sin esto todos sus fallos son silenciosos |
| 1.2 | **I-2** `convertir_pdf.py` ok:False si pdfs_generados vacío | Sin PDFs = error, no éxito |
| 1.3 | **I-3** LibreOffice ausente bloquea el workflow | Agregar a validación en workflow_runner |
| 1.4 | **I-5** PDF/A real — usar `--convert-to "pdf/A"` | Documentos legalmente válidos |
| 1.5 | **I-6** `[VERIFICAR]` no se inserta en JSON, se reporta como advertencia | Documentos sin placeholders visibles |
| 1.6 | **I-4** Discrepancia de siniestros bloquea hasta confirmación | No documentar siniestro equivocado |
| 1.7 | **I-7** `_build_kwargs` levanta error para paso desconocido | TypeError descriptivo |
| 1.8 | **I-8** `datos_clinicos={}` detiene el workflow | No generar 7 documentos en blanco |
| 1.9 | **I-10** CC vacío → error, no "sin_cc" | No sobreescribir archivos de otros pacientes |

### Fase 2 — Lógica correcta en módulos de soporte

| # | Item | Acción |
|---|------|--------|
| 2.1 | **A-3** QA: `qa_ok = len(warnings) == 0` | Lógica correcta |
| 2.2 | **A-4** `sintetizar_maestro`: validar campos mínimos | No datos clínicos incompletos |
| 2.3 | **I-9** `verificar_portales`: "no_verificado" vs "faltante" | Sandra no ve falsas alarmas |
| 2.4 | **A-5** `format_selector`: PRUEBA_TRABAJO + SEGUIMIENTO combinados | Formatos correctos |
| 2.5 | **A-7** Código dead en `correction_loop` → fix condicional | Pregunta de aclaración funciona |
| 2.6 | **A-8** `json_validator`: `False` como vacío | Booleanos validados correctamente |
| 2.7 | **A-12** `custody.py`: `extra_ok=False` → `es_valido=False` | Custodia honesta |
| 2.8 | **S-8** CORS: dominios explícitos | Seguridad bien configurada |

### Fase 3 — Dashboard funcional en producción

| # | Item | Acción |
|---|------|--------|
| 3.1 | **A-2** `next.config.js` y `app/api/`: `BACKEND_URL` env var | App funciona fuera de localhost |
| 3.2 | **A-1** fetch con `credentials: "include"` en todas las páginas | Auth funciona correctamente |
| 3.3 | **A-15** Stack traces no expuestos en 500s | Seguridad |
| 3.4 | **A-11** Crash en `notificar_listo` por portales=None | Sandra siempre recibe notificación |
| 3.5 | **A-10** Sort race condition en `leer_notas_crudas` | No crash si Sandra borra archivo |
| 3.6 | **A-9** `leer_notas_crudas`: retornar `([], False)` si workspace ausente | Estado honesto |
| 3.7 | **M-10** Reset datos al cambiar de CC en dashboard | No stale data |
| 3.8 | **M-12** Errores en UI, no solo `console.error` | Sandra sabe cuándo algo falla |
| 3.9 | **B-1** null check en `archivo.split("/")` | No crash del chat |

### Fase 4 — Robustez y calidad

| # | Item | Acción |
|---|------|--------|
| 4.1 | **M-1** Timestamps UTC en todo el backend | Métricas de duración correctas |
| 4.2 | **M-2** Transacciones atómicas en TaskDB | Estado consistente |
| 4.3 | **M-3** Log en limpieza de temp files | No disk full silencioso |
| 4.4 | **M-7** Validar API keys al arrancar | Fallo temprano descriptivo |
| 4.5 | **A-13** Extracción cualitativa: LLM en lugar de regex rígido | Datos cualitativos no se pierden |
| 4.6 | **A-6** Regex de corrección: terminadores más precisos | Valores sin texto de contexto |
| 4.7 | **A-14** `json.loads` con manejo de error en correction_resolver | Bot no deja de responder |
| 4.8 | **M-6** Confianza de transcripción incluye chunks fallidos | Métrica honesta |
| 4.9 | **M-14** Headers de seguridad HTTP en next.config | Protección básica navegador |
| 4.10 | **M-4** Exponential backoff en lote_worker | Menos carga en API bajo stress |

### Fase 5 — Calidad menor y UX

| # | Item | |
|---|------|---|
| 5.1 | **B-2** Interfaces TypeScript (eliminar `any`) | |
| 5.2 | **B-4** `PASOS_LABELS[paso] ?? "Paso desconocido"` | |
| 5.3 | **B-5** Validación formato CC en inputs | |
| 5.4 | **A-16** DELETE endpoints verifican existencia + logs de auditoría | |
| 5.5 | **M-9** Log en fallo de costos_tracker | |
| 5.6 | **B-9** `backup_status.json` para monitoreo | |
| 5.7 | **B-3** BotonGigante mantiene sublabel en loading | |
| 5.8 | **M-5** Warning explícito si python-docx no disponible | |
| 5.9 | **B-7** Tilde en "conexión" | |

---

*Plan v2 — 2026-05-24 — 9 seguridad · 10 integridad datos · 16 altos · 14 medios · 9 bajos — Total: 58 items nuevos (no duplica PLAN_MEJORAS.md)*
