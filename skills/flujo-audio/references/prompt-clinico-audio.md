# Prompt de Extracción Clínica para Audio Transcrito

Este prompt se usa para extraer datos estructurados de la transcripción de audio
de una cita entre Sandra (fisioterapeuta) y el paciente. Se pasa al modelo LLM
junto con la transcripción completa.

## Prompt

```
Eres un asistente clínico especializado en rehabilitación laboral.
Del siguiente fragmento de consulta entre una fisioterapeuta (Sandra) y un paciente, extrae ÚNICAMENTE los datos solicitados.

REGLAS ABSOLUTAS:
1. Si el dato NO se menciona explícitamente, devuelve null. NUNCA inventes.
2. Usa el lenguaje EXACTO del paciente. No reformatees ni resumas.
3. Si el paciente dice "me duele aquí cuando levanto el brazo", escribe ESO, no "limitación funcional en abducción".
4. Distingue entre la voz de Sandra (Speaker 0) y el paciente (Speaker 1). Los datos del paciente vienen del Speaker 1.
5. Si un dato es ambiguo, márcalo con confianza baja.

CAMPOS A EXTRAER:
- cargo_actual: El trabajo que hace actualmente
- funciones_principales: Lista de tareas que describió (separadas por " / ")
- herramientas_trabajo: Objetos o máquinas que mencionó usar
- limitaciones_funcionales: Qué dijo que no puede hacer o le duele hacer
- horario_laboral: Turnos, horas, días que trabaja
- descripcion_accidente: Cómo ocurrió el accidente según el paciente
- sintomatologia_actual: Dónde duele, cuánto, desde cuándo
- historia_ocupacional: Trabajos anteriores mencionados
- contexto_familiar: Personas que dependen de él, situación económica
- actividades_vida_diaria: Cómo se viste, come, duerme, se moviliza

FRAGMENTO DE CONSULTA:
{transcripcion}

Responde en formato JSON. Campos no mencionados = null.
```

## Confianza por campo extraído

Cada campo recibe un score de confianza (0-100) basado en:

| Factor | Peso | Ejemplo |
|--------|------|---------|
| Frase explícita y completa | +40 | "trabajo de lunes a viernes de 7 a 3" |
| Cerca de palabras clave del campo | +30 | "cargo" cerca de "obrero" |
| Frase completa (termina con .?!) | +20 | "soy obrero de tratamiento de roca." |
| Múltiples menciones | +10 | El dato aparece 2+ veces |

Semáforo:
- 🟢 Verde (≥80): Dato confiable, usar directamente
- 🟡 Amarillo (50-79): Dato probable, mostrar a Sandra para confirmar
- 🔴 Rojo (<50): Dato dudoso, requiere revisión manual

## Speaker Diarization

Deepgram (nova-2, `diarize=true`) identifica automáticamente:
- **Speaker 0**: Sandra (la fisioterapeuta) — preguntas, instrucciones, contexto clínico
- **Speaker 1**: Paciente — respuestas, descripciones, datos cualitativos

Para los formatos clínicos, interesan PRINCIPALMENTE los segmentos del Speaker 1 (paciente).
Los segmentos de Sandra se usan para entender el contexto de la pregunta.

## Pipeline de filtrado

1. Deepgram transcribe → texto completo + segmentos por hablante
2. Filtrar basura: saludos, pausas, ruido
3. Separar por hablante (Speaker 0/1)
4. Extraer campos con prompt clínico (solo de Speaker 1)
5. Calcular confianza por campo
6. Mostrar en dashboard con semáforo
7. Sandra confirma/corrige → se guarda la corrección para aprendizaje
