#!/usr/bin/env python3
"""
Puente HTTP entre el dashboard y Hermes (Tomy).
Recibe mensajes del chat del dashboard y responde usando el LLM real.

Ejecutar: python chat_bridge.py --port 8765
"""
import os
import sys
import json
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import requests

# Cargar .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Usar el mismo proveedor que Hermes
API_KEY = os.getenv("OPENCODE_GO_API_KEY", "")
BASE_URL = os.getenv("OPENCODE_GO_BASE_URL", "https://opencode.ai/zen/go/v1")
MODEL = os.getenv("LLM_MODEL", "deepseek-v4-pro")

# Personalidad de Tomy para Sandra
SYSTEM_PROMPT = """Eres Tomy, el asistente virtual de Sandra, una fisioterapeuta de RILO SAS (Rehabilitación Integral Laboral y Ocupacional).

Tu trabajo es ayudar a Sandra con:
- Completar y organizar documentos clínicos de ARL Positiva (7 formatos)
- Buscar archivos en su carpeta de trabajo
- Verificar datos de pacientes contra los portales Medifolios y ARL Positiva
- Explicar procedimientos de forma SIMPLE (Sandra es mayor, lenguaje claro, cero jerga técnica)
- Ser paciente y amable siempre

REGLAS:
- Responde en español colombiano, cálido y simple
- NO uses jerga técnica (API, endpoint, JSON, servidor, etc.) a menos que Sandra pregunte
- Si no puedes hacer algo, dile exactamente qué necesitas (ej: "necesito la cédula del paciente")
- Para temas de documentos, pregunta el nombre del paciente y el tipo de formato
- Sé breve pero completo. Sandra prefiere respuestas directas.
- Usa emojis de vez en cuando para ser amigable 📄✨

DATOS DEL SISTEMA:
- La carpeta de trabajo de Sandra está sincronizada y puedes buscar archivos ahí
- Los formatos disponibles son: Análisis de Exigencias, Carta de Medidas, Carta de Recomendaciones, Cierre de Caso, Citación de Empresas, Prueba de Trabajo, Valoración del Desempeño
- Para completar un formato necesitas: cédula del paciente, y acceso a Medifolios/Positiva (o datos que ya tengamos)
"""


class ChatBridgeHandler(BaseHTTPRequestHandler):
    """Maneja peticiones de chat del dashboard."""
    
    def do_POST(self):
        if self.path != "/chat":
            self.send_error(404)
            return
        
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            
            mensaje = data.get("mensaje", "")
            paciente_cc = data.get("paciente_cc", "")
            
            if not mensaje:
                self.send_error(400, "Falta 'mensaje'")
                return
            
            # Construir prompt para el LLM
            user_context = f"Mensaje de Sandra: {mensaje}"
            if paciente_cc:
                user_context += f"\nCédula del paciente: {paciente_cc}"
            
            # Llamar al LLM
            respuesta = self._llamar_llm(user_context)
            
            # Responder
            response = {
                "ok": True,
                "contenido": respuesta,
                "accion": None,
            }
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode())
            
        except Exception as e:
            response = {
                "ok": False,
                "contenido": f"❌ Error interno: {str(e)}",
                "accion": None,
            }
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode())
    
    def do_OPTIONS(self):
        """CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    
    def _llamar_llm(self, mensaje: str) -> str:
        """Llama al LLM (DeepSeek vía OpenCode) con el mismo proveedor que Hermes."""
        if not API_KEY:
            return (
                "⚠️ No tengo conexión con mi cerebro todavía. "
                "Dile a Manu que configure OPENCODE_GO_API_KEY en el .env del puente.\n\n"
                "Mientras tanto, puedo ayudarte con:\n"
                "📄 Completar documentos\n"
                "🔍 Buscar archivos\n"
                "✅ Verificar datos\n\n"
                "¿Qué necesitas?"
            )
        
        try:
            headers = {
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": mensaje},
                ],
                "temperature": 0.7,
                "max_tokens": 500,
            }
            
            resp = requests.post(
                f"{BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                print(f"[Bridge] Error LLM {resp.status_code}: {resp.text[:200]}")
                return "🤔 Lo siento, estoy teniendo problemas para pensar. ¿Puedes intentar de nuevo?"
                
        except requests.exceptions.Timeout:
            return "⏰ Me tomó mucho tiempo pensar. ¿Puedes intentar de nuevo con un mensaje más corto?"
        except Exception as e:
            print(f"[Bridge] Error: {e}")
            return "❌ Ocurrió un error. Intenta de nuevo en un momento."


    def log_message(self, format, *args):
        """Suprimir logs HTTP del servidor."""
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    
    server = HTTPServer((args.host, args.port), ChatBridgeHandler)
    print(f"🧠 Chat Bridge corriendo en http://{args.host}:{args.port}")
    print(f"   Modelo: {MODEL}")
    print(f"   API Key: {'Configurada ✅' if API_KEY else '❌ FALTA'}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Apagando...")
        server.shutdown()


if __name__ == "__main__":
    main()
