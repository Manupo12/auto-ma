"""
Resolver de correcciones conversacionales.

Sandra escribe en el chat algo como "el siniestro no es X es Y", y este
módulo identifica:
  - Qué campo en la estructura clínica
  - Cuál es el nuevo valor
  - Cuál era el valor anterior (para validar)
  - Nivel de confianza

Usa LLM clasificador (deepseek-v4-flash, sin razonamiento).
"""
import json
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional


def _log(msg: str):
    print(f"[CORRECTION {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


PROMPT_CLASIFICADOR = """Eres Tomy. Sandra acaba de escribirte una corrección sobre un paciente.

Tu tarea: identificar QUÉ campo de la estructura clínica está corrigiendo, cuál es el valor nuevo,
y opcionalmente cuál era el valor anterior. Devuelve SOLO un JSON entre ```json ... ```.

Estructura clínica posible (campos válidos):
  paciente.documento, paciente.nombre, paciente.edad, paciente.telefono, paciente.direccion,
  paciente.email, paciente.eps_ips, paciente.afp, paciente.ocupacion,
  empresa.nombre, empresa.nit, empresa.cargo,
  siniestro.id_siniestro, siniestro.fecha_evento, siniestro.tipo_evento, siniestro.diagnostico_cie10,
  estado_caso,
  metodologia, proceso_productivo, apreciacion_trabajador,
  concepto_desempeno, recomendaciones.trabajador, recomendaciones.empresa,
  logros, obstaculos

Formato salida:
```json
{
  "campo": "siniestro.id_siniestro",
  "valor_nuevo": "503476658",
  "valor_anterior": "503463870",
  "confianza": 0.9,
  "razonamiento": "1 línea"
}
```

Si no logras identificar el campo o el valor, pon confianza < 0.5."""


def _llamar_llm_clasificador(mensaje: str, paciente_cc: str) -> Dict:
    modelo = os.getenv("LLM_MODEL_EXTRACCION", "deepseek-v4-flash")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
        tmp.write(f"Mensaje de Sandra: \"{mensaje}\"\nCC del paciente: {paciente_cc}")
        ctx_file = tmp.name

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "backend.lote_worker",
             "--tipo", "sintetizar",
             "--modelo", modelo,
             "--mensaje", PROMPT_CLASIFICADOR,
             "--contexto-file", ctx_file,
             "--cc", paciente_cc],
            capture_output=True, text=True, timeout=60,
            cwd=str(Path(__file__).parent.parent),
        )
    finally:
        try: os.unlink(ctx_file)
        except Exception as e: _log(f"No se pudo eliminar temp {ctx_file}: {e}")

    if proc.returncode != 0:
        return {"campo": None, "confianza": 0, "error": proc.stderr[:200]}

    try:
        resultado = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        return {"campo": None, "confianza": 0, "error": str(e)}
    respuesta = resultado.get("respuesta", "")

    import re
    match = re.search(r'```json\s*(\{.*?\})\s*```', respuesta, re.DOTALL)
    if not match:
        return {"campo": None, "confianza": 0, "error": "no JSON"}

    return json.loads(match.group(1))


def interpretar_correccion(mensaje: str, paciente_cc: str) -> Dict:
    """Interpreta el mensaje y devuelve dict {campo, valor_nuevo, valor_anterior, confianza}."""
    return _llamar_llm_clasificador(mensaje, paciente_cc)
