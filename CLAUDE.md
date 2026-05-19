# RILO SAS — Contexto Completo del Sistema

## ¿Qué es RILO SAS?
Sistema de automatización para una clínica de fisioterapia (Rehabilitación Integral Laboral y Ocupacional) que trabaja con ARL Positiva en Colombia. El sistema genera 7 formatos clínicos, extrae datos de portales de salud, y asiste a Sandra (la fisioterapeuta) vía chat IA (Tomy).

## Usuarios
- **Sandra**: Fisioterapeuta, señora mayor, solo ofimática básica. Lenguaje simple, español colombiano. Usa el dashboard y Telegram.
- **Hijo/a de Sandra**: Técnico, configuró el sistema. Revisa cada paso. Exige exploración exhaustiva de portales.

## Arquitectura
```
Docker (Hermes/Tomy) ──git push──→ GitHub (Manupo12/auto-ma) ──git pull──→ WSL (producción PC Sandra)
                                                              ←──git push── Workspace de Sandra
```

### Entornos
- **Docker**: Desarrollo. Contenedor `hermes-a34da917`. Código en `/root/fisioterapia/`.
- **WSL**: Producción en PC de Sandra. `~/rilo-backend/` (FastAPI :8000) + `~/rilo-dashboard/` (Next.js :3000).
- **GitHub**: `https://github.com/Manupo12/auto-ma` — fuente única de verdad.

## Estructura del Proyecto

### Backend (`backend/`) — 8,700+ líneas Python
| Módulo | Líneas | Función |
|--------|--------|---------|
| `doc_generator.py` | 2,172 | Genera 7 formatos .docx + PDF |
| `chat_handler.py` | ~750 | Motor IA del chat (DeepSeek v4) |
| `json_validator.py` | 657 | Schemas por formato, validación |
| `custody.py` | 626 | Cadena custodia, validación semántica |
| `correction_loop.py` | 560 | Loop corrección post-rechazo |
| `server.py` | 555 | FastAPI — 18+ endpoints |
| `extractor_medifolios.py` | 465 | Extracción portal Medifolios |
| `extractor_positiva.py` | 407 | Extracción portal ARL Positiva |
| `fusionador.py` | 395 | Fusión 3 fuentes + reconciliación |
| `browser_session.py` | 366 | Manejo sesión expirada portales |
| `email_reader.py` | 346 | IMAP Gmail — agenda Medifolios |
| `format_selector.py` | 332 | Selecciona formatos por estado |
| `notificador.py` | 268 | Telegram + dashboard |
| `flujo_audio.py` | 245 | Deepgram transcripción |
| `pdf_archivo.py` | 184 | PDF/A-2b archivo legal |
| `verificar_backup.py` | 215 | Restauración mensual backup |
| `orquestador.py` | 180 | Script principal CLI |
| `puente_docker.py` | 192 | WSL↔Docker bridge |

### Dashboard (`dashboard/`) — Next.js 14
6 páginas: Home, Pacientes, Formatos, Chat (con IA real), Archivos (explorador), Subir Audio

### Skills (`skills/`) — 5 skills de fisioterapia
- `flujo-browser/` — Mapa completo de Medifolios (18/18 secciones) y Positiva (9/9)
- `flujo-audio/` — Transcripción Deepgram + diarización
- `generar-documento/` — Generación de 7 formatos
- `verificar-documento/` — QA 10 capas para documentos
- `rilo-despliegue/` — Setup WSL, cron jobs, sincronización

### Storage (`storage/`)
- `docs/` — 33+ documentos .docx generados
- `pdfs/` — 8 PDFs para archivo legal
- `data/` — JSON con datos de pacientes (1193143688, 55162801)
- `reports/` — Reportes de validación
- `huellas_portales.json` — Huella digital de portales

## Los 7 Formatos Clínicos
1. Análisis de Exigencias — perfil del cargo, demandas físicas
2. Carta de Medidas Preventivas — restricciones, adaptaciones
3. Carta de Recomendaciones — reincorporación, seguimiento
4. Cierre de Caso — logros, estado final
5. Citación a Empresas — convocatoria, visita
6. Prueba de Trabajo — tareas, observación
7. VOI (Valoración Desempeño Ocupacional) — historia ocupacional, áreas

## Pacientes con datos
- Juan Carlos Duran Narvaez — CC 1193143688, Siniestro 503463870
- Rosa Maria Garcia Suarez — CC 55162801, Siniestro 503501234
- Laura Rojas Zuñiga — CC 36184789

## Portales
### Medifolios — server0medifolios.net
- User: 55162801-2 / Pass: 55162801-2
- Extraer: datos paciente, historia clínica, siniestro (de Observaciones en Agenda Citas)

### ARL Positiva — positivacuida.positiva.gov.co
- User: 1075209386MR / Pass: Rilo2026*
- Extraer: siniestro OFICIAL, diagnóstico CIE-10, datos asegurado, autorizaciones
- 6 pestañas en Consulta integral + Consultar caso RHI

## LLM — DeepSeek v4 (OpenCode Go)
- URL: `https://opencode.ai/zen/go/v1` (NO api.opencode.ai)
- Modelo de RAZONAMIENTO: gasta 8K-15K tokens pensando antes de responder
- max_tokens DEBE ser ≥8000 o respuesta vacía (finish=length)
- API key en `.env`: OPENCODE_GO_API_KEY
- ⚠️ PROBLEMA CONOCIDO: Contenedor Docker OOM (exit 137) con 5+ lotes
  - Causa: razonamiento acumula ~65K tokens en RAM entre llamadas
  - Solución: aumentar RAM del contenedor (`docker run --memory=2g`)
  - O usar modelo sin razonamiento (deepseek-chat)

## Cron Jobs
- `cdc1f6a5`: Agenda mañana (8:30 PM COL)
- `1192d09e`: Recordatorios 1h antes de cada cita
- `75bd86a3daf1`: Verificación mensual backup (día 1, 3 AM)

## Configuración
- `config/hermes-config.yaml` — Config completa de Hermes Agent
- `config/hermes-env.txt` — Variables de entorno (keys masked)
- `.env` — Variables de entorno del proyecto RILO

## Convenciones
- CC colombiana: limpiar apóstrofes y puntos (12'130.558 → 12130558)
- VOI = Valoración de Desempeño Ocupacional (Formato 7)
- Tomy = nombre del asistente IA (NO "Hermes")
- Workspace Sandra: `C:\Users\Sandra\Desktop\SANDRA\ACTIVIDADES OCUPACIONALES`
- WSL workspace: `/mnt/c/Users/Sandra/Desktop/SANDRA/ACTIVIDADES OCUPACIONALES`
- NO usar rglob en /mnt/c/ (lentísimo, 30s+) — usar scandir máx 2 niveles
- Chat dashboard: fetch directo a :8000, NO proxy Next.js (timeout 30s)

## Problemas Actuales (Mayo 2026)
1. **OOM en lotes**: procesar 9 formatos con DeepSeek v4 agota RAM del contenedor
2. **Extracción portales**: no probada con navegador real
3. **Firma Sandra**: `firma_sandra.png` no existe aún
4. **.odt → .docx**: `ejemplo prueba de trabajo.odt` sin convertir
5. **Gmail/Telegram**: tokens pendientes de configurar
