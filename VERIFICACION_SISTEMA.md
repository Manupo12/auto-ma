# VERIFICACIÓN SISTEMA RILO SAS — Checklist Completo

**Fecha última verificación:** _______________  
**Verificado por:** _______________  
**Entorno:** ☐ Docker (dev)  ☐ WSL Sandra (producción)  
**Versión backend:** _______________  
**Versión dashboard:** _______________  

---

> **Cómo usar este checklist:**
> - Marca ☑ cuando el ítem pase. Marca ✗ cuando falle (anota el error en el campo "Obs.").
> - Los ítems marcados con 🔴 son BLOQUEANTES — no continuar sin resolverlos.
> - Los marcados con 🟡 son importantes pero no bloquean el flujo básico.
> - Los marcados con 🟢 son mejoras/opcionales.
> - Ejecuta las pruebas **en orden**; algunas dependen de las anteriores.

---

## BLOQUE 0 — PRE-REQUISITOS DEL SISTEMA

### 0.1 Dependencias del sistema operativo

- [ ] **Python 3.11+** instalado  
  ```bash
  python3 --version  # debe ser 3.11.x o superior
  ```
  Resultado esperado: `Python 3.11.x`  
  Obs.: _______________

- [ ] **ffmpeg** instalado  
  ```bash
  ffmpeg -version  # debe mostrar versión
  ```
  Resultado esperado: `ffmpeg version 6.x` o superior  
  Obs.: _______________

- [ ] **LibreOffice** instalado (para conversión DOCX→PDF)  
  ```bash
  libreoffice --version
  ```
  Resultado esperado: `LibreOffice 7.x`  
  Obs.: _______________

- [ ] **Node.js 20+** instalado  
  ```bash
  node --version  # debe ser v20.x o superior
  ```
  Obs.: _______________

- [ ] **PM2** instalado globalmente  
  ```bash
  pm2 --version
  ```
  Obs.: _______________

- [ ] **Playwright** y navegadores instalados  
  ```bash
  python3 -c "from playwright.sync_api import sync_playwright; print('OK')"
  ```
  Obs.: _______________

- [ ] **git** instalado y repo clonado  
  ```bash
  git -C ~/rilo-backend log --oneline -1
  ```
  Obs.: _______________

### 0.2 Variables de entorno 🔴

- [ ] Archivo `.env` existe en `~/rilo-backend/`  
  ```bash
  ls -la ~/rilo-backend/.env
  ```
  Obs.: _______________

- [ ] 🔴 `OPENCODE_GO_API_KEY` definida y no vacía  
  ```bash
  grep OPENCODE_GO_API_KEY ~/rilo-backend/.env | grep -v "^#"
  ```
  Obs.: _______________

- [ ] 🔴 `DEEPGRAM_API_KEY` definida y no vacía  
  ```bash
  grep DEEPGRAM_API_KEY ~/rilo-backend/.env | grep -v "^#"
  ```
  Obs.: _______________

- [ ] 🟡 `TELEGRAM_BOT_TOKEN` definida  
  Obs.: _______________

- [ ] 🟡 `TELEGRAM_CHAT_ID` definida  
  Obs.: _______________

- [ ] 🟡 `GMAIL_USER` y `GMAIL_APP_PASSWORD` definidas  
  Obs.: _______________

- [ ] 🔴 `AUTH_PIN` cambiado del default `1234`  
  ```bash
  grep AUTH_PIN ~/rilo-backend/.env
  ```
  ⚠️ Si dice `1234`, CAMBIAR ANTES DE CONTINUAR  
  Obs.: _______________

- [ ] 🔴 `AUTH_SECRET` cambiado del default `cambiar-este-secret-en-prod`  
  ```bash
  grep AUTH_SECRET ~/rilo-backend/.env
  ```
  ⚠️ Si dice `cambiar-este-secret-en-prod`, CAMBIAR ANTES DE CONTINUAR  
  Obs.: _______________

- [ ] `WORKFLOW_DB_PATH` definida o default `./storage/workflow.db` existe  
  Obs.: _______________

- [ ] `DASHBOARD_URL` definida (para links en Telegram)  
  Obs.: _______________

- [ ] `LLM_MODEL_EXTRACCION` = `deepseek-v4-flash` (o definida)  
  Obs.: _______________

- [ ] `LLM_MODEL_SINTESIS` = `deepseek-v4-pro` (o definida)  
  Obs.: _______________

### 0.3 Estructura de directorios

- [ ] `storage/docs/` existe y tiene permisos de escritura  
  ```bash
  ls ~/rilo-backend/storage/docs/ | wc -l
  ```
  Obs.: _______________

- [ ] `storage/pdfs/` existe  
  Obs.: _______________

- [ ] `storage/data/` existe y tiene los JSON de pacientes  
  ```bash
  ls ~/rilo-backend/storage/data/
  ```
  Resultado esperado: archivos `1193143688.json`, `55162801.json`  
  Obs.: _______________

- [ ] `storage/reports/` existe  
  Obs.: _______________

- [ ] `storage/workflow.db` existe (o se creará al primer inicio)  
  Obs.: _______________

- [ ] Workspace de Sandra accesible  
  ```bash
  ls "/mnt/c/Users/Sandra/Desktop/SANDRA/ACTIVIDADES OCUPACIONALES" | head -5
  ```
  Obs.: _______________

---

## BLOQUE 1 — ARRANQUE DEL BACKEND

### 1.1 Inicio del servidor FastAPI

- [ ] 🔴 Backend arranca sin errores  
  ```bash
  cd ~/rilo-backend && python3 -m uvicorn backend.server:app --host 0.0.0.0 --port 8000 2>&1 | head -30
  ```
  Resultado esperado: `Application startup complete.`  
  Obs.: _______________

- [ ] 🔴 Puerto 8000 accesible  
  ```bash
  curl -s http://localhost:8000/ | python3 -m json.tool
  ```
  Resultado esperado: JSON con `{"status": "ok", ...}` o similar  
  Obs.: _______________

- [ ] Sin errores `ImportError` en el log de arranque  
  Obs.: _______________

- [ ] Sin errores de conexión a SQLite en el log  
  Obs.: _______________

- [ ] Scheduler de cron se inicializa (si `FASE_A_CRON_ENABLED=true`)  
  ```bash
  grep "SCHEDULER" /tmp/rilo_server.log | tail -3
  ```
  Obs.: _______________

### 1.2 Modo PM2 (producción)

- [ ] 🟡 Backend registrado en PM2  
  ```bash
  pm2 list | grep rilo
  ```
  Resultado esperado: estado `online`  
  Obs.: _______________

