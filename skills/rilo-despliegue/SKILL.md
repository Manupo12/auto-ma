---
name: rilo-despliegue
description: Despliegue y operaciones del sistema RILO SAS en el PC de Sandra — auto-arranque Windows/WSL, estructura de entornos (Docker dev / WSL prod), sincronización y mantenimiento.
---

# RILO Despliegue — Producción en PC de Sandra

## Arquitectura

```
┌─────────────────────┐     sync-to-wsl.sh     ┌──────────────────────┐
│   DOCKER (dev)      │ ──────────────────────→ │   WSL (producción)   │
│   Hermes/Tomy       │                         │   Sandra usa esto    │
│   /root/fisioterapia│ ←────────────────────── │   ~/rilo-backend/    │
│   Código fuente     │     git push/pull       │   ~/rilo-dashboard/  │
└─────────────────────┘                         └──────────────────────┘
                                                           │
                                                    GitHub (auto-ma)
                                                    fuente única verdad
```

- **Docker**: entorno de desarrollo, donde Hermes hace cambios
- **WSL**: entorno de producción, servicios accesibles desde Windows
- **GitHub**: fuente única de verdad, sincronización bidireccional

## Arranque rápido en Docker (desarrollo/testing)

Cuando necesitás probar backend+dashboard directamente dentro del contenedor Hermes (sin pasar por WSL):

```bash
# 1. Instalar dependencias Python (el contenedor NO las tiene pre-instaladas)
cd /root/fisioterapia && pip3 install -r backend/requirements.txt

# 2. Arrancar backend — ⚠️ NO usar terminal background=true (falla silenciosamente)
# Usar execute_code con subprocess.Popen:
python3 -c "
import subprocess, sys, os
os.chdir('/root/fisioterapia')
subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.server:app',
                  '--host', '0.0.0.0', '--port', '8000'])
"

# 3. Arrancar dashboard — Next.js 14 tarda 1-3 min en compilar en Docker
cd /root/fisioterapia/dashboard
# Si es primera vez o node_modules no existe:
npm install
# Arranque:
python3 -c "
import subprocess, os
os.chdir('/root/fisioterapia/dashboard')
subprocess.Popen(['npm', 'run', 'dev'])
"
# ⚠️ Esperar hasta que responda HTTP 200 (puede tardar >60s)
```

**Verificar que arrancaron:**
```bash
curl http://127.0.0.1:8000/api/health  # → {"ok":true}
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000  # → 200
```

## Setup inicial en PC nuevo

### 1. Copiar backend de Docker a WSL

```bash
sudo docker cp hermes-a34da917:/root/fisioterapia/backend ./rilo-backend
sudo chown -R $USER:$USER ~/rilo-backend
```

El contenedor puede cambiar de nombre. Para encontrarlo:
```bash
sudo docker ps --format '{{.Names}}' | grep hermes-
```

### 2. Estructura correcta del backend

Los imports usan `from backend.xxx`, por lo que los archivos deben estar en subcarpeta:

```bash
cd ~/rilo-backend
mkdir -p backend
mv *.py backend/
touch backend/__init__.py
```

### 3. Entorno virtual Python (OBLIGATORIO en Ubuntu 24.04+)

```bash
cd ~/rilo-backend
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

### 4. Dashboard (Next.js)

```bash
sudo docker cp hermes-a34da917:/root/fisioterapia/dashboard ./rilo-dashboard
sudo chown -R $USER:$USER ~/rilo-dashboard
cd ~/rilo-dashboard && npm install
```

### 5. Lanzar servicios manualmente

```bash
# Terminal 1 — API
cd ~/rilo-backend && source venv/bin/activate
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Dashboard
cd ~/rilo-dashboard && npm run dev
```

## Auto-arranque al encender PC

Crear archivo en carpeta Inicio de Windows (`shell:startup`):

**inicio-rilo.bat**:
```batch
@echo off
wsl -e bash -c "cd ~/rilo-dashboard && npm run dev & cd ~/rilo-backend && source venv/bin/activate && python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000"
```

## Carpeta de trabajo (workspace) de Sandra

La carpeta de producción de Sandra está en Windows:
```
C:\Users\Sandra\Desktop\SANDRA\ACTIVIDADES OCUPACIONALES
```

WSL la ve en `/mnt/c/Users/Sandra/Desktop/SANDRA/ACTIVIDADES OCUPACIONALES`.

### Configurar en WSL

```bash
# En .env del backend:
WORKSPACE_DIR=/mnt/c/Users/Sandra/Desktop/SANDRA/ACTIVIDADES OCUPACIONALES

