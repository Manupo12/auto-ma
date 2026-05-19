# Tomy Completo — Diseño del sistema final para producción

**Fecha:** 2026-05-19
**Autor:** Diseño en colaboración Manu + Claude
**Estado:** Aprobado para implementación
**Continúa de:** `2026-05-19-fase-a-pipeline-portales-design.md` (Fase A ya implementada)

---

## 1. Objetivo

Llevar el sistema RILO SAS a un estado donde **Sandra (la fisioterapeuta) hace SOLO 3 cosas por paciente**:

1. Atender al paciente en consulta (graba audio, opcionalmente toma notas crudas).
2. Subir el audio al dashboard (drag & drop, 1 click).
3. **10-20 min después**, recibir Telegram "✅ Listo", abrir dashboard y revisar/aprobar los 7 formatos generados (o pedir correcciones por chat).

**Todo lo demás lo hace Tomy automáticamente:**
- Transcripción de audio de 1h+ con Deepgram nova-2 + diarización.
- Cruce de transcripción con datos pre-extraídos de Medifolios + ARL Positiva (Fase A).
- Cruce con notas crudas que Sandra haya escrito en su workspace.
- Cruce con formatos antiguos/desorganizados que Sandra subió como referencia.
- Síntesis maestra con reglas clínicas (custody.py + json_validator.py).
- Generación de los 7 formatos DOCX (doc_generator.py).
- QA 10 capas (`skills/verificar-documento/`).
- Conversión a PDF/A para archivo legal.
- Notificación Telegram al finalizar.

**Y Tomy debe manejar todos los casos alternos:**
- Paciente fuera de agenda (no pre-extraído) → extracción al vuelo.
- Audio largo (1h+) o de mala calidad → chunking + diagnóstico.
- Portal caído durante extracción → modo degradado.
- Datos contradictorios entre fuentes → prevalece reglas clínicas + marca ❌.
- Datos críticos faltantes → Tomy pregunta a Sandra de forma específica (no genérica).
- Sandra dicta corrección por chat → Tomy actualiza JSON + regenera formatos afectados.
- Sandra sube formato antiguo desorganizado → Tomy lo reescribe limpio cruzando con verificados.

---

## 2. Contexto: qué ya existe (Fase A completada)

**Backend en producción WSL :8000:**
- `lote_worker.py` — subprocess aislado para evitar OOM con DeepSeek v4.
- `playwright_real/` — extractor real Medifolios + Positiva.
- `cron_pre_extraccion.py` — APScheduler 21:00 COL: pre-extrae datos del día siguiente.
- `chat_handler.py` — carga datos verificados desde JSON pre-extraído + sugiere extracción on-demand.
- `notificador.py` — Telegram + agenda Gmail.
- `flujo_audio.py` — Deepgram nova-2 + diarización Sandra/Paciente.
- `doc_generator.py` — 7 funciones `generar_*` (genera DOCX y opcionalmente PDF/A).
- `custody.py`, `json_validator.py`, `format_selector.py`, `fusionador.py` — capas semánticas.
- `correction_loop.py` — interpreta correcciones en lenguaje natural.

**Dashboard Next.js en :3000:**
- 6 páginas: Home, Pacientes, Formatos, Chat, Archivos, Subir Audio.
- Componentes: Sidebar, ConfianzaBadge, ReconciliacionAlert.
- Diseño funcional pero NO boomer-optimizado.

**Skills (Hermes):**
- `flujo-browser` — mapa exhaustivo Medifolios + Positiva.
- `flujo-audio` — pipeline Deepgram.
- `generar-documento` — guías de los 7 formatos.
- `verificar-documento` — QA 10 capas con scripts ejecutables.
- `rilo-despliegue` — setup WSL, cron jobs.

**Lo que NO funciona como debería hoy (sin Tomy Completo):**
- Sandra sube audio → solo se transcribe + extrae campos por regex. No genera formatos automáticamente.
- No hay pipeline end-to-end. Sandra debe ir manualmente a "Formatos" y darle a "Generar".
- El chat de Tomy no organiza formatos crudos — solo "responde" texto.
- Casos alternos no se manejan elegantemente.
- Dashboard no es boomer-proof: tipografía pequeña, filtros técnicos, lenguaje de programador.

---

## 3. Arquitectura del sistema completo

