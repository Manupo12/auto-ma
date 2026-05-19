# Fase A — Pipeline IA estabilizado + Verificación real contra portales

**Fecha:** 2026-05-19
**Autor:** Diseño en colaboración Manu + Claude
**Estado:** En revisión

---

## 1. Resumen ejecutivo

Esta es la **primera de cuatro fases** para llevar el sistema RILO SAS a producción diaria con Sandra. Fase A se enfoca en dejar el **pipeline IA estable** (sin crashes OOM) y la **verificación contra Medifolios + ARL Positiva implementada de verdad** (no esqueleto). Sin esto, ninguna fase siguiente puede construirse con confianza.

**Objetivo concreto:** que Tomy procese 9+ documentos por paciente sin crashearse y que cada noche pre-extraiga los datos de los pacientes de la agenda del día siguiente, dejando todo listo para que Sandra al día siguiente sólo grabe el audio y reciba los formatos casi terminados.

**Roadmap de fases (contexto, no scope de este doc):**

| Fase | Sub-proyecto | Estado |
|---|---|---|
| **A** | Estabilizar pipeline IA + portales reales | **Este doc** |
| B | Rediseñar Tomy: chat que organiza + corrige documentos (no sólo responde) | Spec futura |
| C | Dashboard Sandra-first: vista paciente 360 + modo consulta en vivo + UX boomer | Spec futura |
| D | Endurecimiento producción: auth, backup verificado, logs auditoría | Spec futura |

---

## 2. Contexto y motivación

### 2.1 El problema OOM (crash actual)

Síntoma: `exit code 137` al procesar 7-9 formatos de un paciente.

Causa raíz: DeepSeek v4 es modelo de razonamiento. Cada llamada genera 8K-15K tokens de `reasoning_content` antes de producir la respuesta. Para 9 documentos en 5 lotes de extracción + 1 llamada de síntesis = 6 llamadas LLM secuenciales en el mismo proceso Python:

| Etapa | Llamadas | Razonamiento c/u | Total acumulado |
|---|---|---|---|
| Extracción | 5 | ~8K-12K | ~50K tokens |
| Síntesis final | 1 | ~12K-15K | ~15K tokens |
| **Total en RAM** | 6 | | **~65K tokens** |

`requests.Response` + `json.loads` mantienen buffers en RAM. El GC de Python no libera entre llamadas. El proceso supera 512MB y el contenedor lo mata.

### 2.2 La verificación contra portales NO está implementada

Tras revisión exhaustiva del código a fecha 2026-05-19:

- `backend/extractor_medifolios.py`: NO ejecuta browser. Son `dataclasses` con lista de pasos guía.
- `backend/extractor_positiva.py`: idem.
- `backend/browser_session.py`: declara explícitamente "*NO es un script que se ejecuta solo — es una guía de patrones que el agente debe seguir al interactuar con los portales vía browser tools*".
- `backend/requirements.txt`: NO incluye Playwright, Selenium, browser-use ni Chromium.
- `backend/puente_docker.py`: invoca `orquestador.py --cc X --fusionar --validar` pero esa flag `--cc` no existe en `orquestador.py`.
- El contenedor `hermes-a34da917` que `puente_docker.py` busca **no está definido en `docker-compose.yml`**.

Lo que SÍ existe y es valioso: **mapas exhaustivos de los portales** en `skills/flujo-browser/references/` (selectores CSS, IDs, JS snippets, flujos de navegación). Estos mapas reducen drásticamente el trabajo de implementar Playwright real.

Lo que pasa hoy: cuando Sandra pide "verifica X", Tomy sólo responde con texto sugiriendo qué verificar manualmente. No hay extracción real.

### 2.3 El flujo deseado: "día listo automágicamente"

Sandra quiere que el sistema le ahorre el trabajo manual de preparar cada paciente antes de cada cita. La automatización completa se ve así:

```
NOCHE (sin Sandra)
9:00 PM → Gmail: nuevo correo de Medifolios "Agenda de mañana"
        → email_reader extrae citas (Juan 8AM, Rosa 10AM, ...)
        → notificador → Telegram a Sandra:
          "🌙 Mañana 3 citas: Juan 8AM, Rosa 10AM, Luis 2PM.
          Empiezo a buscar sus datos en los portales..."

9:05-9:25 PM → cron_pre_extraccion para cada paciente:
        → Playwright (headless) navega Medifolios + Positiva
        → JSON completo en storage/data/{cc}-completo.json
        → si falta dato: marca [VERIFICAR] (no crashea)
        → si discrepancia siniestro Medifolios vs Positiva: marca ❌

9:30 PM → notificador → Telegram:
        "✅ Listo. Datos cargados para los 3 pacientes.
        Mañana sólo grabas el audio y yo armo los formatos.
        ⚠️ Para Luis falta el siniestro en Medifolios — te pregunto mañana."

MAÑANA (Sandra atendiendo)
8:00 AM  → Sandra atiende a Juan, graba audio, toma notas crudas
8:45 AM  → Sandra sube audio al dashboard
         → flujo_audio.py transcribe + diariza
         → chat_handler.py une:
            • JSON pre-extraído de Juan (portales)
            • Transcripción Deepgram
            • Notas crudas (workspace)
            • Síntesis con razonamiento completo
         → genera los formatos que aplican según estado
9:00 AM  → Sandra ve formatos casi listos. Sólo revisa y aprueba.
```

