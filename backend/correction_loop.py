"""
Loop de corrección post-rechazo — capa ⑤⑥⑦ del flujo v2.

Cuando Sandra recibe un DOCX por Telegram y lo rechaza (o pide cambios),
este módulo:
  ⑥ DETECTA qué falló analizando su mensaje en lenguaje natural
  ⑦ CORRIGE: actualiza el JSON, el template, o vuelve a extraer del portal
  ⑤ REENVÍA el documento corregido a Telegram

Flujo:
  Sandra: "Falta el número de siniestro" 
    → Hermes detecta: campo 'siniestro.id_siniestro'
    → Verifica: ¿está en el JSON original?
        Sí → bug en doc_generator → patch al código
        No  → faltó extraer del portal → re-ejecutar flujo browser
        No existe en portal → preguntar a Sandra
    → Corrige → Regenera DOCX → Reenvía

  Sandra: "Cambia la fecha a 15/05/2026"
    → Hermes detecta: campo 'consulta.fecha', nuevo valor '15/05/2026'
    → Actualiza JSON → Regenera → Reenvía

  Sandra: "✅ Aprobado"
    → Fin del loop, documento listo

Uso:
  from backend.correction_loop import analizar_mensaje_rechazo, ejecutar_correccion

  correccion = analizar_mensaje_rechazo(mensaje_sandra)
  # → {tipo: 'campo_faltante', campo: 'siniestro.id_siniestro', ...}
  
  resultado = ejecutar_correccion(correccion, datos, formato)
  # → {ok, json_actualizado, docx_regenerado, ...}
"""

import re
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum


class TipoCorreccion(str, Enum):
    CAMPO_FALTANTE = "campo_faltante"         # Falta un dato en el documento
    CAMPO_INCORRECTO = "campo_incorrecto"     # Un dato está mal (valor equivocado)
    CAMBIO_VALOR = "cambio_valor"             # Sandra da un valor específico nuevo
    FORMATO_INCORRECTO = "formato_incorrecto"  # Problema de formato (mayúsculas, bullets)
    DOCUMENTO_EQUIVOCADO = "documento_equivocado"  # Se generó el formato incorrecto
    APROBADO = "aprobado"                     # ✅ Documento aceptado
    NO_ENTENDIDO = "no_entendido"             # No se pudo interpretar el mensaje


@dataclass
class InstruccionCorreccion:
    """Resultado de analizar el mensaje de rechazo de Sandra."""
    tipo: TipoCorreccion
    campo: Optional[str] = None           # Ruta del campo en el JSON (ej: 'siniestro.id_siniestro')
    valor_nuevo: Optional[str] = None     # Valor correcto (si Sandra lo da explícitamente)
    formato_afectado: Optional[str] = None  # Qué formato tiene el problema
    mensaje_original: str = ""            # El mensaje original de Sandra
    confianza: float = 0.0                # 0.0 a 1.0 — qué tan seguros estamos
    accion_sugerida: str = ""             # Qué acción tomar
    necesita_preguntar: bool = False      # ¿Toca preguntarle a Sandra?
    pregunta_para_sandra: str = ""        # Qué preguntarle si necesita_preguntar


# ═══════════════════════════════════════════════════════════════════════════
# MAPEO DE LENGUAJE NATURAL → CAMPO JSON
# ═══════════════════════════════════════════════════════════════════════════

