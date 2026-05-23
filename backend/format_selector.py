"""
Selector de formato — capa ② del flujo v2.

Decide cuáles de los 7 formatos clínicos generar según el estado del caso.
También permite forzar un formato específico si el usuario lo pide explícitamente.

Estados de caso:
  - NUEVO:        Caso recién reportado, primera intervención
  - SEGUIMIENTO:  Ya tiene análisis previo, en rehabilitación activa
  - CIERRE:       Caso listo para cerrar, última valoración
  - PRUEBA_TRABAJO: Evaluación directa en puesto de trabajo

Detección automática:
  Si no se especifica estado_caso, se infiere de los datos disponibles:
  - ¿Tiene fecha de valoración previa? → SEGUIMIENTO o CIERRE
  - ¿Tiene concepto de cierre? → CIERRE
  - ¿Es primera visita? → NUEVO

Uso:
  from backend.format_selector import seleccionar_formatos

  formatos = seleccionar_formatos(datos, estado="NUEVO")
  # → ['citacion_empresas', 'analisis_exigencias', 'carta_medidas']

  formatos = seleccionar_formatos(datos)  # auto-detectar
"""

from typing import List, Optional, Dict, Any
from enum import Enum


class EstadoCaso(str, Enum):
    NUEVO = "NUEVO"
    SEGUIMIENTO = "SEGUIMIENTO"
    CIERRE = "CIERRE"
    PRUEBA_TRABAJO = "PRUEBA_TRABAJO"


# ═══════════════════════════════════════════════════════════════════════════
# MAPA ESTADO → FORMATOS (en orden de generación)
# ═══════════════════════════════════════════════════════════════════════════

ESTADO_FORMATOS: Dict[EstadoCaso, List[str]] = {
    EstadoCaso.NUEVO: [
        "citacion_empresas",     # 5. Notificar a la empresa
        "analisis_exigencias",   # 1. Análisis del puesto de trabajo
        "carta_medidas",         # 2. Medidas preventivas iniciales
    ],
    EstadoCaso.SEGUIMIENTO: [
        "valoracion_desempeno",  # 7. Valoración de desempeño actual
        "carta_medidas",         # 2. Medidas actualizadas
        "carta_recomendaciones", # 3. Recomendaciones de reintegro
    ],
    EstadoCaso.CIERRE: [
        "valoracion_desempeno",  # 7. Valoración final
        "cierre_caso",           # 4. Cierre de rehabilitación
        "carta_recomendaciones", # 3. Recomendaciones post-cierre
    ],
    EstadoCaso.PRUEBA_TRABAJO: [
        "prueba_trabajo",        # 6. Prueba en sitio
        # + formatos del estado base
    ],
}

# Si es PRUEBA_TRABAJO, se agregan estos formatos adicionales según estado base
PRUEBA_TRABAJO_EXTRAS: Dict[EstadoCaso, List[str]] = {
    EstadoCaso.NUEVO: ["analisis_exigencias", "carta_medidas"],
    EstadoCaso.SEGUIMIENTO: ["valoracion_desempeno", "carta_recomendaciones"],
    EstadoCaso.CIERRE: ["valoracion_desempeno", "cierre_caso"],
}


# ═══════════════════════════════════════════════════════════════════════════
# NOMBRES LEGIBLES
# ═══════════════════════════════════════════════════════════════════════════

FORMATO_NOMBRES = {
    "analisis_exigencias": "1. Análisis de Exigencias / Homologación",
    "carta_medidas": "2. Carta de Medidas Preventivas",
    "carta_recomendaciones": "3. Carta de Recomendaciones / Reincorporación",
    "cierre_caso": "4. Certificado de Rehabilitación / Cierre de Caso",
    "citacion_empresas": "5. Citación de Empresas",
    "prueba_trabajo": "6. Prueba de Trabajo",
    "valoracion_desempeno": "7. Valoración del Desempeño Ocupacional",
}


# ═══════════════════════════════════════════════════════════════════════════
# DETECCIÓN AUTOMÁTICA DE ESTADO
# ═══════════════════════════════════════════════════════════════════════════