---

## 3. Objetivos y no-objetivos

### 3.1 Objetivos (Fase A)

- ✅ El sistema NO crashea al procesar 9+ documentos de un paciente.
- ✅ La extracción real contra Medifolios + ARL Positiva funciona desde código autónomo (sin necesidad de Hermes/Claude Code corriendo).
- ✅ Cada noche se pre-extraen los datos de los pacientes de la agenda del día siguiente.
- ✅ Sandra recibe notificaciones Telegram del estado de la pre-extracción.
- ✅ El chat de Tomy carga automáticamente los datos pre-extraídos cuando Sandra menciona una CC.
- ✅ Manejo de errores: portales caídos, sesión expirada, discrepancias, datos faltantes → todo se reporta sin bloquear el flujo.
- ✅ Optimización de tokens: usar modelo barato para extracción mecánica; modelo razonador completo para síntesis.
- ✅ Feature flag para rollback inmediato si algo falla en producción.

### 3.2 No-objetivos (van a Fases B/C/D)

- ❌ Rediseñar el chat para que ORGANICE/CORRIJA documentos reescribiéndolos (Fase B).
- ❌ Rediseñar la UI del dashboard para Sandra (Fase C).
- ❌ Crear la vista "paciente 360" unificada (Fase C).
- ❌ Auth + backup verificado + logs auditoría (Fase D).
- ❌ Mejorar `doc_generator.py` (2,172 líneas) — queda como está.
- ❌ Cambiar de OpenCode Go a otro proveedor LLM.

---

## 4. Arquitectura general

```
┌──────────────────────────────────────────────────────────────────┐
│                    DASHBOARD NEXT.JS (Sandra)                    │
│                       :3000 — sin cambios mayores                │
└────────────────────┬─────────────────────────────────────────────┘
                     │ HTTP :8000
┌────────────────────▼─────────────────────────────────────────────┐
│                  FASTAPI (WSL — único proceso)                   │
│                                                                  │
│  ┌──────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │ chat_handler │  │ portal_         │  │ cron_pre_           │  │
│  │   (v10)      │  │  extractor      │  │  extraccion         │  │
│  │              │  │ (NUEVO)         │  │ (APScheduler NUEVO) │  │
│  └──────┬───────┘  └────────┬────────┘  └──────────┬──────────┘  │
│         │                   │                      │             │
│         ▼                   ▼                      ▼             │
│  ┌──────────────────────────────┐    ┌──────────────────────────┐│
│  │ lote_worker.py (subprocess)  │    │ playwright_real/         ││
│  │ ──────────────────────────── │    │  ├── session.py          ││
│  │ python -m backend.lote_      │    │  ├── medifolios.py       ││
│  │   worker --tipo extraer      │    │  ├── positiva.py         ││
│  │   --archivos a,b --modelo    │    │  └── orquestador.py      ││
│  │   deepseek-chat              │    │ (chromium headless,      ││
│  │ → stdout JSON                │    │  contexto persistente)   ││
│  │ (muere → libera RAM)         │    └──────────────────────────┘│
│  └──────────────────────────────┘                                │
└──────────────────────────────────────────────────────────────────┘
                     │                          │
              ┌──────▼──────┐            ┌──────▼──────────────────┐
              │ DeepSeek v4 │            │ server0medifolios.net + │
              │ OpenCode Go │            │ positivacuida.gov.co    │
              └─────────────┘            └─────────────────────────┘
```

**Cambios clave:**

| Componente | Estado actual | Cambio en Fase A |
|---|---|---|
| `chat_handler.py` | Procesa lotes en mismo proceso → OOM | Delega a `lote_worker.py` vía subprocess. Carga datos pre-extraídos antes de síntesis. |
| `lote_worker.py` | No existe | Nuevo. Procesa 1 lote, imprime JSON, muere. |
| `playwright_real/` | No existe | Nuevo. Implementación browser real con Playwright. |
| `cron_pre_extraccion.py` | No existe | Nuevo. APScheduler dentro de FastAPI. |
| `extractor_medifolios.py` | Dataclasses guía sin ejecutar | Se mantiene como referencia documental. Marcado `[DEPRECATED]`. |
| `extractor_positiva.py` | idem | idem. |
| `browser_session.py` | Dataclasses guía | Se mantiene; lógica de re-login se traslada a `playwright_real/session.py`. |
| `puente_docker.py` | Roto (contenedor inexistente) | **Eliminar**. Ya no se necesita bridge WSL→Docker. |
| `orquestador.py` | CLI para flujo manual | Sin cambios. Sigue funcionando para tests CLI. |

