---
name: flujo-audio
description: Recibe un audio de consulta subido desde el dashboard web o Telegram, lo transcribe con Deepgram, y extrae los datos cualitativos para los formatos clínicos.
triggers:
  - "transcribir audio"
  - "procesar audio"
  - "subir audio"
  - "deepgram"
---

# Flujo de Audio — Transcripción con Deepgram

## Fuente de datos
Sandra graba la cita con el paciente usando la app Grabadora de su iPhone.
El archivo (M4A/MP3/WAV) se sube al dashboard web o se envía por Telegram.

## Tecnología
- **Deepgram** — API de transcripción de audio a texto (speech-to-text)
- **API Key** — `DEEPGRAM_API_KEY` en `.env`
- **Endpoint** — `https://api.deepgram.com/v1/listen`

## Flujo completo

```
iPhone (Grabadora) → Dashboard (subir audio) → Hermes → Deepgram (nova-2)
                                                              │
                                                    Speaker Diarization
                                                    (Speaker 0 = Sandra, Speaker 1 = Paciente)
                                                              │
                                                    Filtrado de basura
                                                    (saludos, pausas, ruido → descartados)
                                                              │
                                                    Prompt clínico estructurado
                                                    (extrae 10 campos con reglas absolutas)
                                                              │
                                                    Confianza por campo (0-100)
                                                    (verde≥80, amarillo≥50, rojo<50)
                                                              │
                                                    Dashboard: revisión por segmentos
                                                    (timestamp + audio + campo extraído)
                                                              │
                                                    Sandra aprueba/corrige → JSON final
                                                              │
                                                    Fusionar + Generar formatos
```

## Estrategia de filtrado de audio y speaker diarization

El audio contiene mucha "basura": saludos, pausas, ruido, conversación casual.
El paciente NO habla en términos clínicos — dice "me duele aquí cuando levanto el brazo"
y eso DEBE convertirse en lenguaje del formato, pero SIN reformatear ni resumir.

### 1. Speaker Diarization (Deepgram `diarize: true`)
- **Speaker 0** = Sandra (fisioterapeuta) — hace preguntas, da instrucciones, contexto clínico
- **Speaker 1** = Paciente — respuestas, descripción de síntomas, tareas, historia
- Para formatos interesan MÁS los segmentos del paciente (Speaker 1)
- Las preguntas de Sandra NO deben confundirse con respuestas del paciente

### 2. Filtrado de basura
Palabras ignoradas: "buenos días", "cómo está", "gracias", "chao", "listo", "entonces", "eh", "mmm", "respire", "siéntese", "párese", "tosa".
Segmentos < 15 caracteres se descartan.
Solo se conservan segmentos con palabras clave clínicas.

Palabras clave de Sandra (detectan contexto clínico):
"metodología", "método", "procedimiento", "valoración", "desempeño", "cargo", "funciones",
"tareas", "actividad", "materiales", "herramientas", "equipos", "peligros", "riesgo",
"recomendación", "concepto", "conclusión", "diagnóstico", "síntoma", "dolor", "limitación",
"jornada", "horario", "ritmo", "descanso", "turno", "levantar", "cargar", "empujar",
"halar", "movimiento", "postura", "bípeda", "sedente", "peso", "kilo"

### 3. Prompt clínico estructurado
La transcripción NO va directo al documento. Pasa por un prompt clínico que extrae
exactamente los campos que necesita cada formato. Ver `references/prompt-clinico-audio.md`.

REGLAS ABSOLUTAS del prompt:
1. Si el dato NO se menciona explícitamente, devuelve null. NUNCA inventar.
2. Usar el lenguaje EXACTO del paciente. No reformatear ni resumir.
3. Si el paciente dice "me duele aquí cuando levanto el brazo", escribir ESO.
4. Distinguir Speaker 0 (Sandra) de Speaker 1 (paciente).
5. Campos ambiguos → marcar con confianza baja.

### 4. Confianza por campo (0-100)
Cada campo extraído del audio recibe un score:
- ≥80 (verde): el paciente dijo claramente el dato
- 50-79 (amarillo): mencionado vagamente, requiere confirmación de Sandra
- <50 (rojo): inferido o no mencionado