def _get_nested(data: dict, path: str) -> Any:
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() in ("", "[VERIFICAR]"):
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def detectar_estado(datos: dict) -> EstadoCaso:
    """
    Infiere el estado del caso a partir de los datos disponibles.
    
    Reglas:
    1. Si tiene datos de prueba de trabajo (tareas_criticas con descripcion +
       consulta.metodologia que mencione "Prueba de Trabajo") → PRUEBA_TRABAJO
    2. Si tiene concepto integral o fecha de cierre → CIERRE
    3. Si tiene valoración previa (resultados_valoracion) → SEGUIMIENTO
    4. Sino → NUEVO
    
    También respeta el campo explícito 'estado_caso' si existe.
    """
    # 1. Campo explícito
    estado_explicito = _get_nested(datos, "estado_caso")
    if estado_explicito and not _is_empty(estado_explicito):
        estado_upper = estado_explicito.upper().replace(" ", "_")
        for e in EstadoCaso:
            if e.value == estado_upper:
                return e
        # Intentar mapeo flexible
        mapeo = {
            "NUEVO": EstadoCaso.NUEVO,
            "SEGUIMIENTO": EstadoCaso.SEGUIMIENTO,
            "CIERRE": EstadoCaso.CIERRE,
            "PRUEBA": EstadoCaso.PRUEBA_TRABAJO,
            "PT": EstadoCaso.PRUEBA_TRABAJO,
        }
        for key, val in mapeo.items():
            if key in estado_upper:
                return val

    # 2. ¿Prueba de trabajo?
    metodologia = str(_get_nested(datos, "consulta.metodologia") or "").upper()
    concepto = str(_get_nested(datos, "consulta.concepto_desempeno") or "").upper()
    tipo_estudio = str(_get_nested(datos, "visita.tipo_estudio") or "").upper()

    es_prueba = (
        "PRUEBA DE TRABAJO", "prueba de trabajo", "prueba funcional", "prueba laboral", "evaluacion de desempe", "prueba en el trabajo", "prueba en puesto" in metodologia
        or "PRUEBA DE TRABAJO", "prueba de trabajo", "prueba funcional", "prueba laboral", "evaluacion de desempe", "prueba en el trabajo", "prueba en puesto" in concepto
        or "PRUEBA DE TRABAJO", "prueba de trabajo", "prueba funcional", "prueba laboral", "evaluacion de desempe", "prueba en el trabajo", "prueba en puesto" in tipo_estudio
        or "PT" == tipo_estudio.strip()
    )
    if es_prueba:
        # Determinar estado base para extras
        return EstadoCaso.PRUEBA_TRABAJO

    # 3. ¿Cierre?
    concepto_integral = _get_nested(datos, "rehabilitacion.concepto_integral")
    forma_integracion = _get_nested(datos, "rehabilitacion.forma_integracion")
    if not _is_empty(concepto_integral) or not _is_empty(forma_integracion):
        texto_concepto = str(concepto_integral or "").upper()
        texto_forma = str(forma_integracion or "").upper()
        if "CIERRE" in texto_concepto or "CIERRE" in texto_forma or "FINALIZA" in texto_concepto:
            return EstadoCaso.CIERRE

    # 4. ¿Seguimiento? (tiene valoración previa)
    resultados = _get_nested(datos, "consulta.resultados_valoracion")
    programa_rhi = _get_nested(datos, "consulta.programa_rhi")
    tratamiento = _get_nested(datos, "consulta.tratamiento_recibido")

    if not _is_empty(resultados) or not _is_empty(programa_rhi) or not _is_empty(tratamiento):
        return EstadoCaso.SEGUIMIENTO

    # 5. Default: NUEVO
    return EstadoCaso.NUEVO


# ═══════════════════════════════════════════════════════════════════════════
# SELECTOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