# Palabras/frases que Sandra usa → ruta del campo en el JSON
CAMPO_PATTERNS = [
    # Siniestro
    (r"(?:número|nro|#|id)\s*(?:de|del)?\s*siniestro", "siniestro.id_siniestro"),
    (r"(?:fecha|d[ií]a)\s*(?:de|del)?\s*(?:evento|accidente|siniestro|atel)", "siniestro.fecha_evento"),
    (r"diagn[oó]stico", "siniestro.diagnosticos"),
    (r"segmento\s*lesionado", "siniestro.segmento_lesionado"),
    (r"tipo\s*de\s*siniestro", "siniestro.tipo"),
    (r"tiempo\s*(?:de|total)?\s*incapacidad", "siniestro.tiempo_incapacidad"),
    (r"(?:último|ultimo)\s*(?:d[ií]a|fecha)\s*incapacidad", "siniestro.ultimo_dia_incapacidad"),
    (r"c[oó]digo\s*cie\s*10|cie\s*10", "siniestro.codigos_cie10"),
    
    # Paciente
    (r"nombre\s*(?:de|del)?\s*(?:trabajador|afiliado|paciente|servidor)", "paciente.nombre"),
    (r"(?:documento|c[eé]dula|cc)\s*(?:de|del)?\s*(?:trabajador|afiliado|paciente)?", "paciente.documento"),
    (r"(?:edad|años)\s*(?:de|del)?\s*(?:trabajador|afiliado|paciente)?", "paciente.edad"),
    (r"fecha\s*de\s*nacimiento", "paciente.fecha_nacimiento"),
    (r"domi?nancia", "paciente.dominancia"),
    (r"estado\s*civil", "paciente.estado_civil"),
    (r"nivel\s*educativo", "paciente.nivel_educativo"),
    (r"tel[ée]fono\s*(?:de|del)?\s*(?:trabajador|afiliado|paciente)?", "paciente.telefono"),
    (r"direcci[oó]n\s*(?:de|del)?\s*(?:residencia|trabajador|afiliado|paciente)?", "paciente.direccion"),
    (r"eps", "paciente.eps_ips"),
    (r"afp|pensi[oó]n", "paciente.afp"),
    
    # Empresa
    (r"(?:nombre|raz[oó]n\s*social)\s*(?:de|del)?\s*empresa", "empresa.nombre"),
    (r"nit\s*(?:de|del)?\s*(?:la)?\s*empresa", "empresa.nit"),
    (r"contacto\s*(?:de|del)?\s*(?:la)?\s*empresa", "empresa.contacto"),
    (r"cargo\s*(?:de|del)?\s*contacto", "empresa.cargo_contacto"),
    (r"correo\s*(?:de|del)?\s*(?:la)?\s*empresa", "empresa.correo"),
    (r"(?:tel[ée]fono|celular)\s*(?:de|del)?\s*(?:la)?\s*empresa", "empresa.telefono"),
    (r"direcci[oó]n\s*(?:de|del)?\s*(?:la)?\s*empresa", "empresa.direccion"),
    
    # Laboral
    (r"cargo\s*(?:actual|del trabajador|del afiliado)?", "laboral.cargo"),
    (r"[áa]rea\s*(?:de|del)?\s*(?:trabajo|secci[oó]n)", "laboral.area"),
    (r"fecha\s*de\s*ingreso\s*(?:al|del)?\s*cargo", "laboral.fecha_ingreso_cargo"),
    (r"fecha\s*de\s*ingreso\s*(?:a la|de la)?\s*empresa", "laboral.fecha_ingreso_empresa"),
    (r"antig[uü]edad\s*(?:en el|del)?\s*cargo", "laboral.antiguedad_cargo"),
    (r"antig[uü]edad\s*(?:en la|de la)?\s*empresa", "laboral.antiguedad_empresa"),
    (r"vinculaci[oó]n|tipo\s*de\s*contrato", "laboral.vinculacion"),
    (r"jornada\s*(?:laboral|de trabajo)?", "laboral.jornada"),
    (r"ritmo\s*(?:de trabajo)?", "laboral.ritmo"),
    (r"descansos?", "laboral.descansos"),
    (r"turnos?", "laboral.turnos"),
    (r"horas?\s*extras?", "laboral.horas_extras"),
    (r"rotaciones?", "laboral.rotaciones"),
    (r"tiempos?\s*efectivos?", "laboral.tiempos_efectivos"),
    (r"distribuci[oó]n\s*semanal", "laboral.distribucion_semanal"),
    
    # Consulta
    (r"fecha\s*(?:de|del)?\s*(?:visita|valoraci[oó]n|consulta|an[aá]lisis)", "consulta.fecha"),
    (r"metodolog[ií]a", "consulta.metodologia"),
    (r"resultados?\s*(?:de|del)?\s*valoraci[oó]n", "consulta.resultados_valoracion"),
    (r"programa\s*rhi|rh[ií]", "consulta.programa_rhi"),
    (r"proceso\s*productivo|funciones\s*del\s*cargo", "consulta.proceso_productivo"),
    (r"apreciaci[oó]n\s*(?:del|de la)?\s*(?:trabajador|servidor)", "consulta.apreciacion_trabajador"),
    (r"est[aá]ndares?\s*(?:de|del)?\s*productividad", "consulta.estandares_productividad"),
    (r"concepto\s*(?:de|del)?\s*desempeño", "consulta.concepto_desempeno"),
    (r"motivo\s*(?:de|del)?\s*consulta", "consulta.motivo_consulta"),
    (r"enfermedad\s*actual", "consulta.enfermedad_actual"),
    (r"examen\s*f[ií]sico", "consulta.examen_fisico"),
    (r"tratamiento\s*recibido", "consulta.tratamiento_recibido"),
    
    # Rehabilitación
    (r"concepto\s*integral", "rehabilitacion.concepto_integral"),
    (r"forma\s*de\s*integraci[oó]n", "rehabilitacion.forma_integracion"),
    (r"tiempo\s*de\s*vigencia|vigencia", "rehabilitacion.tiempo_vigencia"),
    (r"obst[aá]culos?", "rehabilitacion.obstaculos"),
    (r"observaciones?", "rehabilitacion.observaciones"),
    (r"actividades?\s*funcional", "rehabilitacion.actividades_funcional"),
    (r"actividades?\s*ocupacional", "rehabilitacion.actividades_ocupacional"),
    (r"logros?", "rehabilitacion.logros"),
    
    # Visita
    (r"tipo\s*de\s*estudio", "visita.tipo_estudio"),
    (r"tiempo\s*de\s*ejecuci[oó]n", "visita.tiempo_ejecucion"),
    (r"objetivo\s*(?:de|del)?\s*estudio", "visita.objetivo"),
    (r"fecha\s*y\s*hora\s*(?:de|del)?\s*(?:la)?\s*visita", "visita.fecha_hora"),
    (r"nombre\s*(?:de|del)?\s*profesional", "visita.nombre_profesional"),
    (r"nombre\s*(?:de|del)?\s*auditor", "visita.nombre_auditor"),
    (r"descripci[oó]n\s*(?:de|del)?\s*(?:estado|caso)", "visita.descripcion_estado"),
    (r"requisitos?", "visita.requisitos"),
    
    # Recomendaciones
    (r"recomendaciones?\s*(?:para|del)?\s*(?:el|la)?\s*trabajador", "recomendaciones.trabajador"),
    (r"recomendaciones?\s*(?:para|del)?\s*(?:la)?\s*empresa", "recomendaciones.empresa"),
    (r"recomendaciones?\s*(?:para|del)?\s*desarrollo\s*(?:de|del)?\s*tareas", "recomendaciones.tareas"),
    
    # Registro
    (r"(?:elabor[oó]|quien\s*elabor[oó])", "registro.elaboro"),
    (r"(?:revis[oó]|quien\s*revis[oó])", "registro.reviso"),
    (r"firma", "registro.elaboro"),  # genérico
]

