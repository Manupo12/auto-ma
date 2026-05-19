# Arquitectura Completa del Sistema RILO SAS — v2.0 (Mayo 2026)

## Backend (13 módulos en `/root/fisioterapia/backend/`)

| Módulo | Líneas | Función |
|--------|--------|---------|
| `doc_generator.py` | ~2500 | Genera 7 formatos DOCX (python-docx + LibreOffice PDF) |
| `json_validator.py` | ~400 | ① Valida JSON contra schemas (required/recommended/optional/defaults) |
| `format_selector.py` | ~280 | ② Selecciona formatos según estado (NUEVO/SEGUIMIENTO/CIERRE/PRUEBA) |
| `fusionador.py` | ~316 | ③ Fusiona 3 fuentes + reconciliación de siniestro |
| `custody.py` | ~650 | Validación semántica (11 patrones), custodia, versionado (APROBADO inmutable), confianza (0-100), huella portales, modo degradado, prompt clínico |
| `correction_loop.py` | ~500 | ⑤⑥⑦ NLP español: interpreta rechazos de Sandra → corrige |
| `browser_session.py` | ~350 | ⑧ Detección sesión expirada + re-autenticación |
| `extractor_medifolios.py` | ~400 | Sub-flujo A: 11 pasos guiados |
| `extractor_positiva.py` | ~350 | Sub-flujo B: 12 pasos guiados |
| `pdf_archivo.py` | ~180 | PDF/A-2b (ISO 19005) para archivo legal |
| `verificar_backup.py` | ~200 | Cron mensual: restaura backup, verifica, reporta Telegram |
| `flujo_audio.py` 🆕 | ~238 | Deepgram nova-2 + speaker diarization + extracción clínica |
| `server.py` 🆕 | ~361 | FastAPI (puerto 8000): /api/chat, /api/upload-audio, /api/pacientes, /api/formatos |
| `orquestador.py` | ~200 | Script principal (--fusionar, --validar, --generar) |

## Dashboard (`/root/fisioterapia/dashboard/`)
- **Stack:** Next.js 14 + TypeScript + Tailwind CSS + Lucide React
- **Build:** `npm run dev` → http://localhost:3000
- **5 páginas:** Home (reconciliación, estado sistema), Pacientes (búsqueda), Formatos (versionado + PDF/A), Chat (Tomy), Subir Audio (speaker diarization + confianza)
- **3 componentes:** Sidebar, ConfianzaBadge (semáforo 0-100), ReconciliacionAlert
- **2 API routes:** Proxy POST → Hermes (localhost:8000)
- **Cliente:** `lib/hermes.ts`

## Skills (`~/.hermes/skills/fisioterapia/`)
- `flujo-browser` — Mapa 27/27 secciones portales + guías extracción
- `generar-documento` — Guía generación 7 formatos + pitfalls
- `verificar-documento` — QA 10 capas
- `flujo-audio` — Deepgram + diarization + filtrado

## Dependencias necesarias
```bash
pip install requests fastapi uvicorn python-multipart
```

## Credenciales (`.env`)
- Medifolios: 55162801-2 / server0medifolios.net
- Positiva: 1075209386MR / positivacuida.positiva.gov.co
- Deepgram: 3888b515...
- Telegram: @Tomy1201_bot / chat 8424650300