# O enlazar:
ln -s "/mnt/c/Users/Sandra/Desktop/SANDRA/ACTIVIDADES OCUPACIONALES" ~/rilo-workspace
```

Esta carpeta es la que el dashboard muestra en la página "Archivos" (`/api/archivos`).

### Git en la carpeta de trabajo

Para que los archivos de Sandra estén versionados y Hermes pueda acceder:

```bash
cd "/mnt/c/Users/Sandra/Desktop/SANDRA/ACTIVIDADES OCUPACIONALES"
git init
git remote add origin https://github.com/Manupo12/auto-ma.git
# Usar una rama separada o un subdirectorio workspace/ en el repo principal
```

El endpoint `POST /api/archivos/sync` hace git pull + push automático.

## Chat con IA real (conectado al LLM de Hermes)

El chat del dashboard (`/api/chat` → `chat_handler.py`) ahora usa el LLM REAL (DeepSeek v4 vía OpenCode Go), la misma conciencia que Tomy en Telegram y CLI. Ya NO es un mock con if/else.

### Arquitectura del chat_handler

```
Sandra escribe en dashboard
        │
        ▼
POST /api/chat ──→ chat_handler.procesar_mensaje()
        │
        ├── 1. _buscar_archivo_mencionado(mensaje)
        │       Busca el .docx en el workspace (3 estrategias: nombre exacto, parcial, tipo formato)
        │
        ├── 2. _leer_documento_para_contexto(ruta)
        │       Lee párrafos, tablas, detecta encabezados, secciones vacías
        │
        ├── 3. _actualizar_contexto_workspace()
        │       Lista carpetas y archivos del workspace
        │
        └── 4. _llamar_llm(mensaje + contenido_archivo + workspace + historial)
                LLM responde CONOCIENDO el contenido real del documento
```

### SYSTEM_PROMPT maestro (200+ líneas)

El chat_handler tiene un SYSTEM_PROMPT de ~200 líneas que especializa a Tomy como EXPERTO ABSOLUTO en RILO SAS:
- Conoce los 7 formatos (estructura, campos, fuentes, qué llena Sandra, qué verifica él)
- Conoce el flujo completo (cita → audio → verificar → completar → revisar)
- Conoce el dashboard (6 páginas, menú, funciones)
- Conoce los portales y credenciales
- Conoce la carpeta de trabajo
- Tono: español colombiano, cálido, simple, cero jerga técnica
- Reglas: no inventar info clínica, confirmar contra portales, ejemplos de conversación

### Auto-detección de documentos en el chat (v4 — Mayo 2026)

**Contexto de workspace SIEMPRE presente.** Tomy ya NO espera a que Sandra mencione un archivo. En cada mensaje:

1. `_listar_workspace()` escanea la carpeta de trabajo (caché 5 min, sin rglob)
2. Inyecta la lista de archivos al LLM como parte del contexto del usuario
3. Si Sandra dice "revisa el documento de Juan", Tomy YA sabe cuál es

**Búsqueda específica de archivo** (cuando Sandra menciona uno):
| Sandra dice... | Tomy hace... |
|----------------|-------------|
| "arregla el formato de análisis" | Busca `analisis` en nombres de archivo |
| "completa el documento de Juan Pérez" | Busca `juan` y `perez` en stems |
| "mira la carta de recomendaciones" | Busca el .docx más reciente con `recomendaciones` |

3 estrategias de búsqueda en cascada:
1. **Coincidencia exacta**: nombre del archivo sin extensión aparece en el mensaje
2. **Coincidencia parcial**: ≥2 palabras del nombre del archivo aparecen en el mensaje
3. **Por tipo de formato**: detecta keyword de formato → busca el .docx más reciente que coincida

El contenido del .docx se inyecta al LLM (primeros 25 párrafos + 3 tablas), que ahora "ve" el documento real y responde con precisión quirúrgica.

### Persistencia de conversaciones (localStorage) 🆕

El chat del dashboard guarda automáticamente los mensajes en `localStorage` del navegador:
- Sobrevive refrescos de página y cierres del navegador
- Últimos 50 mensajes (configurable: `MAX_MESSAGES`)
- Botón "Limpiar" para empezar de cero
- El backend también devuelve el campo `archivo` (nombre del doc encontrado) que se muestra en el chat

### Configuración requerida en .env

```bash
OPENCODE_GO_API_KEY=sk-eHI...              # API key de OpenCode Go (67 chars)
OPENCODE_GO_BASE_URL=https://opencode.ai/zen/go/v1  # ⚠️ NO usar api.opencode.ai/v1
LLM_MODEL=deepseek-v4-pro                  # ⚠️ Modelo de RAZONAMIENTO
```

⚠️ **DeepSeek v4 es modelo de razonamiento**. PIENSA antes de responder. Con documentos clínicos pesados, el razonamiento consume 8K-15K tokens. **max_tokens debe ser ≥16000** o la respuesta sale vacía (content=""). El timeout debe ser ≥300s. Ver `flujo-browser/references/dashboard-chat-system.md` para la configuración completa y pitfalls.

### Cómo obtener la API key (en Docker)

La key está en `~/.hermes/.env`. Para copiarla al `.env` del proyecto:

```bash
python3 -c "
with open('/root/.hermes/.env') as f:
    for line in f:
        if 'OPENCODE_GO_API_KEY' in line and '=' in line:
            key = line.strip().split('=',1)[1]