# Palabras que indican aprobación
APROBACION_PATTERNS = [
    r"^[✅✔️👍](?:\s*aprobado)?",
    r"aprobado",
    r"bien\s*(?:as[ií]|hecho|echo)",
    r"(?:est[aá]|qued[oó])\s*bien",
    r"perfecto",
    r"listo\s*(?:para\s*enviar|para\s*subir)?",
    r"ok\s*(?:gracias|listo|perfecto)?",
    r"todo\s*bien",
    r"\bcorrecto\b",
    r"me\s*gusta\s*(?:como|as[ií])?\s*qued[oó]",
]

# Palabras que indican formato incorrecto
FORMATO_PATTERNS = [
    (r"(?:may[uú]sculas?|min[uú]sculas?)", "mayusculas_minusculas"),
    (r"negrita", "negrita"),
    (r"(?:tamaño|letra)\s*(?:de|del)?\s*(?:letra|fuente)", "tamano_letra"),
    (r"(?:vi[ñn]etas?|bullets?)", "vietas"),
    (r"espaciado", "espaciado"),
    (r"marg[ée]n", "margenes"),
    (r"color", "color"),
    (r"fondo\s*amarillo", "fondo_amarillo"),
]

# Patterns that indicate the wrong document was sent
DOCUMENTO_EQUIVOCADO_PATTERNS = [
    r"(?:formato|documento)\s*(?:equivocado|incorrecto|mal|err[oó]neo)",
    r"(?:me\s*(?:mandaste|enviaste|pasaste)|enviaste)\s*(?:el|la)?\s*(?:formato|documento|carta)\s*(?:equivocad|incorrect|mal)",
    r"no\s*es\s*(?:este|el)\s*(?:formato|documento)",
    r"necesito\s*(?:el|la)\s*(?:anali|carta|cierre|citaci|prueba|valoraci|formato)",
    r"(?:este\s*no|no\s*es\s*este)\s*(?:es\s*el)?",
    r"formato\s+equivocado",
    r"documento\s+equivocado",
]