```
┌───────────────────────────────────────────────────────────────────────────┐
│  SANDRA — atiende paciente, graba audio                                   │
└────────────────────────────────┬──────────────────────────────────────────┘
                                 │ 1) sube audio (dashboard)
                                 ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  DASHBOARD NEXT.JS (boomer-proof)                                         │
│  ┌──────────────────┐  ┌────────────────────┐  ┌──────────────────────┐  │
│  │ Vista "Mi Día"   │  │ Vista Paciente 360 │  │ Subida audio simple  │  │
│  │ (agenda + status)│  │ (todo en 1 panel)  │  │ (drag & drop gigante)│  │
│  └──────────────────┘  └────────────────────┘  └──────────────────────┘  │
└────────────────────────────────┬──────────────────────────────────────────┘
                                 │ HTTP :8000
                                 ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  FASTAPI (WSL) — backend orquestador                                      │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  workflow_runner.py — orquesta pipeline end-to-end               │    │
│  │  1. Transcribe audio (chunks si >30min)                          │    │
│  │  2. Carga datos pre-extraídos del paciente                       │    │
│  │     ↳ Si no existe: extrae al vuelo con playwright_real          │    │
│  │  3. Lee notas crudas del workspace                               │    │
│  │  4. Lee formatos crudos subidos (si los hay)                     │    │
│  │  5. Síntesis maestra (LLM razonador, contexto cruzado)           │    │
│  │  6. Genera 7 formatos via doc_generator                          │    │
│  │  7. QA 10 capas via skills/verificar-documento                   │    │
│  │  8. Convierte a PDF/A                                            │    │
│  │  9. Notifica Telegram a Sandra                                   │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  task_db.py — persistencia de tareas en SQLite                   │    │
│  │  Tabla `workflow_tasks`: id, paciente_cc, estado, paso_actual,   │    │
│  │  iniciado_en, terminado_en, error, resultado_json                │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  organizador_formato.py — Caso alterno: formato crudo            │    │
│  │  Lee DOCX desorganizado, cruza con verificados, reescribe limpio │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  correction_resolver.py — Loop conversacional                    │    │
│  │  Sandra: "el siniestro no es X es Y" → Tomy: actualiza + regen   │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  (existentes y mejorados):                                       │    │
│  │  chat_handler · cron_pre_extraccion · playwright_real            │    │
│  │  lote_worker · flujo_audio · doc_generator · notificador         │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────────────┘
                │                          │                       │
        ┌───────▼──────┐         ┌─────────▼───────┐       ┌───────▼─────┐
        │ DeepSeek v4  │         │  Medifolios +   │       │  Deepgram   │
        │ OpenCode Go  │         │  ARL Positiva   │       │   nova-2    │
        └──────────────┘         └─────────────────┘       └─────────────┘
```

---

## 4. Componentes nuevos / modificados

### 4.1 Pipeline asíncrono "Día de Sandra" (CORE)

| Componente | Archivo | Función |
|---|---|---|
| Runner | `backend/workflow_runner.py` | Orquesta 9 pasos del pipeline. Llamable desde endpoint o background. |
| Persistencia | `backend/task_db.py` | Tabla `workflow_tasks` en SQLite. CRUD básico. |
| Paso 1 | `backend/workflow_steps/transcribir.py` | Llama `flujo_audio.transcribir_audio()`. Si dur>30min: chunks. |
| Paso 2 | `backend/workflow_steps/resolver_paciente.py` | Carga JSON pre-extraído. Si no existe: dispara extracción Playwright. |
| Paso 3 | `backend/workflow_steps/leer_notas_crudas.py` | Escanea workspace por archivos con la CC del paciente. |
| Paso 4 | `backend/workflow_steps/leer_formatos_subidos.py` | Lee DOCX subidos por Sandra como referencia. |
| Paso 5 | `backend/workflow_steps/sintetizar_maestro.py` | Llamada LLM razonador con contexto cruzado completo. |
| Paso 6 | `backend/workflow_steps/generar_formatos.py` | Selecciona formatos aplicables + genera DOCX. |
| Paso 7 | `backend/workflow_steps/qa_formatos.py` | Aplica QA 10 capas a cada DOCX. |
| Paso 8 | `backend/workflow_steps/convertir_pdf.py` | LibreOffice → PDF/A. |
| Paso 9 | `backend/workflow_steps/notificar_listo.py` | Telegram "✅ Listo. Revisá en el dashboard." |

**Estado de cada task** progresa: `pendiente → transcribiendo → resolviendo_paciente → leyendo_notas → leyendo_formatos → sintetizando → generando → qa → pdf → notificando → listo` (o `error_en_paso_X`).

**Cada paso es idempotente**: si falla el paso 6, se puede reintentar desde ahí sin re-transcribir.

### 4.2 Organizar formatos crudos existentes (CASO ALTERNO)