with open('/root/fisioterapia/.env', 'a') as f:
    f.write(f'\nOPENCODE_GO_API_KEY={key}\n')
"
```

Al estar `.env` en GitHub (repo privado), WSL recibe la key vía `git pull`.

### ⚠️ PITFALLS

## ⚠️ PITFALLS CRÍTICOS

- **rglob sobre /mnt/c/**: `Path.rglob("*")` en directorios Windows desde WSL tarda 30-60s. Usar caché en memoria (5min TTL), `iterdir()` máx 2 niveles. NUNCA rglob recursivo.
- **Next.js proxy timeout (~30s)**: Las rewrites de Next.js matan requests largos. Para chat y subida de audio, llamar directo a `http://localhost:8000` desde el frontend.
- **Prompt demasiado grande → timeout o respuesta vacía**: System prompt + documento + workspace > 10K chars puede causar timeout. Límite seguro: documento ≤6000 chars, workspace ≤20 archivos. ⚠️ **DeepSeek v4**: max_tokens debe ser ≥16000 y timeout ≥300s. Con menos, respuesta vacía (el razonamiento consume todos los tokens).
- **`requests` NO instalado → API muere en silencio**: Verificar `pip list | grep requests` en venv WSL.
- **URL base OpenCode**: `https://opencode.ai/zen/go/v1` — NO `api.opencode.ai/v1`. La URL incorrecta da HTTP 200 con \"Not Found\".
- **API key enmascarada**: `echo $OPENCODE_GO_API_KEY` muestra `***` en shell. Leer con Python del archivo.
- **python-dotenv en CADA módulo**: Todo archivo con `os.getenv()` debe tener `load_dotenv()` propio.
- **WSL sin git init**: `git pull` falla. Setup inicial: `git init && git remote add && git fetch && git reset --hard origin/main && git branch -m main`.
- **Import List en server.py**: Si se usa `Optional[List[dict]]`, importar `from typing import List`.
- **Cédula colombiana**: `12'130.558` → `re.sub(r\"[.' ]\", \"\", cc)` → `12130558`.
- **Chat responde siempre igual**: Verificar que no es el mock viejo. Debe usar `backend.chat_handler.procesar_mensaje()`.
- **Ver referencia completa**: `references/dashboard-chat-system.md` en skill `flujo-browser`.
- **API key enmascarada**: `echo $OPENCODE_GO_API_KEY` muestra `***` en shell. Leer el archivo directamente con Python.
- **Personalidad**: El `SYSTEM_PROMPT` en `chat_handler.py` define a Tomy como colombiano, cálido, simple, conoce los 7 formatos.
- **WSL sin git init**: `git pull` falla con "not a git repository". WSL recibe los archivos por `docker cp`, no por `git clone`. Hay que hacer `git init` + `git remote add` + `git fetch` + `git reset --hard origin/main` + `git branch -m main` la primera vez.
- **Import `List` faltante en server.py**: Si se usa `Optional[List[dict]]` en modelos de Pydantic, hay que importar `List` de `typing`. El error es `NameError: name 'List' is not defined`.