---

## 5. Componentes detallados

### 5.1 `backend/lote_worker.py` (nuevo, ~150 líneas)

**Propósito:** Aislar cada llamada LLM en un subprocess separado para liberar memoria al terminar.

**Interfaz CLI:**

```bash
python -m backend.lote_worker \
  --tipo extraer \
  --archivos "/path/a.docx,/path/b.docx" \
  --modelo deepseek-chat \
  --cc 1193143688
```

**Salida:** JSON por stdout, exit 0 si OK, exit 1 si error con stacktrace en stderr.

**Tipos de invocación:**

| Tipo | Modelo | Propósito | Prompt |
|---|---|---|---|
| `extraer` | `deepseek-chat` (sin razonamiento) | Sacar campos literales de 1-2 docx | Mini-prompt 400 chars con formato exacto de salida |
| `sintetizar` | `deepseek-v4-pro` (con razonamiento) | Cruzar todos los datos, detectar discrepancias, organizar | SYSTEM_PROMPT actual completo (mantiene calidad) |

**Salida garantizada (campos por documento):**
```json
{
  "ok": true,
  "modelo": "deepseek-chat",
  "tokens": {"input": 1240, "output": 380, "reasoning": 0},
  "tiempo_s": 8.4,
  "datos": {
    "paciente": "Juan Carlos Duran Narvaez",
    "cc": "1193143688",
    "siniestro": "503463870",
    "fecha_evento": "02/03/2026",
    "diagnostico": "S611",
    "empresa": "...",
    "fechas": {"consulta": "...", "valoracion": "..."},
    "segmento": "DEDOS MANO",
    "campos_vacios": ["telefono", "afp"],
    "observaciones": "..."
  }
}
```

**Por qué subprocess y no thread/async:**
- Threads/async comparten heap del proceso padre → reasoning leak NO se libera.
- Subprocess = proceso nuevo en kernel → cuando muere, OS libera la página de RAM completa.
- Costo: ~80ms de overhead por subprocess (insignificante vs latencia LLM ~10s).

**Llamada desde el padre (FastAPI):**

```python
# backend/chat_handler.py (nuevo método)
def _procesar_via_workers(self, archivos: list, cc: str) -> list[dict]:
    resultados = []
    for lote in self._split_en_lotes(archivos, tamano=1):  # 1 doc por subprocess
        proc = subprocess.run(
            ["python", "-m", "backend.lote_worker",
             "--tipo", "extraer",
             "--modelo", "deepseek-chat",
             "--archivos", ",".join(str(p) for p in lote),
             "--cc", cc],
            capture_output=True, text=True, timeout=120
        )
        if proc.returncode == 0:
            resultados.append(json.loads(proc.stdout))
        else:
            _log(f"LOTE_WORKER falló: {proc.stderr[:500]}")
            # No abortar; seguir con el resto
    return resultados
```

### 5.2 `backend/playwright_real/` (nuevo, ~600 líneas total)

**Estructura:**

```
backend/playwright_real/
├── __init__.py
├── session.py          # Manejo login + re-auth + storage_state
├── medifolios.py       # 4 funciones: login, get_paciente, get_siniestro, get_historia
├── positiva.py         # 4 funciones: login, get_siniestros, get_rehab, get_datos
├── orquestador.py      # extraer_paciente_completo(cc) → JSON unificado
└── selectores.py       # Constantes: CSS/XPath/JS de skills/flujo-browser/references/
```

**`session.py` — gestión de sesión persistente:**

- Guarda `storage_state` (cookies + localStorage) en `storage/playwright_sessions/{portal}.json`.
- Antes de cada extracción: carga el state, verifica con un heartbeat (locator del menú post-login).
- Si heartbeat falla → re-login automático con credenciales de `.env`.
- Sesiones expiran ~15 min en ambos portales (documentado en `skills/flujo-browser/references/login-credentials.md`).
- Reutiliza browser context entre llamadas dentro del mismo run del cron (1 navegador para 6 pacientes).

**`medifolios.py` — extracción concreta:**

```python
async def get_paciente_completo(page: Page, cc: str) -> dict:
    """Aprovecha los selectores documentados en skills/flujo-browser/references/."""
    await _navegar_a_pacientes(page)
    await _cargar_paciente(page, cc)  # JS para disparar búsqueda (no Enter)
    
    datos = {}
    datos.update(await _extraer_datos_personales(page))   # Form principal
    datos.update(await _extraer_datos_generales(page))    # EPS/AFP/Empresa
    datos.update(await _extraer_historia_clinica(page))   # Sidebar Historia
    datos.update(await _extraer_siniestro_de_agenda(page, cc))  # Popup observaciones
    
    return datos
```

