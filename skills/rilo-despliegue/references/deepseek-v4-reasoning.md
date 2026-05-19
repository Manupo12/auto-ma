# DeepSeek v4 — Modelo de Razonamiento: Diagnóstico y Configuración

> Lecciones de la sesión Mayo 18, 2026 — chat del dashboard no respondía (10+ intentos fallidos).

## TL;DR

DeepSeek v4 (`deepseek-v4-pro` vía OpenCode Go) es un modelo de RAZONAMIENTO. PIENSA antes de responder. Si `max_tokens` es menor que lo que necesita para pensar, la respuesta sale VACÍA (`content: ""`). El usuario ve "no me responde".

## Síntomas

| Lo que ve el usuario | Lo que realmente pasa |
|----------------------|----------------------|
| Chat en silencio, no aparece respuesta | HTTP 200 pero `content: ""` |
| "no me responde" después de varios intentos | `finish_reason: "length"` — tokens agotados en razonamiento |
| Tarda 30-60s y luego nada | El modelo pensó, gastó todos los tokens, no llegó a escribir respuesta |
| A veces responde, a veces no | Depende el tamaño del prompt — prompts más grandes necesitan más razonamiento |

## Diagnóstico paso a paso

### 1. Verificar que la API responde

```bash
curl -s https://opencode.ai/zen/go/v1/chat/completions \
  -H "Authorization: Bearer $OPENCODE_GO_API_KEY" \
  -H "Content-Type: application/json" \
  -H "User-Agent: Mozilla/5.0" \
  -d '{"model":"deepseek-v4-pro","messages":[{"role":"user","content":"Di hola"}],"max_tokens":500}'
```

⚠️ Sin `User-Agent`, Cloudflare devuelve 403.

### 2. Inspeccionar la respuesta cruda

El campo clave es `choices[0].message`:

```json
{
  "choices": [{
    "finish_reason": "length",
    "message": {
      "content": "",
      "reasoning_content": "Para responder necesito analizar..."
    }
  }],
  "usage": {"completion_tokens": 2000, "total_tokens": 2500}
}
```

**Regla:** Si `finish_reason == "length"` y `content == ""` → `max_tokens` insuficiente.

### 3. Probar con max_tokens creciente

Resultados típicos con documento clínico (~5000 chars prompt):

| max_tokens | content | reasoning | finish | ¿Funciona? |
|-----------|---------|-----------|--------|------------|
| 200 | 0 chars | 830 chars | length | ❌ |
| 500 | 90 chars | 829 chars | stop | ⚠️ muy corto |
| 1000 | 172 chars | 1421 chars | stop | ⚠️ corto |
| 2000 | 0 chars | 7909 chars | length | ❌ |
| 8000 | 3450 chars | 9305 chars | stop | ✅ |
| 16000 | 3373 chars | 15698 chars | stop | ✅ (9 archivos) |

## Configuración correcta

```python
# ❌ MAL — bug original
max_tokens = 800; timeout = 45

# ✅ BIEN — valores probados
max_tokens_values = [16000, 24000]  # intento 1, intento 2
timeout = 300  # 5 minutos
frontend_timeout = 300000  # ms (AbortSignal)
```

## Pitfalls adicionales

### Cloudflare 403
`HTTP 403 | error code: 1010` → Agregar `User-Agent: Mozilla/5.0`

### CC detection con word boundaries
```python
# ❌ MAL — quitar espacios rompe \b
limpio = mensaje.replace(" ", "")
m = re.search(r'\b(\d{6,12})\b', limpio)  # "de1193143688" sin boundary

# ✅ BIEN
m = re.search(r'\b(\d{6,12})\b', mensaje.replace("'","").replace(".","").replace(",",""))
```

### rglob en /mnt/c/
`Path.rglob("*")` tarda 30-60s. Usar `os.scandir()` máx 2 niveles, timeout 3s.

### Límites de prompt
- Documento individual: ≤6000 chars (60 párrafos + 5 tablas)
- Multi-archivo (7+ formatos): ≤15000 chars total
- Workspace listing: ≤20 archivos
- Total prompt al LLM: 5K-14K chars (aceptable con max_tokens=16000)