## Sistema de notificaciones (Gmail + Telegram)

### Arquitectura

```
Correo Medifolios (Gmail de Sandra)
        │
        ▼  IMAP (cada 24h, 8:30 PM COL)
┌───────────────────┐
│  email_reader.py  │  Extrae: fecha, hora, paciente, teléfono, servicio
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│  notificador.py   │  Marca pacientes nuevos, guarda agenda, envía Telegram
└───────┬───────────┘
        │
        ├──→ Telegram: "📅 Mañana tienes X citas: [lista]"
        ├──→ Telegram: "🆕 NUEVO paciente: Jairo Zuñiga"
        ├──→ Telegram: "⏰ En 1 hora: Jairo Zuñiga 8:10 AM"
        └──→ Dashboard: storage/agenda_actual.json → página Archivos
```

### Configuración en .env

```bash
# Gmail — Sandra debe crear "contraseña de aplicación" en:
# https://myaccount.google.com/apppasswords
GMAIL_USER=sandra....@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx

# Telegram — Token del bot Tomy y chat ID de Sandra
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

### Cron jobs

| Job ID | Propósito | Horario |
|--------|-----------|---------|
| `cdc1f6a5` | Check agenda mañana (8:30 PM COL) | `30 1 * * *` (UTC) |
| `1192d09e` | Recordatorios 1h antes de cada cita | `*/30 11-23 * * *` |

⚠️ Los jobs fallan gracefulmente si GMAIL_USER o TELEGRAM_BOT_TOKEN no están configurados — no generan errores fatales.

## Sincronización Docker → WSL

⚠️ **MÉTODO CANÓNICO: `git pull` desde GitHub.** Tanto Docker como WSL comparten GitHub como fuente única de verdad. Docker hace `git push`, WSL hace `git pull`. NO usar `docker cp` como rutina — solo para el setup inicial o emergencias.

```bash
cd ~/rilo-backend && git pull origin main
```

**Método alternativo** (solo si git no está configurado en WSL):

Script: `~/sync-to-wsl.sh` (copiado desde Docker)

```bash
bash ~/sync-to-wsl.sh
```

Los servicios con `--reload` detectan cambios automáticamente. Si no, reiniciar.

## Tomy Completo (Mayo 2026) — Variables de entorno y rollout

### Feature flag maestro
```bash
TOMY_COMPLETO_ENABLED=false   # ← OFF por default (seguro). Poner true para activar pipeline.
```

Controla TODO el pipeline nuevo: workflow_runner, 9 pasos, task_db, dashboard /hoy, auth, backup, costos.
Si está `false`, el sistema se comporta exactamente como antes (modo legacy, sin riesgo).

### Variables nuevas (agregadas en Mayo 2026)

| Variable | Default | Uso |
|---|---|---|
| `TOMY_COMPLETO_ENABLED` | `false` | Feature flag maestro del pipeline |
| `WORKFLOW_DB_PATH` | `./storage/workflow.db` | SQLite para workflow_tasks |
| `WORKFLOW_TIMEOUT_TOTAL_S` | `1800` | Timeout máximo por paciente (30 min) |
| `AUDIO_CHUNK_DURATION_S` | `1500` | Duración de chunks para audios largos (25 min) |
| `AUDIO_TEMP_DIR` | `./storage/audios_temp` | Chunks temporales de ffmpeg |
| `AUTH_PIN` | `1234` | PIN de 4 dígitos para el dashboard |
| `AUTH_SECRET` | (cambiar en prod) | Secreto HMAC para cookies de sesión |
| `BACKUP_HORA` | `23` | Hora del backup diario (formato 24h) |
| `BACKUP_DESTINO` | `./storage/backups` | Destino de backups comprimidos |

### Rollout staged (seguro, sin romper nada)

```
Fase actual:   TOMY_COMPLETO_ENABLED=false  (producción legacy, sin cambios)
Paso siguiente: TOMY_COMPLETO_ENABLED=true   (activa pipeline completo)
```

**Plan de rollout:**
1. Dejar `false` en producción hasta validar todo en desarrollo
2. Probar con 1 paciente real en WSL con flag `true`
3. Si OK → activar definitivamente
4. Si falla → volver a `false` (modo legacy intacto)

### Módulos nuevos en backend/
| Módulo | Función |
|---|---|
| `workflow_runner.py` | Orquestador 9 pasos asíncrono |
| `task_db.py` | SQLite para persistencia de tareas |
| `workflow_steps/` | 9 pasos del pipeline (uno por archivo) |
| `lote_worker.py` | Subprocess aislado (anti-OOM) |
| `playwright_real/` | Extracción automatizada de portales |
| `organizador_formato.py` | Reorganiza DOCX crudos |
| `correction_resolver.py` | Interpreta correcciones de Sandra |
| `aplicador_correccion.py` | Aplica correcciones + regenera formatos |
| `auth_simple.py` | PIN + cookie HMAC |
| `backup_diario.py` | Backup automático 23:00 |
| `costos_tracker.py` | Tracking tokens LLM por día |
| `cron_pre_extraccion.py` | Pre-extracción nocturna de portales |

## Variables de entorno (.env)

### python-dotenv REQUERIDO

FastAPI NO carga `.env` automáticamente. Se necesita `python-dotenv`:

```bash
cd ~/rilo-backend && source venv/bin/activate && pip install python-dotenv
```

Los módulos que leen variables de entorno (`server.py`, `flujo_audio.py`, `email_reader.py`, `notificador.py`) tienen `load_dotenv()` al inicio del archivo.

⚠️ PITFALL: Si `flujo_audio.py` se importa ANTES de que `server.py` ejecute `load_dotenv()`, las variables no estarán disponibles. Por eso **cada módulo que lee `os.getenv()` debe tener su propio `load_dotenv()` al inicio**.

### Variables críticas

| Variable | Dónde se usa | Ejemplo |
|----------|-------------|---------|
| `OPENCODE_GO_API_KEY` | `chat_handler.py` | `sk-eHI...` (67 chars, de `~/.hermes/.env`) |
| `OPENCODE_GO_BASE_URL` | `chat_handler.py` | `https://opencode.ai/zen/go/v1` |
| `DEEPGRAM_API_KEY` | `flujo_audio.py` | `3888b515...` |
| `WORKSPACE_DIR` | `chat_handler.py`, `server.py` | `/mnt/c/Users/Sandra/Desktop/SANDRA/ACTIVIDADES OCUPACIONALES` |
| `GMAIL_USER` | `email_reader.py` | `sandra@gmail.com` |
| `GMAIL_APP_PASSWORD` | `email_reader.py` | Contraseña de aplicación Google |
| `TELEGRAM_BOT_TOKEN` | `notificador.py` | Token del bot |
| `TELEGRAM_CHAT_ID` | `notificador.py` | Chat ID de Sandra |