**`positiva.py` — extracción concreta:**

Idem para las 6 pestañas de Consulta Integral: SINIESTROS, REHABILITACIÓN INTEGRAL, DATOS ASEGURADO, GESTIÓN AUTORIZACIONES, EVOLUCIONES, BITACORAS.

**`orquestador.py` — unión de fuentes:**

```python
async def extraer_paciente_completo(cc: str) -> dict:
    """Llama a medifolios + positiva, cruza siniestros, marca discrepancias."""
    async with sesion_compartida() as (page_medi, page_pos):
        datos_medi = await medifolios.get_paciente_completo(page_medi, cc)
        datos_pos = await positiva.get_paciente_completo(page_pos, cc)
    
    fusionado = fusionador.fusionar(datos_medi, datos_pos)
    fusionado["_meta"] = {
        "extraido_en": datetime.now().isoformat(),
        "fuentes": ["medifolios", "positiva"],
        "discrepancias": _detectar_discrepancias(datos_medi, datos_pos),
    }
    return fusionado
```

**Errores y manejo:**

| Caso | Comportamiento |
|---|---|
| Portal caído / timeout | 3 reintentos exponenciales (2s, 5s, 15s). Si todos fallan: estado `parcial`, alerta Telegram, NO bloquea cron. |
| CC no existe en portal | Marca campos como `[VERIFICAR MANUAL]`, sigue con siguiente paciente. |
| Sesión expira a mitad | Re-login automático y continúa donde quedó (usa `extraction_progress` de `browser_session.py`). |
| HTML del portal cambió (selector falla) | Marca el campo como `[ESTRUCTURA CAMBIÓ]`, captura screenshot a `storage/screenshots/{fecha}-{cc}-{portal}.png`, Telegram a Manu. |
| Discrepancia siniestro Medi vs Pos | Guarda ambos, marca `❌ DISCREPANCIA`, prevalece Positiva (fuente oficial), Telegram. |

### 5.3 `backend/cron_pre_extraccion.py` (nuevo, ~120 líneas)

**Tecnología:** `APScheduler` con `AsyncIOScheduler` dentro del proceso FastAPI (sin cron de sistema, sin systemd, sin contenedor extra).

**Triggers configurados:**

| Hora | Job | Acción |
|---|---|---|
| 21:00 COL | `revisar_email_y_extraer` | 1) Llama `email_reader.check_agenda_manana()`. 2) Por cada CC, llama `playwright_real.extraer_paciente_completo()`. 3) Guarda JSON. 4) Telegram al inicio y al fin. |
| 06:30 COL | `recordatorio_matinal` | Telegram con resumen de citas del día y avisos pendientes. |
| Cada hora | `health_check_portales` | Heartbeat ligero (login + carga 1 página) para detectar caídas tempranas. |

**Configuración:**

```python
# backend/cron_pre_extraccion.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

COL = pytz.timezone("America/Bogota")
scheduler = AsyncIOScheduler(timezone=COL)

scheduler.add_job(
    revisar_email_y_extraer,
    CronTrigger(hour=21, minute=0, timezone=COL),
    id="pre_extraccion_nocturna",
    misfire_grace_time=3600,  # si se cayó FastAPI, ejecutar al levantar (hasta 1h tarde)
)
```

**Cooldown entre pacientes:**
- 30s de espera entre extracciones del mismo cron run.
- Por qué: evita parecer bot, da margen a sesión, mantiene RAM bajo control.
- 6 pacientes × (~45s extracción + 30s espera) ≈ 7-8 minutos total. Aceptable a las 9 PM.

### 5.4 Cambios en `chat_handler.py` (refactor a v10, ~200 líneas modificadas)

**Nuevo flujo dentro de `procesar_mensaje()`:**

```python
def procesar_mensaje(mensaje, paciente_cc, historial):
    # 1. Workspace files (sin cambios)
    workspace_files = _listar_workspace()
    
    # 2. Detectar CC (sin cambios)
    cc = paciente_cc or _detectar_cc(mensaje)
    
    # 3. NUEVO: cargar datos pre-extraídos si existen
    datos_verificados = _cargar_json_paciente(cc) if cc else None
    
    # 4. Archivos del paciente
    archivos_paciente = _buscar_archivos_paciente(cc=cc, mensaje=mensaje)
    
    # 5. Decisión de procesamiento
    if archivos_paciente and len(archivos_paciente) >= 3:
        # NUEVO: subprocess en lugar de mismo proceso
        datos_extraidos_docs = _procesar_via_workers(archivos_paciente, cc)
        doc_content = _comprimir_datos(datos_extraidos_docs)
    elif archivos_paciente:
        doc_content = _leer_multiples_docx(archivos_paciente)
    else:
        archivo = _buscar_archivo(mensaje)
        doc_content = _leer_docx(archivo) if archivo else ""
    
    # 6. Síntesis final (1 subprocess con modelo razonador)
    respuesta = _sintetizar_via_worker(
        mensaje=mensaje,
        cc=cc,
        datos_verificados=datos_verificados,  # NUEVO
        doc_content=doc_content,
        workspace_files=workspace_files,
    )
    return respuesta
```