# ═══════════════════════════════════════════════════════════════════════════
# ANALIZADOR DE MENSAJES
# ═══════════════════════════════════════════════════════════════════════════

def _extraer_valor_nuevo(mensaje: str) -> Optional[str]:
    """
    Intenta extraer un valor nuevo del mensaje.
    Ej: "Cambia la fecha a 15/05/2026" → "15/05/2026"
    Ej: "El siniestro es 503463870" → "503463870"
    Ej: "ponle 3182675427 al telefono" → "3182675427"
    """
    # Patrones comunes de asignación
    patterns = [
        # "cambia/pon/corrige [algo] a/por/con VALOR"
        r"(?:cambia|pon|coloca|escribe|corrige|actualiza|modifica|cambiale)\s+(?:\w+\s+){0,4}(?:a|por|con)\s+['\"]?([^'\".,\n]+?)['\"]?(?:\s*(?:$|[.,]|\s+(?:en|del|de|la|el|al)\s))",
        # "ponle/colocale VALOR"
        r"(?:ponle|ponerle|col[oó]cale|agregale|a[ñn]adele)\s+['\"]?(\d[\d\s/-]*|\S+)['\"]?",
        # "es/sería/debe ser VALOR" (captura número o fecha primero)
        r"(?:es|ser[ií]a|debe\s*ser)\s+['\"]?(\d[\d\s/-]{0,20})['\"]?",
        # "el/la [campo] correcto/a es VALOR"
        r"(?:correcto|correcta)\s+(?:es|ser[ií]a)\s+['\"]?([^'\".,\n]+?)['\"]?(?:\s*$|\s*[.,])",
        # Valor de fecha: DD/MM/AAAA
        r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, mensaje, re.IGNORECASE)
        if match:
            valor = match.group(1).strip()
            # Limpiar
            valor = valor.rstrip(".,;: ")
            # No aceptar valores muy cortos o muy largos
            if 2 <= len(valor) <= 200:
                # Si es "ponle X al Y", asegurarnos de solo capturar X
                # Eliminar trailing "al", "a la", etc.
                valor = re.sub(r'\s+(?:al?|en|de|del|para)\s*$', '', valor)
                return valor
    
    return None