## Flujo de trabajo con GitHub

Repositorio: `https://github.com/Manupo12/auto-ma`

### ⚠️ REGLA DE ORO: CADA CAMBIO → COMMIT + PUSH

**NUNCA dejes cambios sin subir a GitHub.** WSL depende de `git pull` para recibir actualizaciones. Si hacés cambios en Docker y no los subís, WSL se desincroniza y los bugs que arreglaste no llegan a producción.

```bash
# Desde Docker (Hermes hace cambios) — OBLIGATORIO tras cada edición
cd /root/fisioterapia
git add -A
git commit -m "descripción clara del cambio"
git push origin main

# Desde WSL (aplicar cambios)
cd ~/rilo-backend && git pull origin main
```

**Si el usuario pregunta "¿lo subiste a git?", es un recordatorio de que olvidaste este paso.**

### Qué se sube y qué no (.gitignore)

⚠️ **Decisión del usuario (Mayo 2026):** `.env` SÍ se incluye en el repo porque es PRIVADO. Tiene las credenciales de Medifolios, Positiva, Deepgram, Gmail y Telegram.

**EXCLUIDO del repo:**
- `node_modules/`, `.next/`, `venv/`, `__pycache__/`
- `storage/` — documentos generados, logs con datos de pacientes
- `*.db` — base de datos SQLite con datos de pacientes
- `browser-use/` — proyecto externo clonado
- `INFORME_COMPLETO_SISTEMA*.md`, `AUDITORIA_INSTRUCCIONES.md` — informes grandes de auditoría