- [ ] Dashboard Next.js registrado en PM2  
  ```bash
  pm2 list | grep dashboard
  ```
  Resultado esperado: estado `online`  
  Obs.: _______________

- [ ] PM2 arranca automáticamente al reiniciar PC  
  ```bash
  pm2 startup  # verifica que esté configurado
  ```
  Obs.: _______________

- [ ] Logs de PM2 accesibles  
  ```bash
  pm2 logs rilo-backend --lines 20 --nostream
  ```
  Obs.: _______________

---

## BLOQUE 2 — ENDPOINTS DE HEALTH Y STATUS

### 2.1 Health checks básicos

- [ ] 🔴 `GET /` — root del backend  
  ```bash
  curl -s http://localhost:8000/ | python3 -m json.tool
  ```
  Obs.: _______________

- [ ] 🔴 `GET /api/portales/health` — salud de portales  
  ```bash
  curl -s http://localhost:8000/api/portales/health | python3 -m json.tool
  ```
  Resultado esperado: JSON con estado de Medifolios y Positiva  
  Obs.: _______________

- [ ] 🟡 `GET /api/stats` — estadísticas generales  
  ```bash
  curl -s http://localhost:8000/api/stats | python3 -m json.tool
  ```
  Resultado esperado: `num_pacientes`, `num_formatos`, `backup_fecha`  
  Obs.: _______________

### 2.2 Endpoints de pacientes

- [ ] 🔴 `GET /api/pacientes` — lista todos los pacientes  
  ```bash
  curl -s http://localhost:8000/api/pacientes | python3 -m json.tool
  ```
  Resultado esperado: lista con Juan Carlos Duran y Rosa Maria Garcia  
  Obs.: _______________

- [ ] 🔴 `GET /api/pacientes/1193143688` — datos de Juan Carlos  
  ```bash
  curl -s http://localhost:8000/api/pacientes/1193143688 | python3 -m json.tool
  ```
  Resultado esperado: datos completos del paciente  
  Obs.: _______________

- [ ] `GET /api/pacientes/55162801` — datos de Rosa Maria  
  Obs.: _______________

- [ ] `GET /api/pacientes/99999999` — paciente inexistente  
  Resultado esperado: HTTP 404 con mensaje claro  
  Obs.: _______________

### 2.3 Endpoints de agenda

- [ ] 🟡 `GET /api/agenda` — agenda del día  
  ```bash
  curl -s http://localhost:8000/api/agenda | python3 -m json.tool
  ```
  Resultado esperado: `{"citas": [...]}` (puede estar vacía)  
  Obs.: _______________

- [ ] Citas en agenda tienen campo `cc` cuando está disponible  
  Obs.: _______________

### 2.4 Endpoints de archivos

- [ ] 🟡 `GET /api/archivos` — lista de archivos en storage  
  ```bash
  curl -s http://localhost:8000/api/archivos | python3 -m json.tool
  ```
  Resultado esperado: lista de DOCX y PDFs  
  ⚠️ Verificar que NO usa rglob en /mnt/c/ (debe responder en <3s)  
  Tiempo de respuesta: _______________  
  Obs.: _______________

- [ ] `GET /api/archivos` responde en menos de 3 segundos  
  ```bash
  time curl -s http://localhost:8000/api/archivos > /dev/null
  ```
  Obs.: _______________

### 2.5 Endpoints de tareas (workflow)

- [ ] `GET /api/tasks/activas` — tareas en curso  
  ```bash
  curl -s http://localhost:8000/api/tasks/activas | python3 -m json.tool
  ```
  Resultado esperado: `{"tasks": []}` (vacío al inicio)  
  Obs.: _______________

- [ ] `GET /api/tasks/paciente/1193143688` — tareas del paciente  
  ```bash
  curl -s http://localhost:8000/api/tasks/paciente/1193143688 | python3 -m json.tool
  ```
  Obs.: _______________

### 2.6 Endpoints de costos

- [ ] 🟢 `GET /api/costos?dias=7` — costos LLM últimos 7 días  
  ```bash
  curl -s "http://localhost:8000/api/costos?dias=7" | python3 -m json.tool
  ```
  Resultado esperado: JSON con tokens_total, costo_usd  
  Obs.: _______________

---

## BLOQUE 3 — CHAT CON TOMY (LLM)

### 3.1 Conexión LLM básica

- [ ] 🔴 `POST /api/chat` — pregunta simple  
  ```bash
  curl -s -X POST http://localhost:8000/api/chat \
    -H "Content-Type: application/json" \
    -d '{"mensaje": "hola, cuantos pacientes hay?"}' | python3 -m json.tool
  ```
  Resultado esperado: respuesta coherente de Tomy (puede tardar 30-120s con DeepSeek)  
  Tiempo de respuesta: _______________  
  Obs.: _______________

- [ ] 🔴 La respuesta NO es un error HTTP 500  
  Obs.: _______________

- [ ] 🔴 La respuesta NO está vacía (`respuesta: ""`)  
  Obs.: _______________

- [ ] La respuesta menciona los pacientes del sistema  
  Obs.: _______________

### 3.2 Preguntas clínicas

- [ ] Tomy responde a pregunta sobre un paciente específico  
  ```bash
  curl -s -X POST http://localhost:8000/api/chat \
    -H "Content-Type: application/json" \
    -d '{"mensaje": "que formatos tiene Juan Carlos Duran?", "paciente_cc": "1193143688"}' \
    | python3 -m json.tool
  ```
  Obs.: _______________

- [ ] 🟡 Tomy responde de manera diferente a preguntas simples vs. consultas complejas  
  Pregunta simple: `"que dia es hoy?"` → respuesta corta sin secciones  
  Obs.: _______________

- [ ] Tomy responde en español colombiano  
  Obs.: _______________

### 3.3 Contexto del workspace

- [ ] Tomy puede ver documentos del workspace de Sandra  
  ```bash
  curl -s -X POST http://localhost:8000/api/chat \
    -H "Content-Type: application/json" \
    -d '{"mensaje": "que documentos hay en el workspace?"}' | python3 -m json.tool
  ```
  Obs.: _______________

### 3.4 Reintentos y resiliencia

- [ ] 🟡 Si el LLM da error, Tomy reintenta (ver logs `/tmp/rilo_server.log`)  
  Obs.: _______________

- [ ] El timeout del chat no supera 5 minutos (300s)  
  Obs.: _______________

---

## BLOQUE 4 — TRANSCRIPCIÓN DE AUDIO (DEEPGRAM)

### 4.1 Upload de audio básico