**Cuándo Tomy ofrece extraer en vivo:**

Si `cc` está en el mensaje + `datos_verificados is None` (o tiene >24h):
- Tomy responde primero al mensaje original.
- Al final agrega: *"💡 No tengo datos verificados de este paciente todavía. ¿Quiero buscarlo ahora en Medifolios y Positiva? (~2 min). Escribe 'sí' o 'no'."*
- Si Sandra dice "sí" → endpoint `POST /api/verificar/{cc}/extraer-ahora` → ejecuta extracción → próximo turno carga datos.

### 5.5 Endpoints FastAPI (nuevos / modificados)

| Endpoint | Verbo | Estado | Función |
|---|---|---|---|
| `/api/verificar/{cc}` | GET | **Modificado** (ya existía, ahora funciona) | Devuelve `storage/data/{cc}-completo.json` si existe; estado pendiente si no. |
| `/api/verificar/{cc}/extraer-ahora` | POST | **Nuevo** (reemplaza `/extraer` roto) | Dispara `playwright_real.extraer_paciente_completo(cc)` síncrono. Devuelve resultado o estado parcial. |
| `/api/verificar/{cc}/extraer-async` | POST | **Nuevo** | Versión asíncrona: dispara extracción en background y devuelve `task_id`. Sandra puede seguir chateando. |
| `/api/cron/estado` | GET | **Nuevo** | Estado de APScheduler: próxima ejecución, última ejecución, errores. |
| `/api/cron/disparar-ahora` | POST | **Nuevo** | Manual fire del cron nocturno (para testing). |
| `/api/portales/health` | GET | **Nuevo** | Estado actual de Medifolios y Positiva (último heartbeat). |

### 5.6 Cambios en `requirements.txt`

```diff
 fastapi>=0.109.0
 uvicorn[standard]>=0.27.0
 python-docx>=1.1.0
 pydantic>=2.5.0
 python-multipart>=0.0.6
 requests>=2.31.0
 python-dotenv>=1.0.0
+playwright>=1.42.0
+apscheduler>=3.10.4
+pytz>=2024.1
+aiofiles>=23.2.1
```

Plus `playwright install chromium` en el setup.

### 5.7 Variables de entorno nuevas

```diff
 # .env
+# Feature flag para Fase A
+FASE_A_ENABLED=true
+
+# Playwright
+PLAYWRIGHT_DEBUG=false        # true → headed mode para debug
+PLAYWRIGHT_TIMEOUT_MS=30000   # timeout por navegación
+PLAYWRIGHT_SESSIONS_DIR=./storage/playwright_sessions
+
+# Cron
+CRON_HORA_NOCHE=21            # Hora COL para pre-extracción
+CRON_COOLDOWN_PACIENTES_S=30
+
+# Modelos LLM
+LLM_MODEL_EXTRACCION=deepseek-chat       # sin razonamiento, barato
+LLM_MODEL_SINTESIS=deepseek-v4-pro       # con razonamiento, calidad
```

---

## 6. Optimización de tokens (justificación)

**Principio:** Optimizar SÓLO donde la tarea es mecánica. Mantener razonamiento completo donde requiere pensar.

| Tarea | Modelo actual | Modelo propuesto | Ahorro estimado |
|---|---|---|---|
| Extracción de campos literales de 1 .docx | `deepseek-v4-pro` (~10K reasoning) | `deepseek-chat` (~0 reasoning) | ~80% tokens, ~85% latencia |
| Síntesis final cruzando 9 documentos | `deepseek-v4-pro` (~12K reasoning) | `deepseek-v4-pro` (idéntico) | 0% (intencional) |
| Verificación contra portales | No usa LLM (Playwright determinista) | No usa LLM | 100% (sin llamada LLM) |
| Sugerencia "¿quieres extraer?" | Texto fijo en chat_handler | Texto fijo | 0 tokens |

**SYSTEM_PROMPT actual (~3KB) sólo se manda en síntesis.** En extracción se usa un mini-prompt de ~400 chars:

```
Extrae los siguientes campos del documento. Formato EXACTO:
PACIENTE: <nombre completo>
CC: <número>
SINIESTRO: <id>
...
Si un campo no aparece, escribe FALTA.
```