Sandra a veces tiene formatos antiguos con info incompleta o desordenada. Quiere que Tomy los reorganice cruzando con datos verificados.

| Componente | Archivo | Función |
|---|---|---|
| Endpoint | `POST /api/organizar-formato` | Recibe DOCX + CC. Devuelve DOCX limpio + reporte. |
| Lógica | `backend/organizador_formato.py` | Lee DOCX, detecta campos vacíos vs llenos vs contradictorios, cruza con verificados, reescribe. |
| Acceso chat | Comando "organiza este formato {nombre archivo}" | Detecta intención y delega al endpoint. |

### 4.3 Loop de corrección conversacional

Sandra dice por chat: *"El siniestro no es 503463870 es 503476658"*. Tomy debe:

1. Identificar campo afectado y nuevo valor.
2. Actualizar `storage/data/{cc}-completo.json` con la corrección + marca de origen "manual_sandra".
3. Identificar formatos que dependen de ese campo (todos los 7 si es siniestro).
4. Regenerar esos formatos.
5. Confirmar a Sandra: *"Listo, actualicé el siniestro y regeneré los 7 formatos. Revisá."*

| Componente | Archivo | Función |
|---|---|---|
| Resolver | `backend/correction_resolver.py` | Usa `correction_loop.py` + LLM para extraer (campo, valor_nuevo, valor_anterior). |
| Aplicador | `backend/aplicador_correccion.py` | Actualiza JSON + regenera formatos afectados. |
| Endpoint | `POST /api/corregir-paciente/{cc}` | Recibe `{mensaje, formato_id?}`. |

### 4.4 Casos alternos

| Caso | Manejo |
|---|---|
| **Paciente fuera de agenda** | Si Sandra sube audio con `paciente_cc` no en agenda → workflow_runner dispara `playwright_real.extraer_paciente_completo()` antes del paso 5. |
| **Audio largo (>30 min)** | `transcribir.py` divide en chunks de 25 min con `ffmpeg` y los procesa secuencialmente. Concatena transcripciones. |
| **Audio mala calidad** | `flujo_audio.transcribir_audio` evalúa `confidence` global. Si <0.6: marca el task con warning, sigue, pero alerta a Sandra "el audio tiene baja calidad, los datos cualitativos pueden estar incompletos". |
| **Portal caído durante extracción** | `playwright_real/session.py` ya tiene 3 reintentos. Si fallan: workflow_runner sigue con `datos_portales = None` y `sintetizar_maestro` agrega "[VERIFICAR]" a campos que dependían del portal. Telegram a Sandra: "Hoy no pude verificar contra Positiva — usé tus notas." |
| **Datos críticos faltantes** | `sintetizar_maestro` detecta gaps en campos REQUIRED. Tomy responde en lugar de generar formatos: *"Necesito esto para generar formatos: 1) Siniestro de Juan, 2) Empresa. ¿Me los das?"* Sandra responde por chat. |
| **Sandra dicta corrección por voz** | (Fase E, no en este plan) — Sandra sube audio de "corrección por voz" → flujo_audio transcribe → correction_resolver aplica. |

### 4.5 Dashboard Sandra-first

Rediseño focalizado en **boomer-proofing**. NO es un rewrite total; modifica páginas existentes + agrega 2 nuevas.

**Principios:**
- Tipografía mínima `text-lg` (18px). Encabezados `text-3xl`+.
- 1 acción principal por pantalla, en botón grande con icono.
- Lenguaje sin jerga técnica: "su carpeta" en vez de "workspace", "expediente" en vez de "JSON".
- Confirmaciones explícitas: cualquier acción destructiva pide "¿Estás segura?".
- Estados visibles con colores y iconos (🟢🟡🔴), no badges minimalistas.
- Datos del paciente en formato leíble (nombre completo grande, no "CC: 1193143688" como título).

**Páginas nuevas:**
- `/hoy` — Mi Día. Agenda visual con timeline, status del procesamiento de cada paciente. Reemplaza a Home como landing.
- `/paciente/[cc]` — Vista 360 del paciente. UN panel con: datos personales, fuentes verificadas, audios subidos, formatos generados con estado, chat de correcciones.

**Páginas modificadas:**
- `/subir-audio` — simplificar: 1 zona drag-and-drop gigante con texto "Arrastra el audio aquí" + después de subir, redirige a `/paciente/{cc}` mostrando el procesamiento en vivo.
- `/chat` — agregar contexto del paciente activo (si Sandra viene desde `/paciente/{cc}/chat`).