def analizar_mensaje_rechazo(mensaje: str) -> InstruccionCorreccion:
    """
    Analiza el mensaje de Sandra y determina qué corrección hacer.
    
    Args:
        mensaje: Texto del mensaje de Sandra en Telegram
        
    Returns:
        InstruccionCorreccion con el tipo, campo, valor nuevo, etc.
    """
    mensaje_lower = mensaje.lower().strip()
    
    # 0. ¿Es aprobación?
    for pattern in APROBACION_PATTERNS:
        if re.search(pattern, mensaje_lower):
            return InstruccionCorreccion(
                tipo=TipoCorreccion.APROBADO,
                mensaje_original=mensaje,
                confianza=0.95,
                accion_sugerida="Documento aprobado. No se requiere corrección.",
            )
    
    # 1. ¿Falta algo? (indicadores de ausencia)
    falta_patterns = [
        r"(?:falta|falto|falta el|falto el|no tiene|no aparece|no salio|no salió|no est[aá]|no se ve)(?:\s+|$)",
        r"(?:agregar|añadir|incluir|ponerle|colocarle|ponle|col[oó]cale)(?:\s+|$)",
        r"(?:qu[ée]\s*pas[oó]\s*con|d[oó]nde\s*(?:est[aá]|qued[oó]))(?:\s+|$)",
    ]
    
    es_falta = any(re.search(p, mensaje_lower) for p in falta_patterns)
    
    # 2. ¿Está incorrecto? (indicadores de error o cambio)
    error_patterns = [
        r"(?:est[aá]\s*mal|incorrecto|equivocado|error|no es|no corresponde)(?:\s+|$)",
        r"(?:cambia|corrige|modifica|actualiza|arregla|cambiale|cambiar|corregir)(?:\s+|$)",
        r"(?:as[ií]\s*no|no\s*as[ií])(?:\s+|$)",
        r"(?:salio|salió|qued[oó])\s+(?:mal|raro|feo|diferente)(?:\s+|$)",
        r"(?:ponle|ponerle|col[oó]cale)(?:\s+|$)",
    ]
    
    es_error = any(re.search(p, mensaje_lower) for p in error_patterns)
    
    # 2b. Detección adicional: "X es Y" donde X es un campo y Y un valor
    # Ej: "El siniestro es 503463870", "la fecha es 15/05/2026"
    es_asignacion = bool(re.search(r"(?:es|ser[ií]a|debe\s*ser)\s+\d", mensaje_lower))
    
    # 3. Buscar campo específico mencionado
    campo_detectado = None
    mejor_confianza = 0.0
    
    for pattern, campo in CAMPO_PATTERNS:
        match = re.search(pattern, mensaje_lower)
        if match:
            matched_text = match.group(0)
            confianza = min(0.9, len(matched_text) / 30 + 0.3)
            if confianza > mejor_confianza:
                mejor_confianza = confianza
                campo_detectado = campo
    
    # 3b. Catch-all: palabras sueltas comunes (más permisivas, menor confianza)
    if not campo_detectado:
        catch_all = [
            (r"(?:la\s+)?fecha", "consulta.fecha"),
            (r"(?:el\s+)?siniestro", "siniestro.id_siniestro"),
            (r"(?:el\s+)?diagn[oó]stico", "siniestro.diagnosticos"),
            (r"(?:el|la)\s+cargo", "laboral.cargo"),
            (r"(?:el\s+)?nombre", "paciente.nombre"),
            (r"(?:el\s+)?documento|(?:la\s+)?c[eé]dula|cc", "paciente.documento"),
            (r"(?:el|la)\s+edad", "paciente.edad"),
            (r"(?:el\s+)?tel[eé]fono|celular", "paciente.telefono"),
            (r"(?:la\s+)?direcci[oó]n", "paciente.direccion"),
            (r"(?:la\s+)?empresa", "empresa.nombre"),
            (r"(?:el\s+)?nit", "empresa.nit"),
            (r"contacto", "empresa.contacto"),
            (r"correo|email", "empresa.correo"),
            (r"(?:el|la)\s+tratamiento", "consulta.tratamiento_recibido"),
            (r"(?:el\s+)?concepto", "rehabilitacion.concepto_integral"),
        ]
        for pattern, campo in catch_all:
            if re.search(pattern, mensaje_lower):
                campo_detectado = campo
                mejor_confianza = 0.5
                break
    
    # 4. Extraer valor nuevo si Sandra lo da
    valor_nuevo = _extraer_valor_nuevo(mensaje)
    
    # 5. Buscar problemas de formato/documento ANTES de decidir tipo
    formato_detectado = None
    for pattern, tipo_fmt in FORMATO_PATTERNS:
        if re.search(pattern, mensaje_lower):
            formato_detectado = tipo_fmt
            break

    documento_equivocado = any(
        re.search(p, mensaje_lower) for p in DOCUMENTO_EQUIVOCADO_PATTERNS
    )

    # 6. Determinar tipo de corrección (orden de prioridad)
    if documento_equivocado:
        tipo = TipoCorreccion.DOCUMENTO_EQUIVOCADO
        accion = "Sandra solicita un documento diferente. Preguntarle cuál necesita."
    elif es_falta and campo_detectado:
        tipo = TipoCorreccion.CAMPO_FALTANTE
        accion = f"Agregar campo '{campo_detectado}' al JSON de extracción"
    elif valor_nuevo and campo_detectado:
        # Sandra dio un valor nuevo explícito → CAMBIO_VALOR
        tipo = TipoCorreccion.CAMBIO_VALOR
        accion = f"Actualizar '{campo_detectado}' → '{valor_nuevo}'"
    elif es_asignacion and campo_detectado and valor_nuevo:
        # "X es Y" con campo y valor identificados
        tipo = TipoCorreccion.CAMBIO_VALOR
        accion = f"Actualizar '{campo_detectado}' → '{valor_nuevo}'"
    elif es_error and campo_detectado:
        tipo = TipoCorreccion.CAMPO_INCORRECTO
        accion = f"Verificar valor de '{campo_detectado}' — posible error en extracción o generación"
    elif formato_detectado:
        # Problema de formato (mayúsculas, viñetas, color, etc.)
        tipo = TipoCorreccion.FORMATO_INCORRECTO
        campo_detectado = formato_detectado
        accion = f"Corregir formato: {formato_detectado}"
    elif es_error or es_falta:
        # Hay intención de corrección pero no se identificó el campo
        tipo = TipoCorreccion.NO_ENTENDIDO
        accion = "No se pudo determinar el campo exacto. Preguntar a Sandra."
    else:
        tipo = TipoCorreccion.NO_ENTENDIDO
        accion = "No se pudo interpretar el mensaje. Preguntar a Sandra."
    
    necesita_preguntar = (tipo == TipoCorreccion.NO_ENTENDIDO or 
                          (tipo == TipoCorreccion.CAMPO_FALTANTE and not campo_detectado) or
                          (tipo == TipoCorreccion.CAMPO_INCORRECTO and mejor_confianza < 0.4) or
                          (tipo == TipoCorreccion.CAMBIO_VALOR and mejor_confianza < 0.3 and not valor_nuevo))
    
    pregunta = ""
    if necesita_preguntar:
        pregunta = (
            "Sandra, no entendí bien qué hay que corregir. "
            "¿Me puedes decir exactamente qué campo está mal y cuál sería el valor correcto?"
        )
    elif tipo == TipoCorreccion.CAMPO_FALTANTE and campo_detectado and not valor_nuevo:
        pregunta = f"Sandra, ¿cuál es el valor correcto para '{campo_detectado}'?"
    
    return InstruccionCorreccion(
        tipo=tipo,
        campo=campo_detectado,
        valor_nuevo=valor_nuevo,
        mensaje_original=mensaje,
        confianza=mejor_confianza,
        accion_sugerida=accion,
        necesita_preguntar=necesita_preguntar,
        pregunta_para_sandra=pregunta,
    )