**Estimación realista por paciente (9 docs + verificación):**

| Caso | Tokens hoy | Tokens propuesto | Ahorro |
|---|---|---|---|
| Paciente sin pre-extracción | ~60K input + ~70K reasoning = 130K | ~30K input + ~15K reasoning = 45K | ~65% |
| Paciente con pre-extracción nocturna | ~60K input + ~70K reasoning = 130K | ~20K input + ~12K reasoning = 32K | ~75% |

A precios OpenCode Go (sin precios públicos concretos, asumiendo orden de magnitud ~$0.5/M tokens): de ~$0.065 a ~$0.020 por paciente. Para 6 pacientes/día × 22 días = ~$2.5/mes en lugar de ~$8.5/mes. Si los precios reales difieren, la proporción del ahorro se mantiene (~70%).

---

## 7. Manejo de errores y resiliencia

### 7.1 OOM ya no es posible

Cada subprocess vive máximo 2 minutos. Cuando muere libera RAM. El padre solo retiene JSONs de ~3KB. Para que vuelva a haber OOM tendrían que correr 200+ subprocess simultáneos (no pasa: corren en serie).

### 7.2 Portal caído

`session.py` detecta con heartbeat antes de cada extracción. Si falla:
1. Reintenta 3 veces (2s, 5s, 15s).
2. Si todos fallan: marca paciente como `extraccion_parcial` o `pendiente_portal`.
3. Telegram a Sandra: *"⚠️ ARL Positiva está caído ahora. Voy a reintentar a las 22:00. Mañana vas con los datos que tenemos."*
4. El cron continúa con los demás pacientes.

### 7.3 Sesión expira a mitad de extracción

`session.py` envuelve cada navegación con un try/except específico. Si detecta redirect a `/login`:
1. Re-login automático.
2. Vuelve a la URL donde estaba.
3. Continúa.

Si re-login también falla: marca el paciente como `error_sesion` y sigue.

### 7.4 HTML del portal cambió

Cada selector tiene fallback (CSS → XPath → texto visible). Si los 3 fallan:
1. Screenshot a `storage/screenshots/{fecha}-{cc}-{portal}.png`.
2. Telegram a Manu (no a Sandra): *"🔧 Estructura de Medifolios cambió. Revisa selector X. Screenshot guardado."*
3. Marca campo como `[ESTRUCTURA CAMBIÓ]`.

### 7.5 Discrepancias entre portales

Si Medifolios dice siniestro 503463870 y Positiva dice 503476658:
1. Guarda ambos en `_meta.discrepancias`.
2. Marca el campo final con valor de Positiva + emoji ❌.
3. En el chat de mañana Tomy dirá: *"⚠️ Atención: en Medifolios figura siniestro 503463870 pero en Positiva 503476658. Usé el de Positiva. ¿Coincide con lo que sabes?"*

### 7.6 LLM responde vacío / `finish=length`

Manejo actual (líneas 538-583 de `chat_handler.py`) se mantiene en `lote_worker.py`. Si tras 2 reintentos sigue vacío, devuelve fallback con últimas líneas de razonamiento. No bloquea.

### 7.7 Feature flag para rollback

`.env`:
```bash
FASE_A_ENABLED=false   # vuelve al comportamiento actual
FASE_A_CRON_ENABLED=false   # apaga sólo el cron, mantiene workers
```

Si Sandra reporta cualquier problema en producción → `FASE_A_ENABLED=false` y restart FastAPI. Vuelve a v9 (current). Sin migraciones de DB ni borrado de datos. Los JSONs ya extraídos quedan en disco y se pueden volver a usar después.

---

## 8. Testing

### 8.1 Tests unitarios

| Test | Archivo | Cubre |
|---|---|---|
| `test_lote_worker_extraer_ok` | `tests/test_lote_worker.py` | 1 docx → JSON con campos esperados, exit 0 |
| `test_lote_worker_memoria_estable` | idem | 10 invocaciones secuenciales → memoria del padre estable (psutil) |
| `test_lote_worker_sin_api_key` | idem | falla con exit 1 y mensaje claro |
| `test_playwright_session_login_medi` | `tests/test_playwright_session.py` | login Medifolios → cookie guardada |
| `test_playwright_session_reauth` | idem | sesión inválida → re-login automático |
| `test_extractor_medi_real` | `tests/test_extractor_medi.py` | CC 55162801 → JSON con `nombre`, `cc`, `eps_ips` (CC de Sandra, datos siempre presentes) |
| `test_extractor_pos_real` | `tests/test_extractor_pos.py` | CC 1193143688 → JSON con `siniestro`, `diagnostico` (Juan Carlos) |
| `test_orquestador_cruza_siniestros` | `tests/test_orquestador.py` | Mocks medi+pos con valores distintos → marca discrepancia |
| `test_cron_dispara_extraccion` | `tests/test_cron.py` | Agenda con 2 CCs → 2 JSONs creados |