- [ ] 🔴 `POST /api/upload-audio` — archivo de prueba  
  ```bash
  # Crear audio de prueba de 5 segundos
  ffmpeg -f lavfi -i "sine=frequency=440:duration=5" -ar 44100 /tmp/test_audio.mp3 -y 2>/dev/null
  curl -s -X POST http://localhost:8000/api/upload-audio \
    -F "audio=@/tmp/test_audio.mp3" \
    -F "paciente_cc=1193143688" | python3 -m json.tool
  ```
  Resultado esperado: `{"task_id": "...", "estado": "iniciado"}`  
  Obs.: _______________

- [ ] 🟡 Upload de archivo M4A (formato iPhone)  
  ```bash
  ffmpeg -f lavfi -i "sine=frequency=440:duration=5" /tmp/test_audio.m4a -y 2>/dev/null
  curl -s -X POST http://localhost:8000/api/upload-audio \
    -F "audio=@/tmp/test_audio.m4a" \
    -F "paciente_cc=1193143688" | python3 -m json.tool
  ```
  Obs.: _______________

- [ ] Archivo rechazado si no es audio (e.g., .pdf)  
  ```bash
  curl -s -X POST http://localhost:8000/api/upload-audio \
    -F "audio=@/tmp/test.pdf" \
    -F "paciente_cc=1193143688" | python3 -m json.tool
  ```
  Resultado esperado: error `400` o `422` con mensaje claro  
  Obs.: _______________

### 4.2 Transcripción real (requiere Deepgram key válida)

- [ ] 🔴 Deepgram API key válida — verificar con audio real de 10s  
  ```bash
  # Necesitas un archivo real de voz en /tmp/voz_prueba.mp3
  curl -s -X POST "https://api.deepgram.com/v1/listen?model=nova-2&language=es" \
    -H "Authorization: Token $DEEPGRAM_API_KEY" \
    -H "Content-Type: audio/mp3" \
    --data-binary @/tmp/voz_prueba.mp3 | python3 -m json.tool | head -20
  ```
  Resultado esperado: `{"results": {"channels": [...], "utterances": [...]}}`  
  Obs.: _______________

- [ ] 🟡 Transcripción incluye diarización (identificación de hablantes)  
  Obs.: _______________

- [ ] 🟡 Audio largo (>25 min) se divide en chunks automáticamente  
  Obs.: _______________

---

## BLOQUE 5 — FLUJO DE TRABAJO COMPLETO (9 PASOS)

### 5.0 Pre-condiciones

- [ ] `TOMY_COMPLETO_ENABLED=true` en `.env` (o verificar modo manual)  
  ```bash
  grep TOMY_COMPLETO_ENABLED ~/rilo-backend/.env
  ```
  Obs.: _______________

- [ ] Paciente `1193143688` tiene datos en `storage/data/`  
  Obs.: _______________

### 5.1 Paso 1 — Transcripción

- [ ] El paso `transcribir` se ejecuta al iniciar workflow  
  ```bash
  # Después de subir audio, consultar estado:
  TASK_ID="<task_id_del_upload_anterior>"
  curl -s "http://localhost:8000/api/tasks/$TASK_ID" | python3 -m json.tool
  ```
  Resultado esperado: `"paso_actual": 1` o `"paso_actual": 2`  
  Obs.: _______________

### 5.2 Paso 2 — Resolver paciente

- [ ] El paso `resolver_paciente` encuentra datos del paciente  
  Verificar en log: `grep "resolver_paciente" /tmp/rilo_server.log`  
  Obs.: _______________

- [ ] 🟡 Si paciente no está en JSON, extrae datos de portales  
  Obs.: _______________

### 5.3 Paso 3 — Leer notas crudas

- [ ] El paso `leer_notas_crudas` escanea workspace de Sandra  
  Verificar: grep en log por `leer_notas_crudas`  
  Obs.: _______________

- [ ] Escaneo del workspace tarda <5 segundos (no usa rglob)  
  Obs.: _______________

### 5.4 Paso 4 — Leer formatos subidos

- [ ] El paso `leer_formatos_subidos` lee DOCX de referencia  
  Obs.: _______________

### 5.5 Paso 5 — Síntesis maestra (LLM)

- [ ] 🔴 El paso `sintetizar_maestro` llama a DeepSeek v4 Pro  
  Verificar en log: `grep "sintetizar" /tmp/rilo_server.log`  
  Obs.: _______________

- [ ] 🔴 La síntesis produce JSON con datos del paciente  
  Obs.: _______________

- [ ] 🟡 Si contexto >30K chars, se resume automáticamente  
  Obs.: _______________

- [ ] `lote_worker.py` se ejecuta como subprocess separado (no OOM)  
  ```bash
  ps aux | grep lote_worker
  ```
  Obs.: _______________

### 5.6 Paso 6 — Generar formatos

- [ ] 🔴 El paso `generar_formatos` produce archivos DOCX  
  ```bash
  ls -lt ~/rilo-backend/storage/docs/ | head -10
  ```
  Resultado esperado: archivos DOCX recientes  
  Obs.: _______________

- [ ] Se generan los 7 formatos (o los aplicables al caso)  
  Obs.: _______________

### 5.7 Paso 7 — QA de formatos

- [ ] 🔴 El paso `qa_formatos` verifica los documentos generados  
  Verificar en log: `grep "qa_formatos" /tmp/rilo_server.log`  
  Obs.: _______________

- [ ] 🔴 QA NO dice siempre `qa_ok=True` sin verificar (bug NC-1)  
  Verificar que el script QA inline está implementado, no depende de `skills/`  
  Obs.: _______________

- [ ] Los documentos sin placeholders `[VERIFICAR]` pasan QA  
  Obs.: _______________

- [ ] Los documentos CON placeholders `[VERIFICAR]` generan warnings  
  Obs.: _______________

### 5.8 Paso 8 — Convertir PDF

- [ ] 🟡 El paso `convertir_pdf` genera PDF/A con LibreOffice  
  ```bash
  ls ~/rilo-backend/storage/pdfs/ | tail -5
  ```
  Resultado esperado: archivos PDF recientes  
  Obs.: _______________

- [ ] El PDF generado se puede abrir correctamente  
  Obs.: _______________

### 5.9 Paso 9 — Notificar listo

- [ ] 🟡 El paso `notificar_listo` envía mensaje Telegram a Sandra  
  Obs.: _______________

- [ ] El mensaje de Telegram incluye link al dashboard  
  Obs.: _______________

### 5.10 Estado final del workflow