**Componentes nuevos:**
- `<TimelinePaciente />` — pasos del workflow visuales (✓ Transcribiendo → ✓ Cruzando → ⏳ Generando).
- `<FormatoCard />` — card grande con preview + botón "Aprobar" o "Corregir".
- `<BotonGigante />` — botón con icono + texto en 2 líneas para acciones principales.
- `<EstadoVisual />` — semáforo grande con texto descriptivo.

### 4.6 Producción endurecida

| Componente | Archivo | Función |
|---|---|---|
| Auth | `backend/auth_simple.py` | PIN de 4 dígitos por dispositivo. Cookie `rilo_session` con HMAC. Suficiente para uso doméstico. |
| Backup | `backend/backup_diario.py` | Comprime `storage/` (sin audios) diario a las 23:00 → Telegram a Manu (no a Sandra). |
| Health | `GET /api/system/health` | Estado de Deepgram, OpenCode Go, Telegram, Gmail, portales, disk space, RAM. |
| Costos | `backend/costos_tracker.py` | Cuenta tokens LLM por día. Alerta en Telegram si >umbral. |
| Audit log | `storage/audit.log` | Una línea por acción de Sandra (subió audio, aprobó formato, corrigió). Sin datos sensibles. |

---

## 5. Flujo end-to-end "Día perfecto"

```
20:30 COL — Noche anterior
─────────────────────────
   cron_pre_extraccion lee Gmail
   → agenda mañana: 3 pacientes
   → Playwright extrae cada uno
   → JSON en storage/data/
   → Telegram: "🌙 Mañana 3 citas. Datos listos. Buenas noches."

09:00 COL — Mañana
─────────────────
   Sandra atiende a Juan (CC 1193143688)
   → graba audio.m4a (1h 15min)
   → toma notas crudas en su workspace
   
10:15 COL
─────────
   Sandra abre dashboard → /subir-audio
   → drag-and-drop "audio.m4a" + selecciona "Juan Carlos"
   → CLICK [Procesar paciente] (botón gigante)
   → dashboard redirige a /paciente/1193143688
   
10:15-10:30 COL — Tomy trabaja en background
────────────────────────────────────────────
   workflow_runner crea task_id=abc123, paciente_cc=1193143688
   
   PASO 1 (3 min): transcribir.py → Deepgram chunks → 12K palabras
   PASO 2 (5 seg): resolver_paciente.py → JSON pre-extraído OK
   PASO 3 (2 seg): leer_notas_crudas.py → 2 archivos del workspace
   PASO 4 (1 seg): leer_formatos_subidos.py → 0 archivos (no subió ninguno)
   PASO 5 (4 min): sintetizar_maestro.py → contexto 25K chars → LLM 16K reasoning
                   → datos clínicos cruzados con marcas ✅/⚠️/❌
   PASO 6 (2 min): generar_formatos.py → 7 DOCX en storage/docs/
   PASO 7 (1 min): qa_formatos.py → 6 OK, 1 con warning (campo X cuestionable)
   PASO 8 (3 min): convertir_pdf.py → 7 PDFs en storage/pdfs/
   PASO 9 (1 seg): notificar_listo.py → Telegram

10:30 COL
─────────
   Sandra recibe Telegram:
     "✅ Listo! Procesé los datos de Juan Carlos.
      7 formatos generados (1 con warning).
      Revisalos: http://localhost:3000/paciente/1193143688"
   
   Sandra abre el link → ve 7 cards grandes:
     ✅ Análisis de Exigencias    [Aprobar] [Corregir]
     ✅ Carta de Medidas          [Aprobar] [Corregir]
     ✅ Carta de Recomendaciones  [Aprobar] [Corregir]
     ✅ Cierre de Caso            [Aprobar] [Corregir]
     ✅ Citación Empresas         [Aprobar] [Corregir]
     ✅ Prueba de Trabajo         [Aprobar] [Corregir]
     ⚠️ VOI (warning: campo seguro_social vacío)  [Aprobar] [Corregir]
   
   Sandra clica [Aprobar] en 6 → ✅ marcados
   Sandra clica [Corregir] en VOI → chat se abre
   Sandra: "el seguro es Sura"
   Tomy: actualiza JSON + regenera VOI → ✅ listo
   Sandra clica [Aprobar] en VOI
   
   Sandra: ✅ 7 formatos listos en 15 minutos. Tiempo manual: ~5 min.
   (Antes: ~2 horas)
```

---

## 6. Optimización de tokens (continúa lo de Fase A)

