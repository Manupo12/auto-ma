# Envío de documentos por Telegram

Para cuando la doctora necesita revisar un documento generado antes de aprobarlo.

## Método: API directa (no requiere gateway corriendo)

```python
import requests

# Token y chat ID desde .env
token = "867879..."  # TELEGRAM_BOT_TOKEN
chat_id = "8424650300"  # TELEGRAM_HOME_CHANNEL

docx_path = "/root/fisioterapia/storage/docs/documento.docx"
caption = "📄 Descripción del documento"

url = f"https://api.telegram.org/bot{token}/sendDocument"
with open(docx_path, "rb") as f:
    resp = requests.post(url, 
        data={"chat_id": chat_id, "caption": caption},
        files={"document": ("nombre.docx", f)})

print(resp.json())  # → message_id para referencia
```

## Notas
- La API de Telegram acepta .docx directamente (mime: application/vnd.openxmlformats-officedocument...)
- No es necesario convertir a PDF primero para revisión
- El límite de tamaño es 50 MB por archivo
- El bot debe estar autorizado por el usuario (@Tomy1201_bot)
- Para envíos programados, usar el gateway; para envíos únicos de revisión, API directa funciona
