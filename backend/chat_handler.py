"""
Chat inteligente de Tomy — Conectado al LLM real (DeepSeek v4 vía OpenCode).
Misma conciencia que Hermes/Tomy en Telegram y CLI.
"""
import os
import json
import requests
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Mismo proveedor que Hermes
API_KEY = os.getenv("OPENCODE_GO_API_KEY", "")
BASE_URL = os.getenv("OPENCODE_GO_BASE_URL", "https://opencode.ai/zen/go/v1")
MODEL = os.getenv("LLM_MODEL", "deepseek-v4-pro")

WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", Path.home() / "rilo-workspace"))

SYSTEM_PROMPT = """Eres Tomy, el asistente virtual de Sandra, una fisioterapeuta de RILO SAS (Rehabilitación Integral Laboral y Ocupacional) en Colombia.

Tu trabajo es ayudar a Sandra con:
- Completar y organizar los 7 formatos clínicos de ARL Positiva
- Buscar archivos en su carpeta de trabajo
- Explicar procedimientos de forma SIMPLE (Sandra es mayor, lenguaje claro, cero jerga técnica)
- Ser paciente, cálido y amable siempre

LOS 7 FORMATOS:
1. Análisis de Exigencias Ocupacionales
2. Carta de Medidas de Intervención
3. Carta de Recomendaciones
4. Cierre de Caso
5. Citación de Empresas
6. Prueba de Trabajo
7. Valoración del Desempeño Ocupacional

REGLAS:
- Responde en español colombiano, cálido y sencillo
- NO uses palabras técnicas (API, endpoint, JSON, servidor, base de datos)
- Si no puedes hacer algo, dile qué necesitas (ej: "necesito la cédula del paciente")
- Para completar documentos: pide nombre del paciente, cédula, y formato
- Sé breve pero completo. Sandra prefiere respuestas directas.
- Usa emojis de vez en cuando 📄✨
- Si no sabes algo, sé honesto. No inventes información clínica.
- Recuerda: Sandra tiene los documentos en su carpeta de Windows y tú puedes buscarlos."""

# Contexto del workspace (se actualiza con cada mensaje si es posible)
WORKSPACE_CONTEXT = ""


def _actualizar_contexto_workspace():
    """Actualiza el contexto con lo que hay en el workspace."""
    global WORKSPACE_CONTEXT
    try:
        if WORKSPACE_DIR.exists():
            carpetas = []
            for item in sorted(WORKSPACE_DIR.iterdir()):
                if item.is_dir() and not item.name.startswith('.'):
                    num_archivos = sum(1 for _ in item.rglob('*') if _.is_file())
                    carpetas.append(f"  📁 {item.name}/ ({num_archivos} archivos)")
            if carpetas:
                WORKSPACE_CONTEXT = "Carpeta de trabajo actual:\n" + "\n".join(carpetas[:15])
    except:
        pass


def _llamar_llm(mensaje: str, paciente_cc: str = "") -> str:
    """Llama al LLM real (DeepSeek v4 vía OpenCode)."""
    if not API_KEY:
        return (
            "⚠️ *Aviso:* No tengo conexión con mi cerebro principal. "
            "Dile a Manu que configure OPENCODE_GO_API_KEY en el archivo .env.\n\n"
            "Mientras tanto, puedo ayudarte con tareas básicas. ¿Qué necesitas? 😊"
        )
    
    _actualizar_contexto_workspace()
    
    user_msg = mensaje
    if WORKSPACE_CONTEXT:
        user_msg = f"{mensaje}\n\n[{WORKSPACE_CONTEXT}]"
    if paciente_cc:
        user_msg = f"{mensaje}\n\n[CC del paciente: {paciente_cc}]"
    
    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0.7,
                "max_tokens": 500,
            },
            timeout=30,
        )
        
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        else:
            return f"🤔 Lo siento Sandra, tuve un problema para pensar (error {resp.status_code}). ¿Puedes intentar de nuevo?"
            
    except requests.exceptions.Timeout:
        return "⏰ Me tomó mucho tiempo. ¿Me repites la pregunta más corta?"
    except Exception as e:
        return f"❌ Algo falló en mi conexión. Intenta de nuevo en un momento."


def procesar_mensaje(mensaje: str, paciente_cc: str = "") -> dict:
    """
    Procesa un mensaje del chat y devuelve respuesta usando el LLM real.
    """
    if not mensaje.strip():
        return {"contenido": "¿En qué te ayudo, Sandra? 😊", "accion": None}
    
    respuesta = _llamar_llm(mensaje, paciente_cc)
    
    # Detectar si la respuesta sugiere una acción
    accion = None
    if any(p in mensaje.lower() for p in ["completa", "termina", "documento", "formato"]):
        accion = "documento"
    elif any(p in mensaje.lower() for p in ["busca", "archivo", "carpeta"]):
        accion = "buscar"
    
    return {
        "contenido": respuesta,
        "accion": accion,
    }
