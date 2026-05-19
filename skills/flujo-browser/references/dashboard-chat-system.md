# Dashboard Chat System — Arquitectura y Configuración (v7, Mayo 2026)

## Arquitectura

```
Dashboard (Next.js :3000, WSL)
  │
  ├── Chat page → LLAMA DIRECTAMENTE a API :8000 (NO proxy Next.js)
  │     ⚠️ Si pasa por Next.js rewrite, timeout 30s mata respuestas largas
  │     AbortSignal.timeout(300000) — timeout 5 min en frontend
  │
  └── Resto de páginas → Next.js rewrite → API :8000
      
API (FastAPI :8000, WSL)
  │
  ├── chat_handler.py v7 → DeepSeek v4 vía OpenCode Go
  │     URL base: https://opencode.ai/zen/go/v1 (NO api.opencode.ai/v1)
  │     Modelo: deepseek-v4-pro ⚠️ MODELO DE RAZONAMIENTO
  │     max_tokens: 16000 → 24000 (intento 1: 16000, intento 2: 24000)
  │     timeout: 300s por intento (5 min)
  │     User-Agent: Mozilla/5.0 (Cloudflare 403 sin esto)
  │     Lectura: 60 párrafos + 5 tablas (8 filas c/u) + 6000 chars máx
  │     Búsqueda: nombre parcial (≥2 palabras del mensaje en el stem)
  │     Workspace: scandir rápido (sin rglob), fallback a storage/docs/
  │     Persistencia: localStorage guarda 50 mensajes, botón Limpiar
  │
  ├── puente_docker.py → docker exec en contenedor Hermes
  │
  └── email_reader.py → Gmail IMAP

Docker (hermes-a34da917)
  └── /root/fisioterapia/ — código fuente canónico
```

## ⚠️ DEEPSEEK V4: MODELO DE RAZONAMIENTO — EL PITFALL MÁS GRANDE

DeepSeek v4 **PIENSA antes de responder**. El razonamiento (`reasoning_content`) consume tokens ANTES de que el modelo genere la respuesta visible (`content`).

**Síntoma del bug**: HTTP 200, pero `content: ""` (vacío). `finish_reason: "length"`. El frontend no muestra nada.

**Causa real**: Con documentos clínicos complejos (VOI 19 páginas, tablas, datos), el razonamiento puede consumir **8K-15K tokens**. Si `max_tokens` es insuficiente, TODOS los tokens se gastan en razonamiento y la respuesta queda vacía.

**Ejemplo real de la prueba**:
```
max_tokens=200:  content=0 chars   reasoning=830 chars  ❌ finish=length
max_tokens=500:  content=90 chars  reasoning=829 chars  ✅ finish=stop  
max_tokens=8000: content=3450 chars reasoning=9305 chars ✅ finish=stop
max_tokens=16000:content=1153 chars reasoning=14906 chars✅ finish=stop
```

**Configuración correcta**:
- `max_tokens`: **16,000** (mínimo). Si falla, reintento con 24,000.
- `timeout`: **300 segundos** (5 min). El modelo tarda 2-4 min con docs pesados.
- **NUNCA usar max_tokens < 2000** con DeepSeek v4. Respuesta vacía garantizada.

**Manejo de fallback en el código (v7)**:
1. Intento 1: max_tokens=16000, timeout=300s
2. Si content vacío y finish=length → Intento 2: max_tokens=24000
3. Si aún vacío y hay reasoning_content → extraer últimas 3 líneas del razonamiento como respuesta fallback
4. Si finish=stop pero content vacío → mensaje: "El modelo no generó respuesta"
5. Si agotados intentos → "No pude generar respuesta después de varios intentos"

## Configuración de Producción

### Backend (chat_handler.py v7)

| Parámetro | Valor | Nota |
|-----------|-------|------|
| `max_tokens` | 16,000 → 24,000 | Intento 1 y 2. Sin esto, respuesta vacía |
| `timeout` HTTP | 300s | Por intento. Total máx: 600s |
| `temperature` | 0.7 | Balance creatividad/precisión |
| Lectura párrafos | 60 | Docs de varias páginas |
| Lectura tablas | 5 (8 filas c/u) | Tablas clínicas grandes |
| Límite chars doc | 6,000 | Suficiente para VOI 19 págs |
| Workspace files | 20 máx | No saturar prompt |
| System prompt | ~1,200 chars | Compacto, directo |

### Frontend (page.tsx v7)

| Parámetro | Valor |
|-----------|-------|
| AbortSignal | 300,000ms (5 min) |
| localStorage | 50 mensajes |
| API endpoint | `http://localhost:8000/api/chat` |

### Endpoints de diagnóstico

- `GET /api/workspace` — JSON con lista de archivos, si el workspace existe, API key configurada
- `GET /api/health` — `{"ok": true, "version": "1.0.0"}`
- `POST /api/chat` — devuelve `archivo`, `accion`, `workspace_accesible`, `tiempo`

## Pitfalls de Búsqueda de Archivos

### Estrategia 0: nombre PARCIAL (NUEVA en v5)
- "VOI_JOHN" en el mensaje → matchea `VOI_JOHN DEIVER OLIVEROS MAYUNGO.docx`
- ≥2 palabras del mensaje aparecen en el stem del archivo

### Estrategia 1: nombre exacto
- El stem completo está en el mensaje

### Estrategia 2: coincidencia de palabras largas
- ≥2 palabras de ≥4 letras coinciden entre mensaje y nombre de archivo

### Estrategia 3: tipo de formato + nombre
- "voi" → busca archivos con "valoracion" en el nombre, prioriza por coincidencia de nombre de paciente

## Pitfalls de Workspace

1. **rglob en /mnt/c/**: `Path.rglob("*")` sobre directorios Windows desde WSL tarda 30-60s. **Fix**: `os.scandir()` máx 2 niveles, timeout 3s.
2. **Workspace inexistente en Docker**: `/mnt/c/Users/...` no existe. **Fix**: fallback automático a `storage/docs/`.
3. **Diagnóstico**: `curl http://localhost:8000/api/workspace`

## Pitfalls de API

1. **Cloudflare 403**: Sin `User-Agent: Mozilla/5.0`, OpenCode Go bloquea requests desde servidores.
2. **URL base**: `https://opencode.ai/zen/go/v1` — NO `api.opencode.ai/v1`
3. **API key**: 67 caracteres, leer de `~/.hermes/.env` en Docker, de `.env` en WSL.

## Persistencia del Chat

- **localStorage** en el navegador guarda últimos 50 mensajes
- Campo `archivo` en `ChatMessage` muestra el nombre del archivo que Tomy encontró
- Botón "Limpiar" borra localStorage y reinicia conversación
- `historial`: últimos 10 mensajes enviados al LLM como contexto

## Flujo de Trabajo con Git

⚠️ CADA CAMBIO → commit + push para que WSL reciba:

```bash
cd /root/fisioterapia
git add -A && git commit -m "..." && git push origin main
```

En WSL:
```bash
cd ~/rilo-backend && git pull origin main
```

## Formato de CC Colombiana

`12'130.558` → `re.sub(r"['. ]", "", cc)` → `12130558`

## Abreviaciones de Sandra

- VOI = Valoración de Desempeño Ocupacional (Formato 7)