# ═══════════════════════════════════════════════════════════════════════════
# EJECUTOR DE CORRECCIONES (guía para el agente)
# ═══════════════════════════════════════════════════════════════════════════

def ejecutar_correccion(
    instruccion: InstruccionCorreccion,
    datos: dict,
    formato: str,
    docx_path: Optional[str] = None,
) -> dict:
    """
    Ejecuta la corrección según el tipo detectado.
    
    Esta función es una GUÍA para el agente — el agente debe interpretar
    el resultado y ejecutar las acciones concretas (editar JSON, regenerar DOCX, etc.)
    
    Returns:
        Dict con el plan de acción para el agente.
    """
    resultado = {
        "ok": False,
        "tipo": instruccion.tipo.value,
        "plan": [],
        "json_actualizado": None,
        "necesita_regenerar": False,
        "necesita_extraer": False,
        "necesita_preguntar": instruccion.necesita_preguntar,
        "pregunta": instruccion.pregunta_para_sandra,
    }
    
    if instruccion.tipo == TipoCorreccion.APROBADO:
        resultado["ok"] = True
        resultado["plan"] = ["Documento aprobado. Fin del loop."]
        return resultado
    
    if instruccion.tipo == TipoCorreccion.NO_ENTENDIDO:
        resultado["plan"] = ["Preguntar a Sandra qué corregir exactamente"]
        resultado["necesita_preguntar"] = True
        return resultado
    
    if instruccion.tipo == TipoCorreccion.CAMPO_FALTANTE:
        resultado["plan"] = [
            f"1. Verificar si '{instruccion.campo}' está en el JSON original",
            f"2a. Si SÍ está → bug en doc_generator.py → revisar _reemplazar_* que maneja este campo",
            f"2b. Si NO está → faltó extraer del portal → re-ejecutar flujo browser para este campo",
            f"2c. Si el portal no tiene este dato → preguntar a Sandra el valor",
            f"3. Actualizar JSON con el valor correcto",
            f"4. Regenerar {formato} con doc_generator",
            f"5. Reenviar DOCX a Telegram",
        ]
        resultado["necesita_extraer"] = True
        resultado["necesita_regenerar"] = True
        if instruccion.valor_nuevo:
            resultado["plan"].insert(2, f"   ✅ Sandra dio el valor: '{instruccion.valor_nuevo}'")
            resultado["necesita_extraer"] = False
    
    elif instruccion.tipo in (TipoCorreccion.CAMBIO_VALOR, TipoCorreccion.CAMPO_INCORRECTO):
        if instruccion.valor_nuevo:
            resultado["plan"] = [
                f"1. Actualizar '{instruccion.campo}' → '{instruccion.valor_nuevo}' en el JSON",
                f"2. Regenerar {formato} con doc_generator",
                f"3. Reenviar DOCX a Telegram",
            ]
            resultado["necesita_regenerar"] = True
        else:
            resultado["plan"] = [
                f"1. El campo '{instruccion.campo}' parece incorrecto pero Sandra no dio valor nuevo",
                f"2. Revisar el valor actual: ¿vino del portal o de doc_generator?",
                f"3. Preguntar a Sandra el valor correcto",
            ]
            resultado["necesita_preguntar"] = True
    
    elif instruccion.tipo == TipoCorreccion.FORMATO_INCORRECTO:
        resultado["plan"] = [
            f"1. Problema de formato detectado: '{instruccion.campo}'",
            f"2. Verificar doc_generator.py — posible bug en _poner_texto, _reemplazar_celda_entera, etc.",
            f"3. Corregir el código (patch a doc_generator.py)",
            f"4. Regenerar {formato}",
            f"5. Reenviar DOCX a Telegram",
        ]
        resultado["necesita_regenerar"] = True
    
    return resultado


