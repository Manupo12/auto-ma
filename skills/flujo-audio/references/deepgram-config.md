# Configuración y Uso de Deepgram para Transcripción de Audio

## API Key
```
DEEPGRAM_API_KEY=3888b515e3e95415835ff6df2b4a0c283450500d
```

## Parámetros óptimos para citas clínicas
```python
params = {
    "language": "es",           # Español
    "model": "nova-2",          # Modelo más preciso
    "punctuate": "true",        # Puntuación automática
    "diarize": "true",          # Identificar hablantes (Speaker 0 = Sandra, Speaker 1 = Paciente)
    "utterances": "true",       # Agrupar por intervención
    "smart_format": "true",     # Formateo inteligente
}
```

## Estructura de respuesta
```json
{
  "results": {
    "channels": [{
      "alternatives": [{
        "transcript": "texto completo",
        "confidence": 0.95,
        "words": [{
          "word": "siniestro",
          "start": 1.2,
          "end": 1.8,
          "speaker": 0,
          "punctuated_word": "siniestro."
        }]
      }]
    }],
    "metadata": {
      "duration": 124.5,
      "channels": 1
    }
  }
}
```

## Filtrado de audio
El audio de cita contiene mucha información irrelevante (saludos, pausas, ruido ambiente). Pipeline:

1. **Diarización**: Separar voz de Sandra (Speaker 0) de voz del paciente (Speaker 1)
2. **Filtrado por longitud**: Descartar segmentos < 15 caracteres
3. **Filtrado por palabras clave**: Solo conservar segmentos con vocabulario clínico/laboral
4. **Palabras basura a ignorar**: "buenos días", "cómo está", "gracias", "chao", "listo", "entonces", "eh", "mmm", "respire", "siéntese"

## Palabras clave por campo
- **cargo_actual**: trabajo, cargo, puesto, oficio, laboro, hago
- **funciones**: funciones, tareas, realizo, actividad
- **herramientas**: herramienta, uso, manejo, máquina, equipo
- **limitaciones**: duele, dolor, cuesta, difícil, no puedo, molestia
- **horario**: turno, horario, entrada, salida, lunes, semana
- **accidente**: accidente, pasó, ocurrió, golpe, caída
- **síntomas**: duele, inflamado, hinchado, rojo, molesta

## Confianza por campo (0-100)
- Frase explícita y completa (+40)
- Cerca de palabras clave del campo (+30)
- Frase completa con puntuación (+20)
- Múltiples menciones en la consulta (+10)
- Verde ≥80, Amarillo ≥50, Rojo <50