| Tarea | Modelo |
|---|---|
| Transcripción audio | Deepgram (sin tokens LLM) |
| Extracción de datos por documento | `deepseek-v4-flash` (sin razonamiento) |
| Síntesis maestra (cruce y razonamiento clínico) | `deepseek-v4-pro` (con razonamiento, SYSTEM_PROMPT completo) |
| Organización de formato crudo | `deepseek-v4-pro` (requiere razonamiento) |
| Loop de corrección (entender qué pide Sandra) | `deepseek-v4-flash` (clasificación) |
| QA 10 capas | Sin LLM (reglas deterministas) |

**Para audios largos (>30 min):**
- Transcripción se hace en chunks de 25 min con ffmpeg → 3 chunks para audio de 1h15.
- Cada chunk se procesa en paralelo (Deepgram acepta concurrencia).
- Resultado: ~5 min total para audio de 1h vs ~15 min secuencial.

**Para síntesis con contexto >30K chars:**
- Resumen progresivo por bloques de 8K chars.
- Síntesis final con resúmenes + datos verificados (~12K chars total).
- Mantiene calidad clínica.

---

## 7. Errores y manejo

| Tipo de error | Manejo |
|---|---|
| Audio corrupto / formato no soportado | Workflow falla en paso 1. Task = `error_en_paso_1`. Telegram: "el audio no se pudo procesar. ¿Lo grabás de nuevo?". |
| Deepgram timeout | Reintentos: 60s, 120s, 240s. Si todos fallan: task = error, Telegram. |
| Paciente CC no en portales | Si Sandra dice la CC mal o el paciente nunca fue → task continua sin datos verificados, marca todos los campos del portal como [VERIFICAR]. Sandra puede aprobar igual. |
| LLM síntesis devuelve vacío | Reintentos (ya implementado en lote_worker). Si finalmente vacío: task warning, Sandra recibe formatos parciales con marcas explícitas de qué falta. |
| QA detecta error crítico | Formato afectado se marca `⚠️ requiere revisión`, no se genera PDF, se muestra a Sandra para corrección. |
| Disk space < 1GB | Health endpoint alerta. Backup automatico mueve audios antiguos a backup. |
| Sandra interrumpe (click "cancelar") | Task = `cancelado`. Limpia archivos parciales. |

---

## 8. Métricas de éxito

Para considerar Tomy Completo en producción exitosa, en 2 semanas:

- ✅ Sandra usa el flujo `sube audio → recibe Telegram → aprueba en dashboard` para ≥80% de pacientes (vs flujo manual).
- ✅ Tiempo medio del workflow: < 20 min por paciente (1h audio + 9 pasos).
- ✅ Tasa de aprobación sin corrección: > 60% (Sandra aprueba directo).
- ✅ Tasa de corrección manual: < 30% (Sandra usa chat para ajustes).
- ✅ Tasa de error técnico: < 5% (Sandra ve "intentá de nuevo").
- ✅ Cero crashes OOM (mantenido de Fase A).
- ✅ Costo LLM/paciente: < $0.10 (estimado con DeepSeek v4 razonado en síntesis).

---

## 9. Roadmap completo (todo lo que queda)

| # | Subsistema | Estimación | Estado |
|---|---|---|---|
| 1 | Workflow runner asíncrono + task_db | 4 sesiones | Plan |
| 2 | 9 pasos del workflow (transcribir...notificar) | 6 sesiones | Plan |
| 3 | Organizador de formatos crudos | 2 sesiones | Plan |
| 4 | Loop de corrección conversacional | 2 sesiones | Plan |
| 5 | Casos alternos (4) | 2 sesiones | Plan |
| 6 | Dashboard rediseño (6 cambios) | 4 sesiones | Plan |
| 7 | Auth + backup + health + costos | 2 sesiones | Plan |
| 8 | Testing E2E completo | 2 sesiones | Plan |
| 9 | Rollout y monitoreo | 1 sesión | Plan |
| **Total** | | **~25 sesiones** | |

Esfuerzo grande pero parcelable. OpenCode puede ejecutar 2-3 tasks por sesión bien definidas. Estimado: 2-3 semanas de implementación con sesiones cortas.

---

## 10. No-objetivos (explícitos)

- ❌ Rewrite del backend Python existente (mantener `doc_generator.py`, `custody.py`, etc.).
- ❌ Cambiar de FastAPI a otro framework.
- ❌ Migrar de Next.js a otro framework.
- ❌ Cambiar de DeepSeek a otro modelo LLM.
- ❌ Implementar dictado por voz para correcciones (Fase F futura).
- ❌ Multi-tenant / multi-clínica (Sandra es la única usuaria).
- ❌ Soporte offline (asume internet siempre disponible).
- ❌ Mobile app nativa (responsive web es suficiente).

---

**Fin del documento.**