Factores que afectan la confianza:
- Claridad de la frase (+40 si >30 caracteres)
- Proximidad a palabras clave del campo (+30)
- Frase completa con puntuación (+20)
- Múltiples menciones en la conversación (+10)

### 5. Timestamps vinculados
Cada dato extraído lleva el timestamp exacto donde el paciente lo dijo (MM:SS).
Sandra puede hacer clic en el dato en el dashboard y escuchar ese fragmento exacto.
No tiene que escuchar toda la hora de consulta.

### 6. Revisión por segmentos en el dashboard
Sandra ve cada fragmento de audio al lado del campo extraído. Aprueba o corrige
campo por campo. Los campos con confianza <70 aparecen en amarillo. Esto convierte
la revisión en algo rápido y visual.

### 7. Aprendizaje por corrección
Cada corrección de Sandra se guarda. El sistema aprende patrones regionales:
ej. "la mano derecha me falla" → Sandra lo mapea a "dificultad en agarre unilateral derecho"

## Configuración Deepgram
Ver `references/deepgram-config.md` para API key, parámetros, estructura de respuesta, filtrado y confianza por campo.

## Implementación en backend
El código de producción está en `backend/flujo_audio.py` (238 líneas) y se expone vía `backend/server.py` (FastAPI, puerto 8000) en `POST /api/upload-audio`. El dashboard (`/subir-audio`) consume ese endpoint.

```python
import os
import requests

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"

def transcribir_audio(audio_path: str) -> dict:
    """
    Transcribe un archivo de audio usando Deepgram.
    
    Args:
        audio_path: Ruta al archivo de audio (M4A, MP3, WAV)
    
    Returns:
        {
            "texto": "Texto completo transcrito",
            "duracion": 123.4,  # segundos
            "confianza": 0.95,
            "segmentos": [{"texto": "...", "inicio": 0.0, "fin": 5.2}, ...]
        }
    """
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/m4a" if audio_path.endswith(".m4a") else "audio/mpeg",
    }
    
    # Parámetros: español de Colombia, puntuación, speaker diarization
    params = {
        "language": "es",
        "punctuate": "true",
        "diarize": "true",  # Identificar diferentes hablantes
        "model": "nova-2",  # Modelo más preciso para español
    }
    
    with open(audio_path, "rb") as f:
        response = requests.post(
            DEEPGRAM_URL,
            headers=headers,
            params=params,
            data=f,
        )
    
    if response.status_code != 200:
        raise Exception(f"Deepgram error: {response.status_code} - {response.text}")
    
    data = response.json()
    resultados = data.get("results", {})
    canales = resultados.get("channels", [{}])
    alternativas = canales[0].get("alternatives", [{}])
    
    transcripcion = alternativas[0].get("transcript", "")
    confianza = alternativas[0].get("confidence", 0)
    duracion = resultados.get("metadata", {}).get("duration", 0)
    
    # Segmentos por hablante
    segmentos = []
    for alt in alternativas:
        for word in alt.get("words", []):
            texto = word.get("punctuated_word", word.get("word", ""))
            inicio = word.get("start", 0)
            fin = word.get("end", 0)
            hablante = word.get("speaker", 0)
            segmentos.append({
                "texto": texto,
                "inicio": inicio,
                "fin": fin,
                "hablante": hablante,
            })
    
    return {
        "texto": transcripcion,
        "duracion": duracion,
        "confianza": confianza,
        "segmentos": segmentos,
    }


def extraer_datos_cualitativos(transcripcion: str) -> dict:
    """
    Extrae los datos cualitativos del texto transcrito usando NLP básico.
    Busca patrones comunes en las notas de Sandra.
    
    Returns:
        {
            "metodologia": "texto de metodología",
            "proceso_productivo": "descripción del proceso",
            "apreciacion_trabajador": "lo que dice el trabajador",
            "estandares_productividad": "estándares",
            "materiales": [{"nombre": "...", "estado": "..."}],
            "peligros": [{"nombre": "...", "descripcion": "...", "control": "...", "recomendacion": "..."}],
            "tareas_criticas": [{"actividad": "...", "ciclo": "...", "descripcion": "..."}],
            "concepto_desempeno": "concepto",
            "recomendaciones": {"trabajador": "", "empresa": ""},
        }
    """
    import re
    
    datos = {
        "metodologia": "",
        "proceso_productivo": "",
        "apreciacion_trabajador": "",
        "estandares_productividad": "",
        "materiales": [],
        "peligros": [],
        "tareas_criticas": [],
        "concepto_desempeno": "",
        "recomendaciones": {"trabajador": "", "empresa": ""},
    }
    
    texto = transcripcion.lower()
    
    # Buscar secciones por palabras clave
    patrones_secciones = {
        "metodologia": [
            r"(?:metodología|método|procedimiento)(?:.*?)(?=\n\n|\n(?:la servidora|el trabajador|los materiales|se identificaron|$))",
        ],
        "proceso_productivo": [
            r"(?:la servidora|el trabajador|el paciente)\s+(?:manifiesta|menciona|indica|realiza|describe)\s+(?:las siguientes|las|que\s+sus)?\s*(?:funciones|tareas|actividades)?(?:.*?)(?=\n\n|\n(?:los materiales|se identificaron|el ritmo|$))",
        ],
        "apreciacion_trabajador": [
            r"(?:la servidora|el trabajador)\s+(?:manifiesta|menciona|indica|refiere)\s+(?:que|dolor|limitación|molestia)(?:.*?)(?=\n\n|\n(?:la servidora puede|se realizó|$))",
        ],
        "estandares_productividad": [
            r"(?:el ritmo de trabajo|la productividad|estándares|meta)(?:.*?)(?=\n\n|\n(?:$))",
        ],
        "concepto_desempeno": [
            r"(?:concepto|desempeño|capacidad|conclusión)(?:.*?)(?=\n\n|$)",
        ],
    }
    
    for campo, patrones in patrones_secciones.items():
        for patron in patrones:
            match = re.search(patron, texto, re.DOTALL | re.IGNORECASE)
            if match:
                datos[campo] = match.group(0).strip()
                break
    
    # Extraer materiales mencionados
    materiales_keywords = ["gancho", "pala", "barra", "tubo", "martillo", "destornillador", 
                          "guantes", "casco", "gafas", "botas", "epp", "herramienta"]
    for kw in materiales_keywords:
        if kw in texto:
            datos["materiales"].append({"nombre": kw.capitalize(), "estado": "Bueno"})
    
    # Extraer peligros mencionados
    peligros_keywords = ["biomecánico", "ergonómico", "caída", "ruido", "químico", 
                        "psicosocial", "eléctrico", "mecánico", "carga", "repetitivo"]
    for kw in peligros_keywords:
        if kw in texto:
            datos["peligros"].append({
                "nombre": f"Peligro {kw.capitalize()}",
                "descripcion": f"Asociado a {kw}",
                "control": "",
                "recomendacion": "",
            })
    
    return datos
```