# ═══════════════════════════════════════════════════════════════════════════
# PRUEBAS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    mensajes_prueba = [
        # Aprobación
        "✅ Aprobado, así quedó bien",
        "Perfecto, me gusta como quedo",
        "ok gracias",
        
        # Campo faltante
        "Falta el número de siniestro",
        "no tiene la fecha del evento",
        "Falto el diagnostico",
        "Agregar el cargo del trabajador",
        "Qué pasó con el nit de la empresa",
        
        # Cambio de valor
        "Cambia la fecha a 15/05/2026",
        "El siniestro es 503463870",
        "La edad correcta es 45 años",
        "ponle 3182675427 al telefono de la empresa",
        
        # Campo incorrecto
        "El diagnostico esta mal",
        "Esa no es la dirección de la empresa",
        
        # Formato
        "El diagnostico salio en mayusculas y deberia ir normal",
        "Las viñetas salieron dobles",
        "El texto tiene fondo amarillo",
        
        # No entendido
        "mmm no se",
        "arregla eso porfa",
    ]
    
    print("=== ANALIZADOR DE MENSAJES DE SANDRA ===\n")
    
    for msg in mensajes_prueba:
        result = analizar_mensaje_rechazo(msg)
        icono = {
            "aprobado": "✅",
            "campo_faltante": "❌",
            "campo_incorrecto": "⚠️",
            "cambio_valor": "📝",
            "formato_incorrecto": "🎨",
            "no_entendido": "🤔",
        }.get(result.tipo.value, "❓")
        
        print(f"{icono} \"{msg}\"")
        print(f"   Tipo: {result.tipo.value}")
        if result.campo:
            print(f"   Campo: {result.campo}")
        if result.valor_nuevo:
            print(f"   Valor nuevo: {result.valor_nuevo}")
        print(f"   Confianza: {result.confianza:.2f}")
        print(f"   Acción: {result.accion_sugerida}")
        if result.necesita_preguntar:
            print(f"   ⚠️  Toca preguntar: {result.pregunta_para_sandra}")
        print()
    
    # Probar ejecutar_correccion con un caso
    print("=== PLAN DE CORRECCIÓN (CAMPO FALTANTE) ===")
    inst = analizar_mensaje_rechazo("Falta el número de siniestro")
    plan = ejecutar_correccion(inst, {}, "analisis_exigencias")
    for paso in plan["plan"]:
        print(f"  {paso}")
    
    print("\n=== PLAN DE CORRECCIÓN (CAMBIO VALOR) ===")
    inst2 = analizar_mensaje_rechazo("Cambia la fecha a 15/05/2026")
    plan2 = ejecutar_correccion(inst2, {}, "analisis_exigencias")
    for paso in plan2["plan"]:
        print(f"  {paso}")