- [ ] 🔴 Task finaliza con estado `completado` (no queda en `procesando`)  
  ```bash
  curl -s "http://localhost:8000/api/tasks/$TASK_ID" | python3 -m json.tool | grep estado
  ```
  Obs.: _______________

- [ ] `formatos_generados` en la task contiene lista de archivos  
  Obs.: _______________

- [ ] Workflow completo tarda entre 10-20 minutos (para audio de 10 min)  
  Tiempo real: _______________  
  Obs.: _______________

---

## BLOQUE 6 — GENERACIÓN DE LOS 7 FORMATOS

### 6.1 Verificar cada formato individualmente

- [ ] 🔴 **Formato 1 — Análisis de Exigencias** se genera  
  ```bash
  ls ~/rilo-backend/storage/docs/ | grep -i "exigencias"
  ```
  Obs.: _______________

- [ ] 🔴 **Formato 2 — Carta de Medidas Preventivas** se genera  
  ```bash
  ls ~/rilo-backend/storage/docs/ | grep -i "preventivas\|medidas"
  ```
  Obs.: _______________

- [ ] 🔴 **Formato 3 — Carta de Recomendaciones** se genera  
  ```bash
  ls ~/rilo-backend/storage/docs/ | grep -i "recomendaciones"
  ```
  Obs.: _______________

- [ ] 🔴 **Formato 4 — Cierre de Caso** se genera  
  ```bash
  ls ~/rilo-backend/storage/docs/ | grep -i "cierre"
  ```
  Obs.: _______________

- [ ] 🟡 **Formato 5 — Citación a Empresas** se genera  
  ```bash
  ls ~/rilo-backend/storage/docs/ | grep -i "citacion\|citación"
  ```
  Obs.: _______________

- [ ] 🟡 **Formato 6 — Prueba de Trabajo** se genera  
  ```bash
  ls ~/rilo-backend/storage/docs/ | grep -i "prueba"
  ```
  Obs.: _______________

- [ ] 🟡 **Formato 7 — VOI (Valoración Desempeño Ocupacional)** se genera  
  ```bash
  ls ~/rilo-backend/storage/docs/ | grep -i "voi\|valoracion\|valoración"
  ```
  Obs.: _______________

### 6.2 Calidad de los documentos

- [ ] Los DOCX se pueden abrir en Microsoft Word / LibreOffice  
  Obs.: _______________

- [ ] Los datos del paciente (nombre, CC, siniestro) aparecen correctos  
  Obs.: _______________

- [ ] No hay placeholders `[NOMBRE]`, `[CC]`, `[FECHA]` sin reemplazar  
  ```bash
  python3 -c "
  from docx import Document
  import os, glob
  for f in glob.glob(os.path.expanduser('~/rilo-backend/storage/docs/*.docx')):
      doc = Document(f)
      text = ' '.join(p.text for p in doc.paragraphs)
      if '[NOMBRE]' in text or '[CC]' in text:
          print(f'PLACEHOLDER en: {os.path.basename(f)}')
  print('Verificación completa')
  "
  ```
  Obs.: _______________

- [ ] Tablas del documento tienen datos (no filas completamente vacías)  
  Obs.: _______________

- [ ] 🟡 Firma de Sandra aparece en los documentos (si `firma_sandra.png` existe)  
  ```bash
  ls ~/rilo-backend/storage/firma_sandra.png 2>/dev/null && echo "EXISTE" || echo "NO EXISTE"
  ```
  Obs.: _______________

### 6.3 Validación JSON

- [ ] `json_validator.py` valida los datos antes de generar  
  Obs.: _______________

- [ ] Los campos requeridos están presentes o marcados `[VERIFICAR]`  
  Obs.: _______________