## Solución de problemas comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `EACCES: permission denied` | Archivos copiados con sudo | `sudo chown -R $USER:$USER ~/rilo-backend` |
| `externally-managed-environment` | Ubuntu 24.04 protege sistema | Usar venv: `python3 -m venv venv` |
| `ModuleNotFoundError: No module named 'backend'` | Archivos sueltos, no en subcarpeta | `mkdir backend && mv *.py backend/` |
| `ECONNREFUSED :8000` desde dashboard | API no corriendo o puerto no expuesto | Lanzar API en WSL, no en Docker |
| Dashboard compila pero no carga datos | API no accesible | Verificar `http://localhost:8000/api/health` |
| `Could not open requirements.txt` | No se copió desde Docker | `sudo docker cp hermes-...:/root/fisioterapia/backend/requirements.txt .` |
| Subida de audio M4A falla silenciosamente | Next.js limita body a 4MB + MIME types estrictos | ⭐ Bypass: fetch directo a `http://localhost:8000/api/upload-audio` sin proxy. Ver `dashboard/app/subir-audio/page.tsx` |
| Audio .M4A (mayúsculas) no aceptado | `file.name.endsWith(".m4a")` es case-sensitive | Usar `.toLowerCase()` en la validación de extensión |
| `DEEPGRAM_API_KEY no configurado` | python-dotenv no instalado o .env no cargado | `pip install python-dotenv` + verificar que flask_audio.py tenga `load_dotenv()` al inicio |
| Chat responde con frases genéricas o siempre igual | Mock antiguo sin reemplazar o API key no configurada | Verificar que `server.py` importa `backend.chat_handler` y usa `procesar_mensaje()`. Verificar `OPENCODE_GO_API_KEY` y `OPENCODE_GO_BASE_URL` en `.env` |
| Chat responde "No tengo conexión con mi cerebro" | `OPENCODE_GO_API_KEY` vacía o no cargada | Ejecutar script de copia de key desde `~/.hermes/.env`, verificar `load_dotenv()` en `chat_handler.py` |
| Chat responde "Ocurrió un error" | URL base incorrecta | ⚠️ Usar `https://opencode.ai/zen/go/v1`, NO `api.opencode.ai/v1` |
| `fatal: not a git repository` en WSL | Archivos llegaron por docker cp, no git clone | `git init && git remote add origin URL && git fetch && git reset --hard origin/main && git branch -m main` |
| `NameError: name 'List' is not defined` | Falta import List de typing | Agregar `from typing import List` en server.py |
| Cédula colombiana con formato antiguo | Sandra escribe "12'130.558" pero el sistema necesita "12130558" | Limpiar puntos y apóstrofes: `re.sub(r"[.' ]", "", cc)` |
| `pip install` en Docker no persiste | El contenedor no tiene las dependencias Python pre-instaladas (solo pip base) | Ejecutar `pip3 install -r backend/requirements.txt` cada vez que se reinicia el contenedor o se pierden los paquetes |
| `terminal background=true` no arranca uvicorn | El proceso sale con RC=-1 sin output. La herramienta terminal no maneja bien procesos servidores de larga duración | Usar `execute_code` con `subprocess.Popen()` en vez de terminal background. Ver sección "Arranque rápido en Docker" |
| Next.js 14 no responde en Docker (>60s) | Compilación inicial pesada (~3 min, 100%+ CPU). Puede crashear y soltar el puerto durante la compilación | Esperar o reiniciar: `pkill -f "next dev" && npm run dev`. Verificar con `ps aux | grep next`. El build estático (`npm run build`) sí funciona rápido |
| Dashboard compiló pero curl da timeout | Next.js acepta TCP pero no envía HTTP hasta terminar de compilar | Esperar a que baje el CPU (<10%). Reintentar curl. Si crasheó, relanzar |
| **Chat no responde (silencio total)** | LLM devuelve HTTP 200 con `content: ""` — el frontend muestra vacío. El usuario cree que "no respondió" | v5 reintenta 2 veces. Si ambas vacías → mensaje de fallback. Frontend detecta `contenido === ""` y muestra diagnóstico. Ver `references/dashboard-chat-system.md` |
| **Chat responde vacío**: DeepSeek v4 es modelo de RAZONAMIENTO. max_tokens debe ser ≥16000 y timeout ≥300s. Ver diagnóstico completo: `references/deepseek-v4-reasoning.md` |
| **rglob cuelga el chat 30-60s** | `Path.rglob("*")` sobre `/mnt/c/` es extremadamente lento | v5: `_fast_scandir()` — `os.scandir()` máx 2 niveles, timeout 3s, sin rglob. Ver `chat_handler.py` |