### 8.2 Tests de integración (end-to-end)

| Test | Cubre |
|---|---|
| `test_e2e_pre_extraccion_nocturna` | Mock Gmail con 2 citas → cron run manual → 2 JSON en storage/data → Telegram disparado |
| `test_e2e_chat_con_datos_verificados` | JSON pre-existe → mensaje "revisa al paciente 1193143688" → respuesta con marcas ✅/⚠️ en <60s |
| `test_e2e_chat_pide_extraccion` | JSON no existe → mensaje con CC → Tomy ofrece extraer → Sandra "sí" → JSON creado + respuesta |
| `test_e2e_oom_no_crashea` | 12 docs simulados → procesamiento completo sin exit 137 |

### 8.3 Tests manuales con Sandra (smoke)

Antes de activar `FASE_A_ENABLED=true` en producción:
1. Pre-extracción manual de Juan Carlos (CC 1193143688). Validar JSON con Sandra/Manu.
2. Chat: "revisa a Juan Carlos" → confirmar marcas ✅/⚠️ y respuesta razonable.
3. Esperar una noche con cron activo → validar Telegram + JSONs al día siguiente.
4. Día completo en sombra (sin que Sandra use el feature) verificando logs.
5. Activar para Sandra. Manu monitorea logs primer día.

---

## 9. Rollout en producción

### 9.1 Pasos de despliegue en WSL

```bash
# 1. Pull en WSL
cd ~/rilo-backend
git pull origin main

# 2. Instalar dependencias nuevas
pip install -r requirements.txt
playwright install chromium

# 3. Crear directorios
mkdir -p storage/playwright_sessions storage/screenshots

# 4. Variables nuevas en .env (con FASE_A_ENABLED=false al principio)
# (editar manualmente .env)

# 5. Restart FastAPI
pkill -f "uvicorn.*server:app"
nohup uvicorn backend.server:app --host 0.0.0.0 --port 8000 > /tmp/rilo.log 2>&1 &

# 6. Sanity check
curl http://localhost:8000/api/health
curl http://localhost:8000/api/portales/health
```

### 9.2 Activación gradual

| Día | Flag | Acción |
|---|---|---|
| D-7 a D-1 | `FASE_A_ENABLED=false` | Sombras: Manu prueba endpoints, mira logs, confirma JSONs. |
| D-1 noche | `FASE_A_CRON_ENABLED=true` | Solo cron, sin tocar chat. Pre-extracción se ejecuta pero Sandra no nota. |
| D-1 mañana | revisar JSONs creados | Manu confirma calidad. |
| D0 | `FASE_A_ENABLED=true` completo | Sandra empieza a usar. Tomy menciona "ahora tengo datos verificados". |
| D+1 a D+7 | monitoreo activo | Manu revisa logs cada noche. |

### 9.3 Métricas a monitorear

- Memoria de FastAPI (psutil cada 60s → archivo log).
- Tiempo total de cron nocturno.
- % de extracciones exitosas vs parciales vs fallidas.
- Tiempo medio de respuesta de chat con/sin datos pre-cargados.
- Discrepancias detectadas por semana.

---

## 10. Decisiones tomadas (con razón)

| Decisión | Razón |
|---|---|
| Mantener DeepSeek v4 (no migrar a Claude/otro) | Cuota OpenCode Go ya pagada; equipo familiarizado; el problema es memoria, no modelo. |
| Subprocess en lugar de threads/async | Sólo subprocess libera reasoning_content del heap Python. |
| Playwright en lugar de Selenium | Async nativo, mejor manejo de sesiones, más moderno, soporta mejor SPAs. |
| Headless por defecto | Sandra no ve ventanas raras; sólo headed para debug. |
| WSL (mismo proceso) en lugar de Docker dedicado | Simpler deployment; menos componentes que monitorear; mamá no instala Docker. |
| APScheduler dentro de FastAPI vs cron del sistema | Un solo proceso para administrar; sobrevive a reinicios con misfire_grace_time. |
| Pre-extracción nocturna + on-demand | Cubre 95% de casos sin esperar; on-demand para casos nuevos del día. |
| Modelo barato sólo en extracción literal | Calidad clínica intacta en síntesis; ahorro real donde no se necesita razonar. |
| Feature flag `FASE_A_ENABLED` | Rollback en <30 segundos si algo falla; cero migración destructiva. |
| Mantener `extractor_*.py` y `browser_session.py` actuales | Documentación valiosa de los pasos; marcados como referencia. |
| Eliminar `puente_docker.py` | Apunta a contenedor inexistente; ya no se necesita bridge. |

---

