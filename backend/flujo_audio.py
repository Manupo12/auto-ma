"""
Módulo de transcripción de audio y extracción de datos cualitativos.
Usa Deepgram nova-2 con speaker diarization (Speaker 0=Sandra, Speaker 1=Paciente).
"""

import os
import re
import requests

# Cargar .env si existe
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"


def transcribir_audio(audio_path: str) -> dict:
    """
    Transcribe un archivo de audio usando Deepgram nova-2.

    Returns:
        {
            "texto": str,
            "duracion": float,
            "confianza": float,
            "segmentos": [{"texto": str, "inicio": float, "fin": float, "hablante": int}]
        }
    """
    if not DEEPGRAM_API_KEY:
        raise ValueError("DEEPGRAM_API_KEY no está configurado en .env")

    ext = os.path.splitext(audio_path)[1].lower()
    content_type_map = {
        ".m4a": "audio/m4a",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
    }
    content_type = content_type_map.get(ext, "audio/mpeg")

    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": content_type,
    }

    params = {
        "language": "es",
        "punctuate": "true",
        "diarize": "true",
        "model": "nova-2",
    }

    with open(audio_path, "rb") as f:
        response = requests.post(DEEPGRAM_URL, headers=headers, params=params, data=f)

    if response.status_code != 200:
        raise Exception(f"Deepgram error {response.status_code}: {response.text}")

    data = response.json()
    resultados = data.get("results", {})
    canales = resultados.get("channels", [{}])
    alternativas = canales[0].get("alternatives", [{}])

    transcripcion = alternativas[0].get("transcript", "")
    confianza = alternativas[0].get("confidence", 0.0)
    duracion = resultados.get("metadata", {}).get("duration", 0.0)

    palabras = []
    for word in alternativas[0].get("words", []):
        palabras.append({
            "texto": word.get("punctuated_word", word.get("word", "")),
            "inicio": word.get("start", 0.0),
            "fin": word.get("end", 0.0),
            "hablante": word.get("speaker", 0),
        })
    segmentos = _agrupar_palabras_en_frases(palabras)

    return {
        "texto": transcripcion,
        "duracion": duracion,
        "confianza": confianza,
        "segmentos": segmentos,
    }


def _agrupar_palabras_en_frases(palabras: list) -> list:
    """Agrupa palabras individuales de Deepgram en frases por hablante y pausa."""
    if not palabras:
        return []
    frases = []
    frase = {
        "palabras": [palabras[0]["texto"]],
        "inicio": palabras[0]["inicio"],
        "fin": palabras[0]["fin"],
        "hablante": palabras[0]["hablante"],
    }
    for p in palabras[1:]:
        mismo_hablante = p["hablante"] == frase["hablante"]
        pausa_corta = (p["inicio"] - frase["fin"]) < 2.0
        if mismo_hablante and pausa_corta:
            frase["palabras"].append(p["texto"])
            frase["fin"] = p["fin"]
        else:
            frases.append({
                "texto": " ".join(frase["palabras"]),
                "inicio": frase["inicio"],
                "fin": frase["fin"],
                "hablante": frase["hablante"],
            })
            frase = {
                "palabras": [p["texto"]],
                "inicio": p["inicio"],
                "fin": p["fin"],
                "hablante": p["hablante"],
            }
    frases.append({
        "texto": " ".join(frase["palabras"]),
        "inicio": frase["inicio"],
        "fin": frase["fin"],
        "hablante": frase["hablante"],
    })
    return frases


def extraer_datos_cualitativos(transcripcion: str) -> dict:
    """
    Extrae campos clínicos del texto transcrito.

    Returns dict con: metodologia, proceso_productivo, apreciacion_trabajador,
    estandares_productividad, materiales, peligros, tareas_criticas,
    concepto_desempeno, recomendaciones.
    """
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

    materiales_keywords = [
        "gancho", "pala", "barra", "tubo", "martillo", "destornillador",
        "guantes", "casco", "gafas", "botas", "epp", "herramienta",
    ]
    for kw in materiales_keywords:
        if kw in texto:
            datos["materiales"].append({"nombre": kw.capitalize(), "estado": "Bueno"})

    peligros_keywords = [
        "biomecánico", "ergonómico", "caída", "ruido", "químico",
        "psicosocial", "eléctrico", "mecánico", "carga", "repetitivo",
    ]
    for kw in peligros_keywords:
        if kw in texto:
            datos["peligros"].append({
                "nombre": f"Peligro {kw.capitalize()}",
                "descripcion": f"Asociado a {kw}",
                "control": "",
                "recomendacion": "",
            })

    return datos


def filtrar_segmentos_clinicos(segmentos: list) -> list:
    """
    Filtra segmentos irrelevantes (saludos, pausas, ruido < 15 chars).
    Retorna solo segmentos con contenido clínico relevante.
    """
    BASURA = {
        "buenos días", "buenas tardes", "cómo está", "cómo estás",
        "gracias", "chao", "listo", "entonces", "eh", "mmm",
        "respire", "siéntese", "párese", "tosa",
    }

    PALABRAS_CLAVE = {
        "metodología", "método", "procedimiento", "valoración", "desempeño",
        "cargo", "funciones", "tareas", "actividad", "materiales", "herramientas",
        "equipos", "peligros", "riesgo", "recomendación", "concepto", "conclusión",
        "diagnóstico", "síntoma", "dolor", "limitación", "jornada", "horario",
        "ritmo", "descanso", "turno", "levantar", "cargar", "empujar", "halar",
        "movimiento", "postura", "bípeda", "sedente", "peso", "kilo",
    }

    filtrados = []
    for seg in segmentos:
        txt = seg.get("texto", "").strip()
        if len(txt) < 15:
            continue
        txt_lower = txt.lower()
        if any(b in txt_lower for b in BASURA):
            continue
        if any(kw in txt_lower for kw in PALABRAS_CLAVE):
            filtrados.append(seg)

    return filtrados


def calcular_confianza_campo(fragmento: str, palabras_clave_campo: list) -> int:
    """
    Calcula score de confianza (0-100) para un campo extraído del audio.
    """
    score = 0
    if len(fragmento) > 30:
        score += 40
    if any(kw in fragmento.lower() for kw in palabras_clave_campo):
        score += 30
    if fragmento.endswith(".") or fragmento.endswith(","):
        score += 20
    return min(score, 100)