## Integración con el dashboard

```python
# API endpoint en el backend de Hermes
from fastapi import APIRouter, UploadFile, File, Form
from backend.flujo_audio import transcribir_audio, extraer_datos_cualitativos

router = APIRouter(prefix="/api/upload-audio")

@router.post("/")
async def upload_audio(
    audio: UploadFile = File(...),
    paciente_cc: str = Form(...),
):
    # 1. Guardar archivo temporal
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp:
        tmp.write(await audio.read())
        audio_path = tmp.name
    
    # 2. Transcribir con Deepgram
    transcripcion = transcribir_audio(audio_path)
    
    # 3. Extraer datos cualitativos
    datos = extraer_datos_cualitativos(transcripcion["texto"])
    
    # 4. Guardar transcripción
    import json, os
    os.makedirs(f"storage/audio/{paciente_cc}", exist_ok=True)
    with open(f"storage/audio/{paciente_cc}/transcripcion.json", "w") as f:
        json.dump({"transcripcion": transcripcion, "datos": datos}, f, indent=2)
    
    # 5. Limpiar archivo temporal
    os.unlink(audio_path)
    
    return {
        "ok": True,
        "transcripcion": transcripcion["texto"],
        "datos_extraidos": datos,
        "duracion": transcripcion["duracion"],
        "confianza": transcripcion["confianza"],
    }
```

## Prueba

```bash
# Simular subida de audio
curl -X POST http://localhost:8000/api/upload-audio \
  -F "audio=@/ruta/al/audio.m4a" \
  -F "paciente_cc=1193143688"
```