→ Detalles de la técnica de bypass en `references/nextjs-upload-bypass.md`

## Archivos de soporte

- `references/nextjs-upload-bypass.md` — Técnica de bypass para subir archivos > 4MB sin pasar por Next.js
- `scripts/sync-to-wsl.sh` — Script de sincronización Docker → WSL (copiar a `~/sync-to-wsl.sh` en el PC de Sandra)
- `templates/inicio-rilo.bat` — Plantilla de auto-arranque para `shell:startup`

### Módulos del sistema (Docker: /root/fisioterapia/backend/)

| Módulo | Rol |
|--------|-----|
| `server.py` | FastAPI — 18+ endpoints REST |
| `chat_handler.py` v7 | Motor de chat con IA REAL (DeepSeek v4, razonamiento) — ⚠️ necesita max_tokens=16000 y timeout=300s. EXPERTO ABSOLUTO en RILO. Lee docs del workspace, auto-detecta archivos, completa formatos, verifica portales |
| `puente_docker.py` 🆕 | Puente WSL→Docker: `docker exec` para disparar extracción de portales desde el chat |
| `email_reader.py` | Lector IMAP Gmail — extrae agenda de Medifolios |
| `notificador.py` | Telegram + dashboard — check 8:30 PM, recordatorios |
| `flujo_audio.py` | Deepgram nova-2 — transcripción con speaker diarization |
| `doc_generator.py` | Generación 7 formatos .docx |
| `json_validator.py` | Validación JSON contra schemas por formato |
| `format_selector.py` | Selecciona formato según estado del caso |
| `fusionador.py` | Fusión 3 fuentes + reconciliación siniestro |
| `custody.py` | Cadena de custodia, validación semántica, versionado |
| `correction_loop.py` | Loop de corrección post-rechazo |
| `browser_session.py` | Manejo sesión expirada portales |
| `extractor_medifolios.py` | Extracción guiada Medifolios (11 pasos) |
| `extractor_positiva.py` | Extracción guiada Positiva (12 pasos) |
| `pdf_archivo.py` | Conversión PDF/A-2b para archivo legal |
| `orquestador.py` | Script principal: --fusionar → --validar → --generar |

## Verificación automática de portales desde el Dashboard 🆕

### Puente Docker-WSL (`puente_docker.py`)

Permite que la API en WSL dispare extracciones de portales ejecutando `docker exec`:

```python
from backend.puente_docker import extraer_desde_wsl, obtener_datos_verificados

# Buscar datos ya extraídos (storage/data/*CC*-completo.json)
datos = obtener_datos_verificados("12130558")

# Disparar extracción browser (tarda 2-5 min)
resultado = extraer_desde_wsl("12130558")
```

### Endpoints

| Endpoint | Función |
|----------|---------|
| `GET /api/health` | Health check básico |
| `GET /api/workspace` 🆕 | Diagnóstico del workspace: archivos visibles, estado de API key, workspace activo |
| `GET /api/verificar/{cc}` | Busca datos ya extraídos. Si no hay → `estado: pendiente` |
| `POST /api/verificar/{cc}/extraer` | DISPARA extracción browser vía docker exec. Tarda 2-5 min |

### Integración con el chat

Cuando Sandra pide verificar en el chat, `chat_handler.procesar_mensaje()`:
1. Detecta intención "verificar" + extrae CC del mensaje
2. Llama `obtener_datos_verificados(cc)` 
3. Si hay datos → los inyecta al LLM con marcas ✅/⚠️/❌
4. Si no hay → el LLM responde indicando que se necesita extraer
5. El dashboard puede llamar `POST /api/verificar/{cc}/extraer` para disparar

### Contenedor Docker

El nombre del contenedor puede variar. Se configura en `.env`:
```bash
DOCKER_CONTAINER=hermes-a34da917
```
Para detectarlo: `sudo docker ps --format '{{.Names}}' | grep hermes-`

### Backup manual
```bash
sudo docker exec hermes-a34da917 bash /root/fisioterapia/backend/verificar_backup.py
```

### Actualizar dependencias
```bash
cd ~/rilo-backend && source venv/bin/activate && pip install -r backend/requirements.txt --upgrade
cd ~/rilo-dashboard && npm update
```

### Verificar estado
```bash
curl http://localhost:8000/api/health
curl http://localhost:3000
```
