"""
Validador JSON pre-generación — capa ① del flujo v2.

Verifica que el JSON de extracción tenga todos los campos requeridos
por cada formato antes de pasarlo al doc_generator.

Arquitectura:
  - Schemas por formato definen: required, recommended, optional, defaults
  - required → falta = ERROR, bloquea generación
  - recommended → falta = WARNING, el doc_generator lo maneja como campo pendiente
  - optional → falta = INFO, ignora
  - defaults → auto-rellena si el campo está vacío

Uso:
  from backend.json_validator import validar_json

  ok, errores, warnings, json_corregido, stats = validar_json(datos, "analisis_exigencias")
  if not ok:
      print(f"BLOQUEADO: {errores}")
  else:
      generar_documento("analisis_exigencias", json_corregido)
"""

import json
import copy
import re
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

# ═══════════════════════════════════════════════════════════════════════════
# SCHEMAS POR FORMATO
# ═══════════════════════════════════════════════════════════════════════════

FORMAT_SCHEMAS = {
    "analisis_exigencias": {
        "nombre": "Análisis de Exigencias / Homologación (Formato 1)",
        "required": [
            "paciente.nombre",
            "paciente.documento",
            "siniestro.id_siniestro",
            "siniestro.fecha_evento",
            "siniestro.diagnosticos",
            "empresa.nombre",
            "empresa.nit",
            "laboral.cargo",
        ],
        "recommended": [
            "paciente.edad",
            "paciente.fecha_nacimiento",
            "paciente.dominancia",
            "paciente.estado_civil",
            "paciente.nivel_educativo",
            "paciente.telefono",
            "paciente.direccion",
            "paciente.eps_ips",
            "paciente.afp",
            "empresa.contacto",
            "empresa.correo",
            "empresa.telefono",
            "empresa.direccion",
            "laboral.area",
            "laboral.fecha_ingreso_cargo",
            "laboral.antiguedad_cargo",
            "laboral.fecha_ingreso_empresa",
            "laboral.antiguedad_empresa",
            "laboral.vinculacion",
            "laboral.jornada",
            "laboral.ritmo",
            "laboral.descansos",
            "laboral.turnos",
            "laboral.tiempos_efectivos",
            "laboral.rotaciones",
            "laboral.horas_extras",
            "laboral.distribucion_semanal",
            "consulta.fecha",
            "consulta.metodologia",
            "consulta.resultados_valoracion",
            "consulta.programa_rhi",
            "consulta.proceso_productivo",
            "consulta.apreciacion_trabajador",
            "consulta.estandares_productividad",
            "consulta.concepto_desempeno",
            "siniestro.tiempo_incapacidad",
        ],
        "optional": [
            "tareas_criticas",
            "materiales",
            "peligros",
            "recomendaciones.trabajador",
            "recomendaciones.empresa",
            "perfil_exigencias",
            "registro.elaboro",
            "registro.reviso",
            "paciente.formacion_otros",
        ],
        "defaults": {
            "consulta.fecha": lambda: datetime.now().strftime("%d/%m/%Y"),
            "empresa.ciudad": "Neiva",
            "paciente.ciudad": "Neiva",
            "registro.elaboro": "SANDRA PATRICIA POLANIA OSORIO — Fisioterapeuta Esp. SO — REHABILITACION INTEGRAL LABORAL Y OCUPACIONAL SAS",
            "registro.reviso": "DANIEL ALEXANDER MEDINA VICTORIA — Médico Laboral",
        },
    },

    "carta_medidas": {
        "nombre": "Carta de Medidas Preventivas (Formato 2)",
        "required": [
            "paciente.nombre",
            "paciente.documento",
            "siniestro.id_siniestro",
            "siniestro.fecha_evento",
            "empresa.nombre",
            "empresa.contacto",
            "laboral.cargo",
            "consulta.fecha",
        ],
        "recommended": [
            "empresa.cargo_contacto",
            "empresa.direccion",
            "empresa.telefono",
            "empresa.correo",
            "consulta.cuerpo_carta",
            "recomendaciones.trabajador_texto",
            "recomendaciones.tareas_texto",
            "recomendaciones.empresa_texto",
            "siniestro.diagnosticos",
        ],
        "optional": [
            "paciente.telefono",
            "paciente.direccion",
            "laboral.area",
            "rehabilitacion.periodo_vigencia",
            "rehabilitacion.tiempo_vigencia",
        ],
        "defaults": {
            "consulta.fecha": lambda: datetime.now().strftime("%d/%m/%Y"),
            "empresa.ciudad": "Neiva",
            "rehabilitacion.periodo_vigencia": "3 meses a partir de la fecha de esta comunicación",
        },
    },

    "carta_recomendaciones": {
        "nombre": "Carta de Recomendaciones / Reincorporación Laboral (Formato 3)",
        "required": [
            "paciente.nombre",
            "paciente.documento",
            "siniestro.id_siniestro",
            "siniestro.fecha_evento",
            "siniestro.tipo",
            "siniestro.segmento_lesionado",
            "empresa.nombre",
            "empresa.contacto",
            "laboral.cargo",
            "consulta.fecha",
        ],
        "recommended": [
            "empresa.cargo_contacto",
            "empresa.direccion",
            "empresa.telefono",
            "recomendaciones.trabajador",
            "recomendaciones.tareas",
            "recomendaciones.empresa_texto",
            "rehabilitacion.concepto_integral",
            "rehabilitacion.tiempo_vigencia",
            "rehabilitacion.forma_integracion",
            "siniestro.incapacitado",
            "siniestro.fecha_ultima_incapacidad",
        ],
        "optional": [
            "rehabilitacion.periodo_vigencia",
            "rehabilitacion.observaciones",
        ],
        "defaults": {
            "consulta.fecha": lambda: datetime.now().strftime("%d/%m/%Y"),
            "empresa.ciudad": "Neiva",
            "siniestro.incapacitado": False,
        },
    },

    "cierre_caso": {
        "nombre": "Certificado de Rehabilitación Integral / Cierre de Caso (Formato 4)",
        "required": [
            "paciente.nombre",
            "paciente.documento",
            "siniestro.id_siniestro",
            "siniestro.fecha_evento",
            "siniestro.diagnosticos",
            "empresa.nombre",
            "laboral.cargo",
        ],
        "recommended": [
            "paciente.fecha_nacimiento",
            "paciente.edad",
            "paciente.telefono",
            "paciente.direccion",
            "paciente.eps_ips",
            "paciente.afp",
            "empresa.contacto",
            "empresa.telefono",
            "laboral.area",
            "laboral.fecha_ingreso_cargo",
            "laboral.antiguedad_cargo",
            "siniestro.ultimo_dia_incapacidad",
            "siniestro.tiempo_incapacidad",
            "consulta.fecha",
            "consulta.motivo_consulta",
            "consulta.enfermedad_actual",
            "consulta.examen_fisico",
            "consulta.diagnostico_definitivo",
            "rehabilitacion.programa_rhi",
            "rehabilitacion.actividades_funcional",
            "rehabilitacion.actividades_ocupacional",
            "rehabilitacion.logros",
            "rehabilitacion.obstaculos",
            "rehabilitacion.concepto_integral",
            "rehabilitacion.observaciones",
            "rehabilitacion.forma_integracion",
            "rehabilitacion.tiempo_vigencia",
        ],
        "optional": [
            "consulta.plan_tratamiento",
            "siniestro.codigos_cie10",
        ],
        "defaults": {
            "consulta.fecha": lambda: datetime.now().strftime("%d/%m/%Y"),
            "rehabilitacion.obstaculos": "Ninguno frente al caso",
            "rehabilitacion.observaciones": "Ninguna frente al caso",
        },
    },

    "citacion_empresas": {
        "nombre": "Citación de Empresas (Formato 5)",
        "required": [
            "paciente.nombre",
            "paciente.documento",
            "empresa.nombre",
            "empresa.contacto",
            "laboral.cargo",
            "consulta.fecha",
            "visita.tipo_estudio",
            "visita.tiempo_ejecucion",
            "visita.objetivo",
            "visita.fecha_hora",
        ],
        "recommended": [
            "empresa.cargo_contacto",
            "empresa.direccion",
            "visita.nombre_profesional",
            "visita.nombre_auditor",
            "visita.descripcion_estado",
            "visita.requisitos",
            "proveedor.telefono",
            "proveedor.correo",
        ],
        "optional": [],
        "defaults": {
            "consulta.fecha": lambda: datetime.now().strftime("%d/%m/%Y"),
            "empresa.ciudad": "Neiva",
            "visita.nombre_profesional": "SANDRA PATRICIA POLANIA OSORIO",
            "visita.nombre_auditor": "DANIEL ALEXANDER MEDINA VICTORIA",
            "proveedor.telefono": "3182675427",
            "proveedor.correo": "tocupacionalrilo@gmail.com",
        },
    },

    "prueba_trabajo": {
        "nombre": "Prueba de Trabajo (Formato 6)",
        "required": [
            "paciente.nombre",
            "paciente.documento",
            "siniestro.id_siniestro",
            "siniestro.fecha_evento",
            "siniestro.diagnosticos",
            "empresa.nombre",
            "empresa.nit",
            "laboral.cargo",
            "consulta.fecha",
        ],
        "recommended": [
            "paciente.edad",
            "paciente.fecha_nacimiento",
            "paciente.dominancia",
            "paciente.estado_civil",
            "paciente.nivel_educativo",
            "paciente.telefono",
            "paciente.direccion",
            "paciente.eps_ips",
            "paciente.afp",
            "empresa.contacto",
            "empresa.cargo_contacto",
            "empresa.correo",
            "empresa.telefono",
            "empresa.direccion",
            "laboral.area",
            "laboral.fecha_ingreso_cargo",
            "laboral.antiguedad_cargo",
            "laboral.fecha_ingreso_empresa",
            "laboral.antiguedad_empresa",
            "laboral.vinculacion",
            "laboral.jornada",
            "laboral.ritmo",
            "laboral.descansos",
            "laboral.turnos",
            "laboral.horas_extras",
            "laboral.rotaciones",
            "laboral.tiempos_efectivos",
            "laboral.distribucion_semanal",
            "siniestro.ultimo_dia_incapacidad",
            "siniestro.tiempo_incapacidad",
            "consulta.metodologia",
            "consulta.proceso_productivo",
            "consulta.apreciacion_trabajador",
            "consulta.estandares_productividad",
            "consulta.concepto_desempeno",
            "tareas_criticas",
            "materiales",
            "peligros",
        ],
        "optional": [
            "paciente.formacion_otros",
        ],
        "defaults": {
            "consulta.fecha": lambda: datetime.now().strftime("%d/%m/%Y"),
            "empresa.ciudad": "Neiva",
        },
    },

    "valoracion_desempeno": {
        "nombre": "Valoración del Desempeño Ocupacional Final (Formato 7)",
        "required": [
            "paciente.nombre",
            "paciente.documento",
            "siniestro.id_siniestro",
            "siniestro.fecha_evento",
            "siniestro.diagnosticos",
            "empresa.nombre",
            "laboral.cargo",
            "consulta.fecha",
        ],
        "recommended": [
            "paciente.edad",
            "paciente.fecha_nacimiento",
            "paciente.dominancia",
            "paciente.estado_civil",
            "paciente.nivel_educativo",
            "paciente.telefono",
            "paciente.direccion",
            "paciente.eps_ips",
            "paciente.afp",
            "empresa.contacto",
            "empresa.cargo_contacto",
            "empresa.correo",
            "empresa.telefono",
            "empresa.direccion",
            "laboral.area",
            "laboral.fecha_ingreso_cargo",
            "laboral.antiguedad_cargo",
            "laboral.fecha_ingreso_empresa",
            "laboral.antiguedad_empresa",
            "laboral.vinculacion",
            "laboral.modalidad",
            "laboral.tiempo_modalidad",
            "laboral.jornada",
            "laboral.horario",
            "laboral.herramientas",
            "laboral.epp",
            "laboral.requerimientos_motrices",
            "siniestro.tipo",
            "siniestro.segmento_lesionado",
            "siniestro.tiempo_incapacidad",
            "siniestro.ultimo_dia_incapacidad",
            "siniestro.incapacitado",
            "siniestro.fecha_ultima_incapacidad",
            "siniestro.pcl_aplica",
            "siniestro.pcl_porcentaje",
            "consulta.tratamiento_recibido",
            "consulta.motivo_consulta",
            "consulta.enfermedad_actual",
            "historia_ocupacional",
            "adaptaciones",
            "recomendaciones.trabajador",
            "recomendaciones.empresa",
            "rehabilitacion.concepto_integral",
            "rehabilitacion.orientacion",
            "rehabilitacion.forma_integracion",
            "rehabilitacion.tiempo_vigencia",
        ],
        "optional": [
            "paciente.formacion_otros",
            "otros_oficios",
            "oficios_interes",
            "consulta.plan_tratamiento",
        ],
        "defaults": {
            "consulta.fecha": lambda: datetime.now().strftime("%d/%m/%Y"),
            "empresa.ciudad": "Neiva",
            "siniestro.incapacitado": False,
            "rehabilitacion.observaciones": "Ninguna frente al caso",
        },
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# VALIDADOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

def _get_nested(data: dict, path: str) -> Any:
    """Obtiene un valor anidado por ruta con puntos: 'paciente.nombre'"""
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


def _set_nested(data: dict, path: str, value: Any) -> None:
    """Establece un valor anidado por ruta con puntos."""
    keys = path.split(".")
    current = data
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def _is_empty(value: Any) -> bool:
    """Determina si un valor está vacío (None, string vacío, lista vacía, 0)."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    if value == 0:
        return True  # 0 se considera vacío (edad=0, tiempo=0 no son válidos)
    if value is False:
        return True  # False explicito requiere verificacion
    return False


def validar_json(
    datos: dict, formato: str
) -> Tuple[bool, List[str], List[str], dict, dict]:
    """
    Valida un JSON contra el schema del formato especificado.

    Args:
        datos: Diccionario con los datos extraídos del portal
        formato: Nombre del formato (ej: 'analisis_exigencias', 'cierre_caso')

    Returns:
        (ok, errores, warnings, json_corregido, stats)
        - ok: True si no hay errores bloqueantes
        - errores: Lista de campos required faltantes (bloquean generación)
        - warnings: Lista de campos recommended faltantes (se auto-completan)
        - json_corregido: Copia de datos con defaults y [VERIFICAR] aplicados
        - stats: Diccionario con conteos {required_ok, required_fail, recommended_ok, recommended_warn, defaults_applied}
    """
    if formato not in FORMAT_SCHEMAS:
        return False, [f"Formato desconocido: '{formato}'. Válidos: {list(FORMAT_SCHEMAS.keys())}"], [], datos, {}

    schema = FORMAT_SCHEMAS[formato]
    datos = copy.deepcopy(datos)  # No mutar el original
    errores = []
    warnings = []
    defaults_applied = 0
    required_ok = 0
    required_fail = 0
    recommended_ok = 0
    recommended_warn = 0

    # 1. Aplicar defaults primero
    for path, default_fn in schema.get("defaults", {}).items():
        valor = _get_nested(datos, path)
        if _is_empty(valor):
            val = default_fn() if callable(default_fn) else default_fn
            _set_nested(datos, path, val)
            defaults_applied += 1

    # 2. Validar campos required
    for path in schema["required"]:
        valor = _get_nested(datos, path)
        if _is_empty(valor):
            errores.append(f"❌ REQUERIDO: '{path}' está vacío o ausente")
            required_fail += 1
        else:
            required_ok += 1

    # 3. Validar campos recommended
    for path in schema["recommended"]:
        valor = _get_nested(datos, path)
        if _is_empty(valor):
            warnings.append(f"⚠️  RECOMENDADO: '{path}' esta vacio — pendiente de verificar")
            recommended_warn += 1
        else:
            recommended_ok += 1

    # 4. Contar opcionales presentes (info)
    optional_present = 0
    optional_total = len(schema.get("optional", []))
    for path in schema.get("optional", []):
        valor = _get_nested(datos, path)
        if not _is_empty(valor):
            optional_present += 1

    stats = {
        "formato": schema["nombre"],
        "required_ok": required_ok,
        "required_fail": required_fail,
        "required_total": len(schema["required"]),
        "recommended_ok": recommended_ok,
        "recommended_warn": recommended_warn,
        "recommended_total": len(schema["recommended"]),
        "optional_present": optional_present,
        "optional_total": optional_total,
        "defaults_applied": defaults_applied,
    }

    ok = len(errores) == 0
    return ok, errores, warnings, datos, stats


def validar_para_formatos(
    datos: dict, formatos: List[str]
) -> Dict[str, dict]:
    """
    Valida el JSON contra múltiples formatos. Útil para saber cuáles
    se pueden generar y cuáles no.

    Returns:
        {formato: {ok, errores, warnings, stats}}
    """
    resultados = {}
    for fmt in formatos:
        ok, errores, warnings, corregido, stats = validar_json(datos, fmt)
        resultados[fmt] = {
            "ok": ok,
            "errores": errores,
            "warnings": warnings,
            "stats": stats,
            "json_corregido": corregido if ok else None,
        }
    return resultados


def reporte_legible(resultados: Dict[str, dict]) -> str:
    """Genera un reporte en texto legible para Telegram/CLI."""
    lineas = []
    lineas.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lineas.append("📋 VALIDACIÓN JSON PRE-GENERACIÓN")
    lineas.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    for fmt, res in resultados.items():
        stats = res["stats"]
        icono = "✅" if res["ok"] else "❌ BLOQUEADO"
        lineas.append(f"\n{icono} {stats['formato']}")

        # Required
        req_pct = (
            int(stats["required_ok"] / stats["required_total"] * 100)
            if stats["required_total"] > 0
            else 100
        )
        lineas.append(
            f"   REQUERIDOS: {stats['required_ok']}/{stats['required_total']} ({req_pct}%)"
        )

        # Recommended
        if stats["recommended_total"] > 0:
            rec_pct = (
                int(stats["recommended_ok"] / stats["recommended_total"] * 100)
                if stats["recommended_total"] > 0
                else 100
            )
            lineas.append(
                f"   RECOMENDADOS: {stats['recommended_ok']}/{stats['recommended_total']} ({rec_pct}%)"
            )

        # Defaults
        if stats["defaults_applied"] > 0:
            lineas.append(f"   DEFAULTS APLICADOS: {stats['defaults_applied']}")

        # Opcionales
        if stats["optional_total"] > 0:
            lineas.append(
                f"   OPCIONALES: {stats['optional_present']}/{stats['optional_total']} presentes"
            )

        # Errores
        if res["errores"]:
            lineas.append("   ❌ ERRORES BLOQUEANTES:")
            for e in res["errores"][:5]:  # Máx 5 para no saturar
                lineas.append(f"      {e}")
            if len(res["errores"]) > 5:
                lineas.append(f"      ... y {len(res['errores']) - 5} más")

        # Warnings
        if res["warnings"]:
            warn_count = len(res["warnings"])
            lineas.append(f"   ⚠️  ADVERTENCIAS: {warn_count} campo(s) pendientes de verificar")

    lineas.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    total_ok = sum(1 for r in resultados.values() if r["ok"])
    lineas.append(f"📊 Total: {total_ok}/{len(resultados)} formatos pueden generarse")
    lineas.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lineas)


# ═══════════════════════════════════════════════════════════════════════════
# PRUEBA RÁPIDA
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Simular un JSON incompleto
    datos_prueba = {
        "paciente": {
            "nombre": "JUAN CARLOS DURAN NARVAEZ",
            "documento": "1193143688",
        },
        "empresa": {"nombre": "CONSORCIO XYZ"},
        "laboral": {"cargo": "OPERARIO"},
        "siniestro": {
            # id_siniestro FALTA a propósito
            "fecha_evento": "15/03/2025",
            "diagnosticos": "HERIDA DEL CUARTO DEDO PIE DERECHO",
        },
        "consulta": {},
    }

    print("=== PRUEBA VALIDADOR ===")
    ok, errores, warnings, corregido, stats = validar_json(
        datos_prueba, "analisis_exigencias"
    )

    print(f"\n¿OK? {ok}")
    print(f"Errores ({len(errores)}):")
    for e in errores:
        print(f"  {e}")
    print(f"\nWarnings ({len(warnings)}):")
    for w in warnings[:5]:
        print(f"  {w}")
    if len(warnings) > 5:
        print(f"  ... y {len(warnings) - 5} más")

    print(f"\nStats: {json.dumps(stats, indent=2, ensure_ascii=False)}")

    # Prueba multi-formato
    print("\n=== PRUEBA MULTI-FORMATO ===")
    resultados = validar_para_formatos(
        datos_prueba,
        ["analisis_exigencias", "citacion_empresas", "carta_medidas"],
    )
    print(reporte_legible(resultados))