## 11. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Portales cambian HTML | Media (anual) | Alto | Selectores con fallback CSS→XPath→texto; alerta Telegram a Manu; screenshots de evidencia. |
| Cron falla y nadie se entera | Baja | Medio | Telegram al inicio Y al fin del cron; `/api/cron/estado` accesible desde dashboard. |
| Sesión Playwright se rompe en producción | Media (primeros días) | Medio | Re-login automático; storage_state persistente; logs detallados. |
| Costo en tokens supera presupuesto | Baja | Bajo | Logging de tokens por subprocess; alerta si tokens/día >umbral. |
| `apscheduler` no respeta timezone COL | Baja | Bajo | pytz explícito; test específico con `test_cron_timezone`. |
| Subprocess se cuelga | Baja | Medio | timeout=120s en `subprocess.run`; mata el proceso si supera. |
| WSL/Windows file lock en storage_state | Media | Bajo | Lock file con `fcntl`; reintento al escribir; usar `tmpfile + rename` atómico. |

---

## 12. Próximos pasos tras Fase A

Una vez Sandra esté usando Fase A en producción durante 1-2 semanas con estabilidad:

- **Fase B — Chat que actúa, no sólo responde:** Tomy reescribe documentos (no solo sugiere correcciones), genera nuevos formatos desde la conversación, organiza notas crudas estructuradamente.
- **Fase C — Dashboard Sandra-first:** Vista paciente 360 (chat + audios + formatos + estado verificación en una pantalla); modo consulta en vivo; rediseño visual boomer-friendly; tutoriales contextuales.
- **Fase D — Producción endurecida:** Auth multi-dispositivo; backup verificado con Telegram; logs de auditoría; modo offline parcial.

Cada fase tendrá su propia spec → plan → ejecución.

---

## Anexo A — Mapeo de archivos existentes vs nuevos

```
backend/
├── chat_handler.py                [MODIFICADO — v10, ~200 líneas afectadas]
├── lote_worker.py                 [NUEVO — ~150 líneas]
├── cron_pre_extraccion.py         [NUEVO — ~120 líneas]
├── playwright_real/               [NUEVO — ~600 líneas]
│   ├── __init__.py
│   ├── session.py
│   ├── medifolios.py
│   ├── positiva.py
│   ├── orquestador.py
│   └── selectores.py
├── server.py                      [MODIFICADO — 6 endpoints nuevos/modificados]
├── puente_docker.py               [ELIMINADO]
├── extractor_medifolios.py        [DEPRECATED — marcar al inicio del archivo]
├── extractor_positiva.py          [DEPRECATED — marcar al inicio del archivo]
├── browser_session.py             [DEPRECATED — lógica migrada a playwright_real/session.py]
├── orquestador.py                 [SIN CAMBIOS]
├── notificador.py                 [MODIFICADO — nuevos mensajes Telegram cron]
├── email_reader.py                [SIN CAMBIOS]
├── flujo_audio.py                 [SIN CAMBIOS]
├── doc_generator.py               [SIN CAMBIOS]
├── json_validator.py              [SIN CAMBIOS]
├── format_selector.py             [SIN CAMBIOS]
├── fusionador.py                  [MODIFICADO — ~30 líneas para integrar discrepancias]
├── custody.py                     [SIN CAMBIOS]
├── correction_loop.py             [SIN CAMBIOS]
├── pdf_archivo.py                 [SIN CAMBIOS]
└── verificar_backup.py            [SIN CAMBIOS]

tests/                             [NUEVO directorio]
├── conftest.py
├── test_lote_worker.py
├── test_playwright_session.py
├── test_extractor_medi.py
├── test_extractor_pos.py
├── test_orquestador.py
├── test_cron.py
└── test_e2e.py

docs/superpowers/specs/
└── 2026-05-19-fase-a-pipeline-portales-design.md   [ESTE DOC]
```

---

## Anexo B — Estimación de esfuerzo

| Componente | Líneas | Sesiones de implementación |
|---|---|---|
| `lote_worker.py` + integración chat | ~250 | 1 |
| `playwright_real/session.py` + login básico | ~180 | 1 |
| `playwright_real/medifolios.py` | ~220 | 1-2 |
| `playwright_real/positiva.py` | ~250 | 1-2 |
| `playwright_real/orquestador.py` + fusión | ~80 | 0.5 |
| `cron_pre_extraccion.py` + APScheduler | ~150 | 0.5 |
| Endpoints FastAPI nuevos | ~200 | 0.5 |
| Tests unitarios + integración | ~600 | 1-2 |
| Smoke testing manual con Sandra | — | 0.5 |
| **Total estimado** | **~1,930 líneas + tests** | **6-9 sesiones** |

Esfuerzo medio-alto. Distribuible en 2-3 semanas con sesiones cortas.

---

**Fin del documento.**
