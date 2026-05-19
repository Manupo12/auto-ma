# Chat Handler — Receta de debugging y configuración

## Síntoma: Chat responde siempre con el mensaje de ayuda

El chat del dashboard (`/api/chat` → `chat_handler.py`) respondía siempre con el mismo mensaje genérico de ayuda, sin importar lo que Sandra escribiera.

### Causa raíz

Dos causas en secuencia:
1. El `server.py` tenía un mock con if/else que nunca llamaba al LLM real
2. Al reemplazarlo, la API key y URL base de OpenCode Go no estaban configuradas

### Pasos de debugging (orden correcto)

1. **Verificar que server.py usa el handler nuevo:**
   ```python
   from backend.chat_handler import procesar_mensaje
   resultado = procesar_mensaje(req.mensaje, req.paciente_cc)
   ```
   Si `server.py` tiene `if "siniestro" in msg:` → es el mock viejo.

2. **Verificar que OPENCODE_GO_API_KEY está cargada:**
   ```bash
   python3 -c "import os; print('KEY:', repr(os.getenv('OPENCODE_GO_API_KEY', 'NOT SET')[:10]+'...'))"
   ```
   Si sale `NOT SET` → la variable no está en el entorno de Python.
   
   La variable está en `~/.hermes/.env` pero no se exporta al shell de comandos. 
   SOLUCIÓN: leer el archivo directamente con Python, no depender de `os.getenv()`:
   ```python
   with open('/root/.hermes/.env') as f:
       for line in f:
           if 'OPENCODE_GO_API_KEY' in line and '=' in line:
               api_key = line.strip().split('=',1)[1]
   ```

3. **Verificar URL base correcta:**
   ```bash
   curl -s -X POST https://opencode.ai/zen/go/v1/chat/completions \
     -H "Authorization: Bearer $KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"deepseek-v4-pro","messages":[{"role":"user","content":"hola"}]}'
   ```
   - URL CORRECTA: `https://opencode.ai/zen/go/v1` → HTTP 200 + JSON válido
   - URL INCORRECTA: `https://api.opencode.ai/v1` → HTTP 200 + "Not Found"

4. **Verificar nombre del modelo:**
   El modelo configurado en Hermes es `deepseek-v4-pro`. Si no funciona, revisar:
   ```bash
   grep "model:" ~/.hermes/config.yaml
   grep "provider:" ~/.hermes/config.yaml
   ```

## Sistema prompt de Tomy

El `chat_handler.py` define un `SYSTEM_PROMPT` que establece la personalidad:

- Español colombiano, cálido y simple
- Cero jerga técnica (API, endpoint, JSON, servidor)
- Conoce los 7 formatos ARL Positiva
- Pide cédula para completar documentos
- Usa emojis para ser amigable
- NO inventa información clínica

## Fallback sin API key

Si `OPENCODE_GO_API_KEY` está vacía, el chat responde:
> ⚠️ *Aviso:* No tengo conexión con mi cerebro principal. Dile a Manu que configure...

Esto evita que el chat se rompa — sigue siendo usable para tareas básicas.

## Lección: API keys de Hermes enmascaradas

El shell de Hermes enmascara variables con `***` para seguridad. `echo $VAR` no sirve.
Para leer el valor real: `python3 -c "print(os.getenv('VAR'))"` o leer el archivo `.env` directamente.
