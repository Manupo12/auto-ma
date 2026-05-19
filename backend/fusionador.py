"""
Fusionador de datos — Une los JSON de Medifolios, Positiva, y Audio
en un solo JSON listo para el doc_generator.

Prioridad de fuentes (en caso de conflicto):
  1. Positiva (fuente oficial ARL — siniestros, CIE10, empresa)
  2. Medifolios (datos clínicos, historia, agenda)
  3. Audio (datos cualitativos: metodología, materiales, peligros, concepto)

Uso:
  from backend.fusionador import fusionar_todo

  datos_completos = fusionar_todo(datos_medifolios, datos_positiva, datos_audio)
  # → JSON listo para doc_generator
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any


# ═══════════════════════════════════════════════════════════════════════════
# FUSIÓN PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

_CIE10_SEGMENTO = {
    "S0": "Cabeza/Cuello", "S1": "Cuello/Tórax",
    "S2": "Tórax/Costillas", "S3": "Abdomen/Lumbar",
    "S4": "Hombro/Brazo", "S5": "Codo/Antebrazo",
    "S6": "Muñeca/Mano/Dedos", "S7": "Cadera/Muslo",
    "S8": "Rodilla/Pierna", "S9": "Tobillo/Pie",
    "M5": "Columna vertebral", "M7": "Miembro superior",
    "M8": "Miembro inferior",
}


def _derivar_segmento_lesionado(codigos: list, diagnostico_texto: str) -> str:
    """Deriva el segmento corporal lesionado desde códigos CIE-10 o texto."""
    for code in (codigos or []):
        prefix = str(code)[:2].upper()
        if prefix in _CIE10_SEGMENTO:
            return _CIE10_SEGMENTO[prefix]
    texto = (diagnostico_texto or "").upper()
    if any(w in texto for w in ["MANO", "DEDO", "MUÑECA"]):
        return "Muñeca/Mano/Dedos"
    if any(w in texto for w in ["HOMBRO", "BRAZO"]):
        return "Hombro/Brazo"
    if any(w in texto for w in ["RODILLA", "PIERNA"]):
        return "Rodilla/Pierna"
    if any(w in texto for w in ["COLUMNA", "LUMBAR", "ESPALDA"]):
        return "Columna vertebral"
    if any(w in texto for w in ["PIE", "TOBILLO"]):
        return "Tobillo/Pie"
    return ""


def _merge_dicts(base: dict, override: dict, prefer_override: bool = True) -> dict:
    """Fusiona dos dicts. Si prefer_override=True, el override gana en conflictos."""
    result = dict(base)
    for k, v in override.items():
        if k not in result or not result[k] or prefer_override:
            if v:  # Solo sobreescribir si el valor no está vacío
                result[k] = v
    return result


def fusionar_todo(
    datos_medifolios: Optional[dict] = None,
    datos_positiva: Optional[dict] = None,
    datos_audio: Optional[dict] = None,
    estado_caso: str = "",
) -> dict:
    """
    Fusiona datos de las 3 fuentes en un JSON completo para el doc_generator.
    
    Args:
        datos_medifolios: Output de extractor_medifolios.fusionar_datos_medifolios()
        datos_positiva: Output de extractor_positiva.fusionar_datos_positiva()
        datos_audio: Datos transcritos del audio de cita (metodología, etc.)
        estado_caso: 'NUEVO', 'SEGUIMIENTO', 'CIERRE', 'PRUEBA_TRABAJO'
    
    Returns:
        JSON completo compatible con los schemas del doc_generator.
    """
    # Valores por defecto
    med = datos_medifolios or {}
    pos = datos_positiva or {}
    aud = datos_audio or {}
    
    # ── 1. PACIENTE ───────────────────────────────────────────────
    # Prioridad: Positiva > Medifolios > Audio
    paciente = {}
    paciente.update(med.get("paciente", {}))
    paciente.update(pos.get("paciente", {}))
    
    # Construir nombre completo si no existe
    if not paciente.get("nombre"):
        partes = []
        for k in ["nombre1", "nombre2", "apellido1", "apellido2"]:
            if paciente.get(k):
                partes.append(paciente.pop(k))
        if partes:
            paciente["nombre"] = " ".join(partes)
    
    # Asegurar campos mínimos
    paciente.setdefault("documento", "")
    paciente.setdefault("nombre", "")
    paciente.setdefault("fecha_nacimiento", "")
    paciente.setdefault("edad", "")
    paciente.setdefault("telefono", "")
    paciente.setdefault("direccion", "")
    paciente.setdefault("email", "")
    paciente.setdefault("ciudad", "Neiva")
    paciente.setdefault("eps_ips", "")
    paciente.setdefault("afp", "")
    paciente.setdefault("arl", "POSITIVA COMPANIA DE SEGUROS SA")
    
    # ── 2. EMPRESA ────────────────────────────────────────────────
    empresa = _merge_dicts(med.get("empresa", {}), pos.get("empresa", {}))
    empresa.setdefault("nombre", "")
    empresa.setdefault("nit", "")
    empresa.setdefault("contacto", "")
    empresa.setdefault("cargo_contacto", "")
    empresa.setdefault("correo", "")
    empresa.setdefault("telefono", "")
    empresa.setdefault("direccion", "")
    empresa.setdefault("ciudad", "Neiva")
    
    # ── 3. SINIESTRO (con reconciliación) ───────────────────────────
    # Prioridad: Positiva (fuente oficial). Pero reconciliar con Medifolios.
    siniestro = {}
    siniestro_med = med.get("siniestro", {}).get("id_siniestro", "")
    siniestro_pos = pos.get("siniestro", {}).get("id_siniestro", "")
    
    # RECONCILIACIÓN: comparar siniestro de ambos portales
    reconciliacion = {
        "medifolios": siniestro_med,
        "positiva": siniestro_pos,
        "coinciden": True,
        "alerta": "",
    }
    
    if siniestro_med and siniestro_pos:
        if siniestro_med.strip() != siniestro_pos.strip():
            reconciliacion["coinciden"] = False
            reconciliacion["alerta"] = (
                f"⚠️ DISCREPANCIA DE SINIESTRO: Medifolios={siniestro_med}, "
                f"Positiva={siniestro_pos}. Se usará el de Positiva (fuente oficial). "
                f"Verificar manualmente."
            )
    elif siniestro_med and not siniestro_pos:
        reconciliacion["alerta"] = "ℹ️ Siniestro solo en Medifolios (no en Positiva)"
    elif siniestro_pos and not siniestro_med:
        reconciliacion["alerta"] = "ℹ️ Siniestro solo en Positiva (no en Medifolios)"
    else:
        reconciliacion["alerta"] = "⚠️ Siniestro NO encontrado en ningún portal"
    
    siniestro.update(med.get("siniestro", {}))
    siniestro.update(pos.get("siniestro", {}))
    
    # Si hay múltiples siniestros en Positiva, el principal es el primero AT
    todos = siniestro.pop("todos", [])
    if todos:
        for s in todos:
            if s.get("tipo_evento") == "AT" and not siniestro.get("id_siniestro"):
                siniestro["id_siniestro"] = s.get("id_siniestro", "")
                siniestro["fecha_evento"] = s.get("fecha_evento", "")
                siniestro["tipo"] = "AT"
    
    siniestro.setdefault("id_siniestro", "")
    siniestro.setdefault("fecha_evento", "")
    siniestro.setdefault("tipo", "AT")
    siniestro.setdefault("diagnosticos", "")
    siniestro.setdefault("codigos_cie10", [])
    if not siniestro.get("segmento_lesionado"):
        siniestro["segmento_lesionado"] = _derivar_segmento_lesionado(
            siniestro.get("codigos_cie10", []), siniestro.get("diagnosticos", "")
        )
    siniestro.setdefault("tiempo_incapacidad", "Sin datos")
    siniestro.setdefault("ultimo_dia_incapacidad", "")
    siniestro.setdefault("incapacitado", False)
    siniestro.setdefault("pcl_aplica", False)
    siniestro.setdefault("pcl_porcentaje", "")
    
    # ── 4. LABORAL ────────────────────────────────────────────────
    laboral = _merge_dicts(med.get("laboral", {}), pos.get("laboral", {}))
    laboral.setdefault("cargo", "")
    laboral.setdefault("area", "")
    laboral.setdefault("fecha_ingreso_cargo", "")
    laboral.setdefault("fecha_ingreso_empresa", "")
    laboral.setdefault("antiguedad_cargo", "")
    laboral.setdefault("antiguedad_empresa", "")
    laboral.setdefault("vinculacion", "")
    laboral.setdefault("jornada", "")
    laboral.setdefault("ritmo", "")
    laboral.setdefault("descansos", "")
    laboral.setdefault("turnos", "")
    laboral.setdefault("horas_extras", "")
    laboral.setdefault("rotaciones", "")
    laboral.setdefault("tiempos_efectivos", "")
    laboral.setdefault("distribucion_semanal", "")
    
    # ── 5. CONSULTA ───────────────────────────────────────────────
    consulta = {}
    consulta.update(med.get("consulta", {}))
    consulta["fecha"] = datetime.now().strftime("%d/%m/%Y")
    
    # ── 6. REHABILITACIÓN ─────────────────────────────────────────
    rehabilitacion = {}
    rehabilitacion.update(med.get("rehabilitacion", {}))
    rehabilitacion.update(pos.get("rehabilitacion", {}))
    rehabilitacion.setdefault("programa_rhi", [])
    rehabilitacion.setdefault("actividades_funcional", [])
    rehabilitacion.setdefault("actividades_ocupacional", [])
    rehabilitacion.setdefault("logros", "")
    rehabilitacion.setdefault("obstaculos", "Ninguno frente al caso")
    rehabilitacion.setdefault("concepto_integral", "")
    rehabilitacion.setdefault("observaciones", "Ninguna frente al caso")
    rehabilitacion.setdefault("forma_integracion", "")
    rehabilitacion.setdefault("tiempo_vigencia", "")
    rehabilitacion.setdefault("proveedor", "REHABILITACION INTEGRAL LABORAL Y OCUPACIONAL SAS")
    
    # ── 7. DATOS DE AUDIO (cualitativos) ──────────────────────────
    if aud:
        for _campo in ("metodologia", "proceso_productivo", "apreciacion_trabajador",
                       "estandares_productividad", "concepto_desempeno"):
            _val = aud.get(_campo, "")
            if _val:
                consulta[_campo] = _val
        
        # Tareas críticas
        if aud.get("tareas_criticas"):
            laboral["tareas_criticas"] = aud["tareas_criticas"]
        
        # Materiales y peligros
        if aud.get("materiales"):
            laboral["materiales"] = aud["materiales"]
        if aud.get("peligros"):
            laboral["peligros"] = aud["peligros"]
        
        # Recomendaciones — handled below when assembling resultado
    
    # ── 8. HISTORIA CLÍNICA (Medifolios) ──────────────────────────
    historia = med.get("historia_clinica", {})
    
    # ── 8b. VISITA (campos para Citación de Empresas) ─────────────
    # Los datos de visita se rellenan cuando Sandra agenda la cita.
    # Acá se ponen defaults que se actualizan antes de generar el formato.
    visita = med.get("visita", pos.get("visita", {}))
    visita.setdefault("tipo_estudio", "Análisis de Exigencias y Homologación del Cargo")
    visita.setdefault("tiempo_ejecucion", "3 horas")
    visita.setdefault(
        "objetivo",
        "Realizar análisis de exigencias del cargo y homologación de funciones con el "
        "perfil de exigencias, como parte del proceso de rehabilitación integral laboral.",
    )
    visita.setdefault("fecha_hora", "[FECHA Y HORA A DEFINIR]")
    visita.setdefault("nombre_profesional", "SANDRA PATRICIA POLANIA OSORIO")
    visita.setdefault("nombre_auditor", "DANIEL ALEXANDER MEDINA VICTORIA")
    visita.setdefault(
        "descripcion_estado",
        "Servidor en proceso de rehabilitación integral laboral y ocupacional.",
    )
    visita.setdefault(
        "requisitos",
        "Se solicita que la visita sea acompañada por un representante del área de "
        "seguridad y salud en el trabajo y jefe inmediato. Se solicita a la empresa "
        "facilitar las funciones del cargo durante la visita.",
    )

    # ── 9. ENSAMBLAR ──────────────────────────────────────────────
    resultado = {
        "paciente": paciente,
        "empresa": empresa,
        "siniestro": siniestro,
        "laboral": laboral,
        "consulta": consulta,
        "rehabilitacion": rehabilitacion,
        "historia_clinica": historia,
        "visita": visita,
        "estado_caso": estado_caso,
    }
    
    # Agregar recomendaciones del audio si existen
    if aud.get("recomendaciones"):
        resultado["recomendaciones"] = aud["recomendaciones"]
    
    # Integrar discrepancias de Fase A (Playwright real) si existen
    discrepancias = []
    if isinstance(datos_medifolios, dict) and datos_medifolios.get("_meta", {}).get("discrepancias"):
        discrepancias = datos_medifolios["_meta"]["discrepancias"]
    if isinstance(datos_positiva, dict) and datos_positiva.get("_meta", {}).get("discrepancias"):
        discrepancias.extend(
            d for d in datos_positiva["_meta"]["discrepancias"]
            if d not in discrepancias
        )

    resultado["_metadata"] = {
        "fecha_extraccion": datetime.now().isoformat(),
        "fuentes": {
            "medifolios": datos_medifolios is not None,
            "positiva": datos_positiva is not None,
            "audio": datos_audio is not None,
        },
        "reconciliacion_siniestro": reconciliacion,
        "discrepancias_portales": discrepancias,
        "total_campos": sum(
            len(v) if isinstance(v, dict) else 1
            for k, v in resultado.items()
            if not k.startswith("_")
        ),
    }
    
    return resultado


# ═══════════════════════════════════════════════════════════════════════════
# CARGA/GUARDA
# ═══════════════════════════════════════════════════════════════════════════

def guardar_datos_completos(datos: dict, cc_paciente: str, output_dir: str = None) -> str:
    """Guarda el JSON fusionado en storage/data/"""
    if output_dir is None:
        output_dir = "/root/fisioterapia/storage/data"
    os.makedirs(output_dir, exist_ok=True)
    
    # Nombre de archivo: [fecha]-[cc]-completo.json
    fecha = datetime.now().strftime("%Y%m%d")
    filename = f"{fecha}-{cc_paciente}-completo.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
    
    return filepath


def cargar_datos_parciales(cc_paciente: str, fuente: str = None, data_dir: str = None) -> Optional[dict]:
    """Carga datos previamente extraídos de un paciente."""
    if data_dir is None:
        data_dir = "/root/fisioterapia/storage/data"
    
    patron = f"{cc_paciente}"
    if fuente:
        patron += f"-{fuente}"
    
    archivos = []
    if os.path.exists(data_dir):
        for f in os.listdir(data_dir):
            if patron in f and f.endswith(".json"):
                archivos.append(os.path.join(data_dir, f))
    
    if archivos:
        # Cargar el más reciente
        archivos.sort(reverse=True)
        with open(archivos[0], "r", encoding="utf-8") as f:
            return json.load(f)
    
    return None


# ═══════════════════════════════════════════════════════════════════════════
# PRUEBA
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Simular datos de las 3 fuentes
    datos_med = {
        "paciente": {"documento": "1193143688", "nombre": "JUAN CARLOS DURAN NARVAEZ", "telefono": "3027218147"},
        "siniestro": {"id_siniestro": "503463870"},
        "empresa": {"nombre": "BOLIVARIANA DE MINERALES Y CIA LTDA"},
    }
    
    datos_pos = {
        "paciente": {"documento": "1193143688", "nombre": "JUAN CARLOS DURAN NARVAEZ", "direccion": "CALLE 1H 24 14", "email": "JUANDURAN3688@GMAIL.COM"},
        "siniestro": {"id_siniestro": "503463870", "fecha_evento": "02/03/2026", "tipo": "AT", "diagnosticos": "S611 HERIDA DEL CUARTO DEDO", "codigos_cie10": ["S611"]},
        "rehabilitacion": {"proveedor": "RILO SAS", "estado": "Cerrada"},
    }
    
    datos_aud = {
        "metodologia": "La metodología utilizada para el Análisis de Exigencias fue...",
        "tareas_criticas": [{"actividad": "Triturar piedra", "ciclo": "Diario"}],
        "materiales": [{"nombre": "Gancho de hierro", "estado": "Bueno"}],
    }
    
    resultado = fusionar_todo(datos_med, datos_pos, datos_aud, estado_caso="SEGUIMIENTO")
    
    print("=== RESULTADO FUSIÓN ===")
    # Mostrar resumen sin saturar
    resumen = {
        "paciente.nombre": resultado["paciente"].get("nombre"),
        "paciente.documento": resultado["paciente"].get("documento"),
        "siniestro.id": resultado["siniestro"].get("id_siniestro"),
        "siniestro.fecha": resultado["siniestro"].get("fecha_evento"),
        "siniestro.diag": resultado["siniestro"].get("diagnosticos"),
        "empresa": resultado["empresa"].get("nombre"),
        "estado_caso": resultado["estado_caso"],
        "fuentes": resultado["_metadata"]["fuentes"],
    }
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    
    # Guardar (simulación)
    path = guardar_datos_completos(resultado, "1193143688")
    print(f"\nGuardado en: {path}")