- [ ] La CC no tiene apóstrofes ni puntos (ej: 12'130.558 → 12130558)  
  Obs.: _______________

---

## BLOQUE 7 — EXTRACCIÓN DE PORTALES

### 7.1 Portal Medifolios

- [ ] 🟡 Conexión al portal Medifolios  
  ```bash
  curl -s -o /dev/null -w "%{http_code}" "https://server0medifolios.net" 2>/dev/null
  ```
  Resultado esperado: código 200 o 302  
  Obs.: _______________

- [ ] 🟡 Login en Medifolios funciona con credenciales guardadas  
  Credenciales: `55162801-2` / `55162801-2`  
  Obs.: _______________

- [ ] 🟡 Extracción de datos del paciente Rosa Maria (CC 55162801) desde Medifolios  
  ```bash
  curl -s -X POST http://localhost:8000/api/portales/medifolios/extraer \
    -H "Content-Type: application/json" \
    -d '{"cc": "55162801"}' | python3 -m json.tool
  ```
  Obs.: _______________

- [ ] 🟡 Las 18 secciones de Medifolios se extraen correctamente  
  Obs.: _______________

### 7.2 Portal ARL Positiva

- [ ] 🟡 Conexión al portal ARL Positiva  
  ```bash
  curl -s -o /dev/null -w "%{http_code}" "https://positivacuida.positiva.gov.co" 2>/dev/null
  ```
  Obs.: _______________

- [ ] 🟡 Login en ARL Positiva funciona  
  Credenciales: `1075209386MR` / `Rilo2026*`  
  Obs.: _______________

- [ ] 🟡 Extracción de siniestro OFICIAL de Juan Carlos Duran (1193143688)  
  Resultado esperado: siniestro `503463870`  
  Obs.: _______________

- [ ] 🟡 Las 9 pestañas de ARL Positiva (6 Consulta integral + Consultar caso RHI) se extraen  
  Obs.: _______________

- [ ] 🟡 Datos extraídos de portales coinciden con los guardados en JSON  
  Obs.: _______________

### 7.3 Modo degradado (portal caído)

- [ ] 🔴 Si Medifolios no responde, el sistema continúa con datos locales  
  Verificar en log: `modo_degradado`  
  Obs.: _______________

- [ ] Los campos de portal caído se marcan `[VERIFICAR]` (no vacíos, no error)  
  Obs.: _______________

- [ ] La cadena de custodia registra que el dato viene de modo degradado  
  Obs.: _______________

---

## BLOQUE 8 — SISTEMA DE NOTIFICACIONES

### 8.1 Telegram

- [ ] 🟡 El bot de Telegram está activo  
  ```bash
  curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe" | python3 -m json.tool | grep username
  ```
  Obs.: _______________

- [ ] 🟡 Se puede enviar mensaje de prueba  
  ```bash
  curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
    -H "Content-Type: application/json" \
    -d "{\"chat_id\": \"$TELEGRAM_CHAT_ID\", \"text\": \"Prueba RILO $(date)\"}" | python3 -m json.tool
  ```
  Resultado esperado: `"ok": true`  
  Obs.: _______________

- [ ] 🟡 Sandra recibe el mensaje en Telegram  
  Obs.: _______________

- [ ] 🟡 Los emojis y formato del mensaje son correctos  
  Obs.: _______________

### 8.2 Notificaciones de workflow

- [ ] 🟡 Al completar workflow, Sandra recibe mensaje con link al dashboard  
  Obs.: _______________

- [ ] 🟡 Si hay error en workflow, Sandra recibe mensaje de error  
  Obs.: _______________

---

## BLOQUE 9 — LECTURA DE AGENDA (GMAIL)

- [ ] 🟡 Conexión IMAP a Gmail funciona  
  ```bash
  python3 -c "
  import imaplib, os
  try:
      m = imaplib.IMAP4_SSL('imap.gmail.com')
      m.login(os.getenv('GMAIL_USER', ''), os.getenv('GMAIL_APP_PASSWORD', ''))
      m.logout()
      print('Gmail OK')
  except Exception as e:
      print(f'Error: {e}')
  "
  ```
  Obs.: _______________

- [ ] 🟡 `GET /api/agenda` devuelve citas de hoy cuando hay correos de Medifolios  
  Obs.: _______________

- [ ] 🟡 Las citas tienen: hora, paciente, servicio  
  Obs.: _______________

- [ ] 🟡 Las citas tienen CC del paciente (cuando se puede encontrar por nombre)  
  Obs.: _______________

---

## BLOQUE 10 — DASHBOARD (NEXT.JS)

### 10.1 Servidor del dashboard

- [ ] 🔴 Dashboard arranca en puerto 3000  
  ```bash
  curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
  ```
  Resultado esperado: `200`  
  Obs.: _______________

- [ ] 🔴 No hay errores de compilación TypeScript  
  ```bash
  cd ~/rilo-dashboard && npm run build 2>&1 | grep -E "error|Error" | head -10
  ```
  Obs.: _______________

### 10.2 Página "Mi Día" (`/hoy`)

- [ ] 🔴 La página `/hoy` carga sin error  
  ```bash
  curl -s http://localhost:3000/hoy | grep -i "error\|Error" | head -5
  ```
  Obs.: _______________

- [ ] La página muestra la agenda del día  
  Obs.: _______________

- [ ] Las tareas activas se muestran con estado legible  
  Resultado esperado: "Transcribiendo audio..." no "transcribiendo" raw  
  Obs.: _______________

- [ ] Los links de citas con CC llevan a `/paciente/[cc]`  
  Obs.: _______________

- [ ] 🟡 El estado de las tareas se actualiza automáticamente  
  Obs.: _______________

### 10.3 Página "Pacientes" (`/pacientes`)

- [ ] 🔴 La página `/pacientes` carga sin error  
  Obs.: _______________

- [ ] La lista de pacientes aparece (Juan Carlos, Rosa Maria)  
  Obs.: _______________

- [ ] 🔴 No hay errores de `import from "@/lib/hermes"` después del rename a `api.ts`  
  Obs.: _______________

- [ ] Clicking en un paciente lleva a su vista 360  
  Obs.: _______________

### 10.4 Vista 360 del paciente (`/paciente/[cc]`)

- [ ] 🔴 La página `/paciente/1193143688` carga sin error  
  Obs.: _______________

- [ ] Muestra datos del paciente (nombre, CC, siniestro, empresa)  
  Obs.: _______________

- [ ] Muestra los formatos generados para el paciente  
  Obs.: _______________

- [ ] Se puede descargar un formato DOCX desde esta página  
  Obs.: _______________

- [ ] Se puede descargar un PDF desde esta página  
  Obs.: _______________

- [ ] 🟡 El campo de corrección funciona (envía mensaje y lo procesa)  
  Obs.: _______________

- [ ] 🔴 La corrección no usa `alert()` (debe ser toast/modal no bloqueante)  
  Obs.: _______________

### 10.5 Página "Documentos" (`/formatos`)

- [ ] La página `/formatos` carga sin error  
  Obs.: _______________

- [ ] Lista todos los documentos generados  
  Obs.: _______________

- [ ] Se puede filtrar por paciente o tipo de formato  
  Obs.: _______________

### 10.6 Página "Subir Audio" (`/subir-audio`)

- [ ] 🔴 La página `/subir-audio` carga sin error  
  Obs.: _______________

- [ ] Se puede seleccionar un archivo de audio  
  Obs.: _______________

- [ ] Se puede ingresar la CC del paciente  
  Obs.: _______________

- [ ] 🟡 Solo acepta archivos de audio (MP3, M4A, WAV, MP4, OGG)  
  Obs.: _______________

- [ ] 🟡 Muestra barra de progreso durante el upload  
  Obs.: _______________

- [ ] Después del upload, redirige o muestra confirmación  
  Obs.: _______________

### 10.7 Página "Chat con Tomy" (`/chat`)

- [ ] 🔴 La página `/chat` carga sin error  
  Obs.: _______________

- [ ] Se puede escribir un mensaje y enviarlo  
  Obs.: _______________

- [ ] 🔴 La respuesta de Tomy aparece (puede tardar 30-120s)  
  Obs.: _______________

- [ ] 🟡 Los mensajes anteriores se guardan al recargar la página  
  Obs.: _______________

- [ ] 🟡 El Markdown en las respuestas de Tomy se renderiza correctamente  
  Obs.: _______________

### 10.8 Página "Mis Archivos" (`/archivos`)

- [ ] La página `/archivos` carga sin error  
  Obs.: _______________

- [ ] Muestra los archivos en `storage/docs/` y `storage/pdfs/`  
  Obs.: _______________

- [ ] Se puede descargar un archivo desde esta página  
  Obs.: _______________

### 10.9 Variable de entorno de API (NC-7)

- [ ] 🔴 El dashboard usa `NEXT_PUBLIC_API_URL` (no `localhost:8000` hardcodeado)  
  ```bash
  grep -r "localhost:8000" ~/rilo-dashboard/app/ ~/rilo-dashboard/lib/ | grep -v ".next"
  ```
  Resultado esperado: 0 resultados (o solo en archivos de config con env var)  
  Obs.: _______________

- [ ] `NEXT_PUBLIC_API_URL` apunta al servidor correcto en producción  
  Obs.: _______________

---

## BLOQUE 11 — AUTENTICACIÓN Y SEGURIDAD

### 11.1 Login con PIN

- [ ] 🔴 `POST /api/auth/login` con PIN correcto devuelve token  
  ```bash
  curl -s -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"pin": "'"$(grep AUTH_PIN ~/rilo-backend/.env | cut -d= -f2)"'"}' \
    | python3 -m json.tool
  ```
  Resultado esperado: `{"ok": true, "token": "..."}`  
  Obs.: _______________

- [ ] `POST /api/auth/login` con PIN incorrecto devuelve 401  
  ```bash
  curl -s -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"pin": "0000"}' | python3 -m json.tool
  ```
  Resultado esperado: HTTP 401  
  Obs.: _______________

- [ ] 🔴 La página de login existe en el dashboard (`/login`)  
  ```bash
  curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/login
  ```
  Resultado esperado: 200  
  Obs.: _______________

- [ ] 🔴 El middleware del dashboard protege las rutas (redirige a `/login` sin auth)  
  ```bash
  curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/hoy
  ```
  Sin cookie de auth, resultado esperado: 302 redirect a /login  
  Obs.: _______________

### 11.2 CORS

- [ ] 🟡 CORS en el backend viene de variable de entorno (no hardcodeado)  
  ```bash
  grep -n "allow_origins" ~/rilo-backend/backend/server.py
  ```
  Resultado esperado: usa `os.getenv("CORS_ORIGINS")` o lista configurable  
  Obs.: _______________

---

## BLOQUE 12 — SISTEMA DE BACKUP

### 12.1 Backup diario

- [ ] 🔴 `backup_diario.py` existe y tiene el endpoint configurado  
  ```bash
  python3 -c "from backend.backup_diario import ejecutar_backup; print('OK')"
  ```
  Obs.: _______________

- [ ] 🔴 El backup genera un archivo tar.gz  
  ```bash
  python3 -c "
  import asyncio
  import sys
  sys.path.insert(0, '/root/fisioterapia')
  from backend.backup_diario import ejecutar_backup
  asyncio.run(ejecutar_backup())
  "
  ls -lh /tmp/rilo_backup_*.tar.gz 2>/dev/null || ls -lh ~/rilo-backend/storage/backups/ 2>/dev/null
  ```
  Obs.: _______________

- [ ] 🔴 El archivo tar.gz se envía a Telegram (no solo el texto del log)  
  Verificar que `enviar_backup_telegram()` usa `sendDocument`, no solo `sendMessage`  
  Obs.: _______________

- [ ] El backup NO incluye archivos de audio (tamaño razonable <50MB)  
  Obs.: _______________

- [ ] El backup incluye `storage/docs/`, `storage/pdfs/`, `storage/data/`  
  Obs.: _______________

### 12.2 Cron de backup

- [ ] 🟡 El cron de backup está registrado en el mismo scheduler que los otros crons  
  Verificar que usa la instancia de `cron_pre_extraccion.py`, no un scheduler separado  
  Obs.: _______________

- [ ] El cron de backup está programado para las 23:00 COL  
  Obs.: _______________

### 12.3 Verificación mensual de backup

- [ ] 🟡 `verificar_backup.py` está registrado en el cron (día 1, 3 AM)  
  ```bash
  grep -r "verificar_backup\|75bd86a3" ~/rilo-backend/backend/ | head -5
  ```
  Obs.: _______________

---

## BLOQUE 13 — CRON JOBS

### 13.1 Cron agenda (8:30 PM COL)

- [ ] 🟡 Cron de agenda mañana existe en el scheduler  
  ```bash
  grep "cdc1f6a5\|agenda_manana\|agenda mañana" ~/rilo-backend/backend/*.py | head -5
  ```
  Obs.: _______________

- [ ] 🟡 El cron de agenda recupera citas del día siguiente  
  Obs.: _______________

### 13.2 Cron recordatorios (1h antes de cita)

- [ ] 🟡 Cron de recordatorios existe  
  ```bash
  grep "1192d09e\|recordatorio" ~/rilo-backend/backend/*.py | head -5
  ```
  Obs.: _______________

- [ ] 🟡 El recordatorio se envía 1h antes de cada cita  
  Obs.: _______________

### 13.3 Feature flag de crons

- [ ] `FASE_A_CRON_ENABLED` en `.env` controla los crons  
  Obs.: _______________

- [ ] Cuando `FASE_A_CRON_ENABLED=false`, los crons NO se ejecutan  
  ```bash
  grep "CRON" /tmp/rilo_server.log | head -3
  ```
  Resultado esperado: `SCHEDULER: desactivado`  
  Obs.: _______________

---

## BLOQUE 14 — CORRECCIÓN DE DOCUMENTOS

### 14.1 Corrección por chat

- [ ] 🟡 `POST /api/corregir-paciente/{cc}` acepta instrucción de corrección  
  ```bash
  curl -s -X POST http://localhost:8000/api/corregir-paciente/1193143688 \
    -H "Content-Type: application/json" \
    -d '{"mensaje": "cambia el cargo de Juan Carlos a Auxiliar de Bodega"}' \
    | python3 -m json.tool
  ```
  Resultado esperado: `{"ok": true, "campo_corregido": "cargo"}`  
  Obs.: _______________

- [ ] 🟡 La corrección actualiza el JSON del paciente  
  Obs.: _______________

- [ ] 🟡 La corrección regenera los formatos afectados  
  Obs.: _______________

- [ ] 🟡 El modelo `deepseek-v4-flash` se usa para clasificar el campo (rápido)  
  Verificar en log: `grep "flash\|extraccion" /tmp/rilo_server.log | tail -5`  
  Obs.: _______________

---

## BLOQUE 15 — CADENA DE CUSTODIA

- [ ] 🟡 `custody.py` registra de dónde viene cada dato (Medifolios, Positiva, audio, manual)  
  Obs.: _______________

- [ ] 🟡 Los datos de Positiva tienen mayor confianza que los de audio  
  Verificar lógica de `ConfianzaCampo`  
  Obs.: _______________

- [ ] 🟡 `huellas_portales.json` se actualiza después de cada extracción  
  ```bash
  ls -la ~/rilo-backend/storage/huellas_portales.json
  ```
  Obs.: _______________

- [ ] 🟡 Los datos contradictorios entre portales se registran (no se silencian)  
  Obs.: _______________

---

## BLOQUE 16 — MANEJO DE TAREAS BACKGROUND (NC-8)

- [ ] 🔴 Las tareas de workflow NO usan `threading.Thread(daemon=True)`  
  ```bash
  grep -n "daemon=True\|threading.Thread" ~/rilo-backend/backend/workflow_runner.py
  ```
  Resultado esperado: 0 resultados (o usa BackgroundTasks/run_in_executor)  
  Obs.: _______________

- [ ] 🔴 Al reiniciar el backend, las tareas que estaban en `procesando` se marcan `zombie`/`error`  
  Verificar que hay lógica de zombie cleanup en el startup  
  Obs.: _______________

- [ ] Las tareas completadas siguen accesibles después de reiniciar el backend  
  Obs.: _______________

---

## BLOQUE 17 — SELECTOR DE FORMATOS

- [ ] 🟡 `format_selector.py` detecta el estado del caso correctamente  
  ```bash
  python3 -c "
  import sys; sys.path.insert(0, '/root/fisioterapia')
  from backend.format_selector import seleccionar_formatos
  # Caso nuevo: solo datos básicos sin historial
  formatos = seleccionar_formatos({'tiene_historial': False, 'estado': 'NUEVO'})
  print('NUEVO:', formatos)
  "
  ```
  Obs.: _______________

- [ ] Estado `NUEVO` → 3 formatos básicos (Análisis, Carta Preventivas, VOI)  
  Obs.: _______________

- [ ] Estado `SEGUIMIENTO` → 3 formatos de seguimiento  
  Obs.: _______________

- [ ] Estado `CIERRE` → 3 formatos de cierre (incluye Cierre de Caso)  
  Obs.: _______________

- [ ] Estado `PRUEBA_TRABAJO` → incluye Prueba de Trabajo  
  Obs.: _______________

---

## BLOQUE 18 — CASOS DE BORDE Y RESILIENCIA

### 18.1 Datos incorrectos

- [ ] 🔴 CC con apóstrofes se limpia automáticamente (12'130.558 → 12130558)  
  ```bash
  python3 -c "
  cc_raw = \"12'130.558\"
  cc_clean = cc_raw.replace(\"'\", '').replace('.', '').replace(',', '')
  print(cc_clean)  # debe ser 12130558
  "
  ```
  Obs.: _______________

- [ ] Paciente con CC que no existe devuelve error claro (no crash)  
  ```bash
  curl -s http://localhost:8000/api/pacientes/00000000 | python3 -m json.tool
  ```
  Obs.: _______________

### 18.2 Recursos del sistema

- [ ] El proceso del backend no consume >1GB de RAM en operación normal  
  ```bash
  ps aux | grep uvicorn | awk '{print $6}' # RSS en KB
  ```
  Obs.: _______________

- [ ] Después de procesar un audio de 10 min, la RAM vuelve a niveles normales  
  Obs.: _______________

- [ ] El proceso `lote_worker` termina (no queda zombie) después de la síntesis  
  ```bash
  ps aux | grep lote_worker | grep -v grep
  ```
  Resultado esperado: sin procesos zombie  
  Obs.: _______________

### 18.3 Timeouts

- [ ] Si Deepgram no responde en 600s, la tarea falla con error claro  
  Obs.: _______________

- [ ] Si el LLM no responde, hay reintento con backoff exponencial  
  Obs.: _______________

- [ ] Si el portal Medifolios tarda >120s, el sistema continúa en modo degradado  
  Obs.: _______________

### 18.4 Archivo inválido

- [ ] Si se sube un archivo de video (.mp4 de 500MB), el sistema lo rechaza antes de enviarlo a Deepgram  
  Obs.: _______________

- [ ] Si se sube un archivo .pdf como audio, se rechaza con mensaje claro  
  Obs.: _______________

### 18.5 Concurrencia

- [ ] 🟡 Dos audios subidos simultáneamente no interfieren entre sí  
  Obs.: _______________

- [ ] 🟡 Las lecturas de base de datos durante un write no bloquean el sistema (WAL mode)  
  Obs.: _______________

---

## BLOQUE 19 — NUEVAS FUNCIONALIDADES (PLAN DE EVOLUCIÓN)

### 19.1 Streaming de respuestas (EVO-1)

- [ ] 🟢 `GET /api/chat/stream` devuelve Server-Sent Events  
  ```bash
  curl -N -s "http://localhost:8000/api/chat/stream?mensaje=hola" | head -5
  ```
  Resultado esperado: líneas `data: {"token": "..."}` en tiempo real  
  Obs.: _______________

### 19.2 Autenticación completa

- [ ] 🔴 Página `/login` existe y funciona en el dashboard  
  Obs.: _______________

- [ ] 🔴 El middleware redirige a `/login` si no hay cookie de auth  
  Obs.: _______________

### 19.3 Tracking de costos (NC-18)

- [ ] 🟢 `GET /api/costos?dias=30` devuelve historial de 30 días  
  Obs.: _______________

- [ ] 🟢 Se envía alerta Telegram si el costo diario supera el umbral  
  Obs.: _______________

### 19.4 Paquete ARL completo (INT-3)

- [ ] 🟢 `GET /api/tasks/{task_id}/paquete-arl` genera ZIP con todos los documentos  
  Obs.: _______________

- [ ] 🟢 El ZIP incluye: carta de presentación, 7 formatos DOCX, resumen ejecutivo  
  Obs.: _______________

### 19.5 Entrevistador clínico (INT-2)

- [ ] 🟢 Si faltan campos críticos después de síntesis, el workflow se pausa y pregunta a Sandra  
  Obs.: _______________

- [ ] 🟢 `POST /api/tasks/{task_id}/responder-preguntas` reanuda el workflow  
  Obs.: _______________

### 19.6 Reporte mensual (BIZ-1)

- [ ] 🟢 El día 1 de cada mes se envía reporte con métricas del mes anterior  
  Obs.: _______________

### 19.7 Timeline del caso (INT-6)

- [ ] 🟢 `GET /api/pacientes/{cc}/timeline` devuelve cronología del caso  
  Obs.: _______________

### 19.8 Habeas Data / GDPR Colombia (LEGAL-1)

- [ ] 🟢 `GET /api/pacientes/{cc}/exportar-datos` devuelve todos los datos del paciente  
  Obs.: _______________

- [ ] 🟢 `DELETE /api/pacientes/{cc}/eliminar-datos` anonimiza los datos  
  Obs.: _______________

### 19.9 Circuit breaker (ARCH-2)

- [ ] 🟢 Después de 5 fallos consecutivos, el circuit breaker de Deepgram se abre  
  Obs.: _______________

- [ ] 🟢 Después de 30s, el circuit breaker pasa a HALF_OPEN y reintenta  
  Obs.: _______________

---

## BLOQUE 20 — SINCRONIZACIÓN Y DEPLOY

### 20.1 Flujo git

- [ ] 🔴 El repo GitHub (`Manupo12/auto-ma`) está actualizado con el código de producción  
  ```bash
  cd ~/rilo-backend && git log --oneline -5
  ```
  Obs.: _______________

- [ ] 🔴 El WSL de Sandra puede hacer `git pull` sin conflictos  
  ```bash
  cd ~/rilo-backend && git fetch && git status
  ```
  Resultado esperado: `Your branch is up to date`  
  Obs.: _______________

### 20.2 Después de un git pull en producción

- [ ] El backend se reinicia automáticamente con PM2  
  ```bash
  pm2 restart rilo-backend && sleep 5 && pm2 status
  ```
  Obs.: _______________

- [ ] El dashboard se reconstruye automáticamente (o PM2 hace restart)  
  Obs.: _______________

- [ ] Las migraciones de base de datos se aplican automáticamente (`alembic upgrade head`)  
  Obs.: _______________

### 20.3 Acceso externo (si nginx configurado)

- [ ] 🟢 nginx está activo y proxy-pasa a puerto 8000 y 3000  
  ```bash
  nginx -t && systemctl status nginx
  ```
  Obs.: _______________

- [ ] 🟢 HTTPS funciona con certificado válido  
  Obs.: _______________

- [ ] 🟢 Las peticiones de audio grandes (>50MB) no dan error 413  
  Obs.: _______________

---

## BLOQUE 21 — PRUEBA DE EXTREMO A EXTREMO (END-TO-END)

Este bloque simula el uso completo de una sesión de trabajo de Sandra.

**Preparación:**
- [ ] Backend corriendo en PM2  
- [ ] Dashboard accesible en el navegador  
- [ ] Sandra autenticada (PIN ingresado)  
- [ ] Audio de prueba de 10 minutos disponible (voz de fisioterapeuta + paciente)  
- [ ] Paciente con CC `1193143688` en el sistema  

**Secuencia:**

- [ ] **E2E-1:** Sandra abre el dashboard y ve la agenda de hoy  
  Obs.: _______________

- [ ] **E2E-2:** Sandra va a "Subir audio" y selecciona el audio de prueba  
  Obs.: _______________

- [ ] **E2E-3:** Sandra ingresa CC `1193143688` y pulsa "Subir"  
  Obs.: _______________

- [ ] **E2E-4:** El dashboard muestra confirmación del upload y el task_id  
  Obs.: _______________

- [ ] **E2E-5:** En "Mi Día" aparece la tarea en progreso (paso 1 → 9)  
  Obs.: _______________

- [ ] **E2E-6:** Después de ~15 minutos, Sandra recibe mensaje de Telegram: "Formatos listos"  
  Tiempo real de procesamiento: _______________  
  Obs.: _______________

- [ ] **E2E-7:** Sandra va a la vista del paciente y ve los formatos generados  
  Obs.: _______________

- [ ] **E2E-8:** Sandra descarga el Análisis de Exigencias y lo revisa  
  - Nombre del paciente: ✓/✗ _______________  
  - CC: ✓/✗ _______________  
  - Empresa: ✓/✗ _______________  
  - Diagnóstico: ✓/✗ _______________  
  - Sin placeholders: ✓/✗ _______________  

- [ ] **E2E-9:** Sandra escribe a Tomy: "Cambia el cargo a Operario de Planta"  
  Obs.: _______________

- [ ] **E2E-10:** El formato actualizado se regenera en <5 minutos  
  Obs.: _______________

- [ ] **E2E-11:** Sandra descarga el PDF del Cierre de Caso  
  Obs.: _______________

---

## BLOQUE 22 — LIMPIEZA DE HERMES (POST-MIGRACIÓN)

> Ejecutar solo cuando el sistema esté completamente validado con los tests anteriores.

- [ ] 🟡 Todos los imports de `hermes` en el dashboard han sido renombrados a `api` o `rilo`  
  ```bash
  grep -r "hermes" ~/rilo-dashboard/app/ ~/rilo-dashboard/lib/ ~/rilo-dashboard/components/ \
    | grep -v ".next" | grep -v "node_modules"
  ```
  Resultado esperado: 0 resultados  
  Obs.: _______________

- [ ] 🟡 `dashboard/lib/hermes.ts` ha sido renombrado a `dashboard/lib/api.ts`  
  Obs.: _______________

- [ ] 🟡 Variable `NEXT_PUBLIC_HERMES_API` ha sido renombrada a `NEXT_PUBLIC_API_URL`  
  Obs.: _______________

- [ ] 🟡 La skill `rilo-despliegue` no contiene referencias a Hermes en contextos visibles para Sandra  
  Obs.: _______________

- [ ] 🟡 Los logs del servidor dicen "[TOMY]" no "[HERMES]"  
  ```bash
  grep "HERMES" /tmp/rilo_server.log | wc -l
  ```
  Resultado esperado: 0  
  Obs.: _______________

---

## RESUMEN DE VERIFICACIÓN

| Bloque | Descripción | ✓ | ✗ | N/A |
|--------|-------------|---|---|-----|
| 0 | Pre-requisitos | | | |
| 1 | Arranque backend | | | |
| 2 | Endpoints health/status | | | |
| 3 | Chat Tomy (LLM) | | | |
| 4 | Transcripción audio | | | |
| 5 | Workflow 9 pasos | | | |
| 6 | 7 formatos DOCX | | | |
| 7 | Extracción portales | | | |
| 8 | Telegram | | | |
| 9 | Gmail agenda | | | |
| 10 | Dashboard | | | |
| 11 | Autenticación | | | |
| 12 | Backup | | | |
| 13 | Cron jobs | | | |
| 14 | Corrección documentos | | | |
| 15 | Cadena de custodia | | | |
| 16 | Background tasks | | | |
| 17 | Selector formatos | | | |
| 18 | Casos de borde | | | |
| 19 | Funciones nuevas | | | |
| 20 | Deploy y git | | | |
| 21 | End-to-end completo | | | |
| 22 | Limpieza Hermes | | | |

---

### Ítems BLOQUEANTES fallidos (deben resolverse antes de producción)

| # | Ítem | Error encontrado | Responsable | Resuelto |
|---|------|-----------------|-------------|---------|
| 1 | | | | ☐ |
| 2 | | | | ☐ |
| 3 | | | | ☐ |
| 4 | | | | ☐ |
| 5 | | | | ☐ |

---

### Notas adicionales / observaciones

```
_______________________________________________________________
_______________________________________________________________
_______________________________________________________________
_______________________________________________________________
```

---

**Firma del verificador:** _________________________  
**Fecha de aprobación para producción:** _______________  
**Versión aprobada (git commit):** _______________  
