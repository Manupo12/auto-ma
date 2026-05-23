"""
Paso 5: Síntesis maestra — LLM razonador con contexto cruzado.

Compone contexto a partir de:
  - Transcripción del audio (chunked si es necesario)
  - Datos verificados de portales (Medifolios + Positiva)
  - Notas crudas del workspace
  - Formatos antiguos subidos como referencia

Llama al LLM razonador (deepseek-v4-pro) en subprocess aislado vía
lote_worker --tipo sintetizar para evitar OOM.

Si el contexto excede 30K chars, hace resumen progresivo antes.
"""
import json
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List


def _log(msg: str):
    print(f"[SINTESIS {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _formatear_portales(datos: dict) -> str:
    if not datos or datos.get("_vacio"):
        return "[NO HAY DATOS VERIFICADOS DE PORTALES]"
    medi = datos.get("medifolios", {})
    pos = datos.get("positiva", {})
    discrepancias = datos.get("_meta", {}).get("discrepancias", [])
    bloques = ["📋 DATOS VERIFICADOS PORTALES:"]
    if medi:
        nombre = " ".join([medi.get("nombre1", ""), medi.get("apellido1", "")]).strip()
        if nombre: bloques.append(f"  Paciente: {nombre}")
        if medi.get("telefono"): bloques.append(f"  Teléfono: {medi['telefono']}")
        if medi.get("direccion"): bloques.append(f"  Dirección: {medi['direccion']}")
        if medi.get("siniestro_medi"): bloques.append(f"  Siniestro (Medi): {medi['siniestro_medi']}")
    if pos.get("siniestros"):
        for s in pos["siniestros"][:2]:
            bloques.append(f"  Siniestro (Pos): {s.get('id','?')} | {s.get('fecha','?')} | {s.get('diagnostico','?')[:50]}")
    if discrepancias:
        bloques.append("\n⚠️ DISCREPANCIAS DETECTADAS:")
        for d in discrepancias:
            bloques.append(f"  - {d.get('campo','?')}: Medi={d.get('medifolios','?')} vs Pos={d.get('positiva','?')}")
    return "\n".join(bloques)


def _formatear_notas(notas: list) -> str:
    if not notas:
        return "[NO HAY NOTAS CRUDAS]"
    bloques = [f"📝 NOTAS CRUDAS ({len(notas)} archivos):"]
    for n in notas[:5]:
        bloques.append(f"\n--- {n['nombre']} ---\n{n['contenido']}")
    return "\n".join(bloques)


def _formatear_formatos_subidos(formatos: list) -> str:
    if not formatos:
        return ""
    bloques = [f"📄 FORMATOS DE REFERENCIA SUBIDOS POR SANDRA ({len(formatos)}):"]
    for f in formatos:
        bloques.append(f"\n--- {f['nombre']} ---\n{f['contenido']}")
    return "\n".join(bloques)


def _resumir_si_largo(texto: str, max_chars: int = 30000) -> str:
    if len(texto) <= max_chars:
        return texto
    inicio_chars = max_chars * 4 // 10
    fin_chars = max_chars * 4 // 10
    return (
        texto[:inicio_chars]
        + f"\n\n[...RESUMIDO: {len(texto) - inicio_chars - fin_chars} chars omitidos del medio...]\n\n"
        + texto[-fin_chars:]
    )


def _componer_contexto(transcripcion, datos_portales, notas_crudas, formatos_subidos, paciente_cc) -> str:
    transcripcion_texto = transcripcion.get("texto", "")
    if len(transcripcion_texto) > 20000:
        transcripcion_texto = _resumir_si_largo(transcripcion_texto, 20000)
    bloques = [
        f"═══ PACIENTE CC: {paciente_cc} ═══\n",
        "🎙️ TRANSCRIPCIÓN DEL AUDIO:",
        transcripcion_texto,
        "",
        _formatear_portales(datos_portales),
        "",
        _formatear_notas(notas_crudas),
        "",
        _formatear_formatos_subidos(formatos_subidos),
    ]
    return "\n".join(bloques)


PROMPT_USUARIO_SINTESIS = """Eres Tomy, asistente clínico EXPERTO de Sandra (RILO SAS, ARL Positiva Colombia).

Tu tarea AHORA: a partir del contexto cruzado abajo (audio + portales + notas + formatos), produce un JSON estructurado con TODOS los datos clínicos necesarios para generar los 7 formatos oficiales.

Devuelve SOLO un bloque JSON válido entre ```json ... ```. Estructura esperada:

```json
{
  "paciente": {"documento": "...", "nombre": "...", "edad": "...", "telefono": "...", "direccion": "...", "email": "...", "eps_ips": "...", "afp": "...", "ocupacion": "..."},
  "empresa": {"nombre": "...", "nit": "...", "cargo": "..."},
  "siniestro": {"id_siniestro": "...", "fecha_evento": "...", "tipo_evento": "...", "diagnostico_cie10": "...", "descripcion": "..."},
  "estado_caso": "NUEVO|SEGUIMIENTO|CIERRE|PRUEBA_TRABAJO",
  "metodologia": "...",
  "proceso_productivo": "...",
  "apreciacion_trabajador": "...",
  "materiales": [{"nombre":"...","estado":"..."}],
  "peligros": [{"nombre":"...","descripcion":"...","recomendacion":"..."}],
  "tareas_criticas": [{"tarea":"...","observacion":"...","desempeno":"..."}],
  "concepto_desempeno": "...",
  "recomendaciones": {"trabajador":"...","empresa":"..."},
  "logros": "...",
  "obstaculos": "...",
  "_meta": {
    "campos_faltantes": ["lista de campos críticos sin info"],
    "discrepancias": ["resoluciones tomadas"],
    "confianza_global": 0.0-1.0
  }
}
```

REGLAS:
- Si un dato está en portales Y en audio Y coinciden → úsalo.
- Si discrepan → prevalece portal (es fuente oficial). Marca en _meta.discrepancias.
- Si solo está en audio (subjetivo) → úsalo y marca confianza_global menor.
- Si falta dato crítico → escribe "[FALTA: descripción específica]" y agrégalo a campos_faltantes.
- NUNCA inventes datos clínicos. Si no sabes, di [FALTA].
- Español colombiano clínico."""


def sintetizar(transcripcion: Dict, datos_portales: Dict, notas_crudas: List, formatos_subidos: List, paciente_cc: str) -> Dict:
    """Llama a lote_worker --tipo sintetizar con el contexto cruzado."""
    contexto = _componer_contexto(transcripcion, datos_portales, notas_crudas, formatos_subidos, paciente_cc)
    _log(f"Contexto compuesto: {len(contexto)} chars")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
        tmp.write(contexto)
        contexto_file = tmp.name

    modelo = os.getenv("LLM_MODEL_SINTESIS", "deepseek-v4-pro")

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "backend.lote_worker",
             "--tipo", "sintetizar",
             "--modelo", modelo,
             "--mensaje", PROMPT_USUARIO_SINTESIS,
             "--contexto-file", contexto_file,
             "--cc", paciente_cc],
            capture_output=True, text=True,
            timeout=900,
            cwd=str(Path(__file__).parent.parent.parent),
        )
    finally:
        try: os.unlink(contexto_file)
        except Exception: pass

    if proc.returncode != 0:
        _log(f"lote_worker falló: {proc.stderr[:500]}")
        return {"ok": False, "error": proc.stderr[:500]}

    try:
        resultado = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "stdout no es JSON"}

    respuesta_texto = resultado.get("respuesta", "")
    _log(f"Síntesis: {resultado.get('tokens', {})} tokens en {resultado.get('tiempo_s')}s")

    import re
    match = re.search(r'```json\s*(\{.*?\})\s*```', respuesta_texto, re.DOTALL)
    datos_clinicos = None
    if match:
        try:
            datos_clinicos = json.loads(match.group(1))
        except json.JSONDecodeError as e:
            _log(f"JSON clinico inválido: {e}")

    return {
        "ok": True,
        "respuesta_completa": respuesta_texto,
        "datos_clinicos": datos_clinicos,
        "tokens": resultado.get("tokens", {}),
        "tiempo_s": resultado.get("tiempo_s"),
    }


def ejecutar(transcripcion: Dict, datos_portales: Dict, notas_crudas: List, formatos_subidos: List, paciente_cc: str) -> dict:
    return sintetizar(transcripcion, datos_portales, notas_crudas, formatos_subidos, paciente_cc)