def seleccionar_formatos(
    datos: dict,
    estado: Optional[str] = None,
    forzar: Optional[List[str]] = None,
) -> List[str]:
    """
    Determina qué formatos generar.

    Args:
        datos: JSON con los datos del paciente/caso
        estado: Estado explícito ('NUEVO', 'SEGUIMIENTO', 'CIERRE', 'PRUEBA_TRABAJO').
                Si es None, se auto-detecta.
        forzar: Lista de formatos específicos a generar (ignora la lógica de estado).
                Útil cuando Sandra pide explícitamente "solo la citación".

    Returns:
        Lista ordenada de nombres de formato a generar.
    """
    # Si se fuerzan formatos, usar esos
    if forzar:
        validos = []
        for f in forzar:
            f_clean = f.strip().lower().replace(" ", "_")
            if f_clean in FORMATO_NOMBRES:
                validos.append(f_clean)
        if validos:
            return validos

    # Determinar estado
    if estado:
        estado_upper = estado.upper().replace(" ", "_")
        try:
            estado_obj = EstadoCaso(estado_upper)
        except ValueError:
            estado_obj = detectar_estado(datos)
    else:
        estado_obj = detectar_estado(datos)

    # Obtener formatos base para el estado
    formatos = list(ESTADO_FORMATOS.get(estado_obj, []))

    # Si es PRUEBA_TRABAJO, agregar extras según estado base
    if estado_obj == EstadoCaso.PRUEBA_TRABAJO:
        estado_base = detectar_estado(datos)
        if estado_base == EstadoCaso.PRUEBA_TRABAJO:
            estado_base = EstadoCaso.NUEVO  # fallback
        extras = PRUEBA_TRABAJO_EXTRAS.get(estado_base, [])
        for extra in extras:
            if extra not in formatos:
                formatos.append(extra)

    return formatos


def seleccionar_con_contexto(
    datos: dict,
    estado: Optional[str] = None,
    forzar: Optional[List[str]] = None,
) -> dict:
    """
    Versión completa que retorna estado detectado + formatos + metadata.
    Ideal para mostrar a la usuaria.
    """
    formatos = seleccionar_formatos(datos, estado=estado, forzar=forzar)

    if estado:
        estado_obj = estado.upper()
    else:
        estado_obj = detectar_estado(datos).value

    # Nombre del paciente para el mensaje
    paciente = _get_nested(datos, "paciente.nombre") or "Paciente sin nombre"

    return {
        "estado_detectado": estado_obj,
        "paciente": paciente,
        "formatos": formatos,
        "nombres_formatos": [FORMATO_NOMBRES.get(f, f) for f in formatos],
        "total": len(formatos),
    }


# ═══════════════════════════════════════════════════════════════════════════
# PRUEBA
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Caso nuevo (sin historial)
    datos_nuevo = {
        "paciente": {"nombre": "LAURA ROJAS ZUÑIGA", "documento": "36184789"},
        "siniestro": {"id_siniestro": "503463870", "fecha_evento": "10/01/2026"},
        "empresa": {"nombre": "EMPRESA ABC"},
        "laboral": {"cargo": "AUXILIAR ADMINISTRATIVO"},
        "consulta": {},
    }

    # Caso seguimiento (con historial)
    datos_seguimiento = {
        **datos_nuevo,
        "consulta": {
            "resultados_valoracion": "Servidora con evolución favorable...",
            "programa_rhi": "Fortalecimiento muscular, manejo de cargas",
        },
    }

    # Caso cierre
    datos_cierre = {
        **datos_nuevo,
        "rehabilitacion": {
            "concepto_integral": "Se finaliza proceso de rehabilitación integral...",
            "forma_integracion": "Reintegro sin modificaciones",
        },
    }

    # Prueba
    datos_prueba = {
        **datos_nuevo,
        "consulta": {
            "metodologia": "La metodología utilizada para la Prueba de Trabajo...",
        },
    }

    print("=== DETECCIÓN DE ESTADO ===")
    for nombre, datos in [
        ("NUEVO", datos_nuevo),
        ("SEGUIMIENTO", datos_seguimiento),
        ("CIERRE", datos_cierre),
        ("PRUEBA_TRABAJO", datos_prueba),
    ]:
        estado = detectar_estado(datos)
        formatos = seleccionar_formatos(datos)
        print(f"\n{nombre}: estado={estado.value}")
        print(f"  Formatos: {formatos}")

    # Probar seleccionar_con_contexto
    print("\n=== SELECCIÓN CON CONTEXTO ===")
    ctx = seleccionar_con_contexto(datos_nuevo)
    print(f"Estado: {ctx['estado_detectado']}")
    print(f"Paciente: {ctx['paciente']}")
    print(f"Formatos ({ctx['total']}):")
    for f in ctx['nombres_formatos']:
        print(f"  - {f}")

    # Probar forzar formatos
    print("\n=== FORZAR FORMATOS ===")
    forzados = seleccionar_formatos(datos_nuevo, forzar=["cierre_caso", "carta_medidas"])
    print(f"Forzados: {forzados}")
