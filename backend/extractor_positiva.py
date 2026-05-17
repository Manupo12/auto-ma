"""
Extractor ARL Positiva — Sub-flujo B del flujo v2.

Extrae datos del paciente desde ARL Positiva usando browser automation.
El agente sigue estos pasos para navegar y extraer información de
Consulta integral (6 pestañas) y Consultar caso RHI.

Fuentes de datos en Positiva:
  1. Consulta integral → SINIESTROS (ID, fecha, diagnóstico, %PCL)
  2. Consulta integral → REHABILITACIÓN INTEGRAL (CIE10, proveedor, estado)
  3. Consulta integral → DATOS ASEGURADO (nombre, dirección, tel, email)
  4. Consulta integral → GESTIÓN AUTORIZACIONES (aut/neg, procedimientos)
  5. Consulta integral → EVOLUCIONES (seguimiento, incapacidades)
  6. Consulta integral → BITACORAS (trazabilidad RHI)
  7. Rehabilitación → Consultar caso RHI → MATRICULAS

Output: JSON parcial que se fusiona con datos de Medifolios y Audio.
"""

import json
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════

POSITIVA_URL = "https://positivacuida.positiva.gov.co/cas/login?service=https://positivacuida.positiva.gov.co/web/j_spring_cas_security_check"
POSITIVA_USER = "1075209386MR"
POSITIVA_PASS = "Rilo2026*"

# Mapeo de pestañas de Consulta integral → campos a extraer
TABS_CONSULTA_INTEGRAL = {
    "SINIESTROS": {
        "columnas": [
            "Documento Asegurado", "Siniestro", "Fecha Siniestro",
            "Tipo Evento", "Indicador Tipo Accidente", "Tipo de accidente",
            "% PCL", "Estado Calificación Origen", "Diagnóstico",
            "Clasificación de Gravedad", "Acciones"
        ],
        "campos_clave": ["Siniestro", "Fecha Siniestro", "Diagnóstico", "% PCL", "Tipo Evento"],
    },
    "REHABILITACIÓN INTEGRAL": {
        "columnas": [
            "Asegurado", "Id Ingreso", "Fecha Ingreso",
            "No. Siniestro", "Fecha de Siniestro", "Proveedor Asignado",
            "Diagnóstico", "Calificación origen", "Estado", "Acciones"
        ],
        "campos_clave": ["Id Ingreso", "No. Siniestro", "Diagnóstico", "Proveedor Asignado", "Estado"],
    },
    "DATOS ASEGURADO": {
        "campos": [
            "Tipo de Identificación", "Número Identificación", "Nombre",
            "Fecha de Nacimiento", "Departamento", "Ciudad/ Municipio",
            "Zona", "Localidad", "Barrio", "Dirección de Residencia",
            "Correo Electronico", "Teléfono Fijo Particular",
            "Teléfono Fijo Laboral", "Celular Particular", "Celular Laboral"
        ],
    },
    "GESTIÓN AUTORIZACIONES": {
        "columnas": [
            "Número Siniestro", "Código Diagnóstico", "Cod. Procedimiento",
            "Número Aut/Neg", "Fecha Aut/Neg", "Fecha Solicitud",
            "Proveedor Solicitante", "Proveedor Autorizado",
            "Tipo Solicitud", "Estado Solicitud", "Rol Autorizador", "Usuario Autorizador"
        ],
    },
    "EVOLUCIONES": {
        "columnas": [
            "Fecha Evolución", "Usuario", "Empresa", "Siniestro",
            "Requiere Incapacidad", "Incapacidad", "Especialidad Médica"
        ],
    },
    "BITACORAS": {
        "subpestañas": ["Bitacoras solicitudes", "Bitacoras asegurado"],
        "columnas_solicitudes": [
            "Tipo Solicitud", "Fecha Bitácora", "Solicitud",
            "Relación Laboral", "Siniestro", "Asunto",
            "Razón Social", "Usuario Sistema", "Observaciones", "Usuario"
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# PASOS DE EXTRACCIÓN
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PasoExtraccion:
    orden: int
    nombre: str
    descripcion: str
    accion: str
    detalle: dict = field(default_factory=dict)


def obtener_pasos_extraccion(cc_paciente: str) -> List[PasoExtraccion]:
    """Devuelve los pasos que el agente debe seguir en Positiva."""
    pasos = []
    
    # ── FASE 1: Login ─────────────────────────────────────────────
    pasos.append(PasoExtraccion(
        orden=1, nombre="Login ARL Positiva",
        descripcion="Navegar al CAS de Positiva e iniciar sesión",
        accion="login",
        detalle={
            "url": POSITIVA_URL,
            "usuario": POSITIVA_USER,
            "contraseña": POSITIVA_PASS,
            "campo_usuario": "textbox 'Usuario'",
            "campo_password": "textbox 'Clave'",
            "boton_login": "button 'Ingresar'",
        }
    ))
    
    # ── FASE 2: Consulta integral ─────────────────────────────────
    pasos.append(PasoExtraccion(
        orden=2, nombre="Navegar a Consulta integral",
        descripcion="En el menú lateral, click en 'Consulta integral'",
        accion="click",
        detalle={"menu_item": "link 'Consulta integral'"}
    ))
    
    pasos.append(PasoExtraccion(
        orden=3, nombre="Buscar paciente",
        descripcion=f"Seleccionar 'Cédula de ciudadanía', escribir '{cc_paciente}', click en 'Buscar'",
        accion="form",
        detalle={
            "tipo_id": "Cédula de ciudadanía",
            "numero_id": cc_paciente,
            "campo_id": "textbox 'Número Identificación'",
            "boton_buscar": "button 'Buscar'",
            "verificar": "Debe aparecer 'CC {cc} - NOMBRE DEL PACIENTE'",
        }
    ))
    
    # ── FASE 3: Extraer cada pestaña ──────────────────────────────
    for tab_name, tab_info in TABS_CONSULTA_INTEGRAL.items():
        pasos.append(PasoExtraccion(
            orden=4 + list(TABS_CONSULTA_INTEGRAL.keys()).index(tab_name),
            nombre=f"Extraer pestaña: {tab_name}",
            descripcion=f"Hacer click en la pestaña '{tab_name}' y extraer todos los datos visibles",
            accion="extraer",
            detalle={
                "tab_name": tab_name,
                "tab_link": f"link '{tab_name}'",
                "columnas": tab_info.get("columnas", []),
                "campos": tab_info.get("campos", []),
                "subpestañas": tab_info.get("subpestañas", []),
                "js_extract": """
                    // Extraer todas las filas de la tabla/grid activa
                    var rows = document.querySelectorAll('.tab-pane.active tr, [role="tabpanel"]:not([hidden]) tr');
                    var data = [];
                    rows.forEach(function(row) {
                        var cells = row.querySelectorAll('td, th');
                        var rowData = Array.from(cells).map(c => c.textContent.trim());
                        if (rowData.some(c => c.length > 0)) data.push(rowData);
                    });
                    JSON.stringify(data);
                """,
            }
        ))
    
    # ── FASE 4: Consultar caso RHI ─────────────────────────────────
    pasos.append(PasoExtraccion(
        orden=10, nombre="Navegar a Consultar caso RHI",
        descripcion="Menú lateral → Rehabilitación → submenú → Consultar caso RHI",
        accion="click",
        detalle={
            "menu_rehab": "link 'Rehabilitación' (abre submenú)",
            "submenu": "link 'Consultar caso rhi'",
        }
    ))
    
    pasos.append(PasoExtraccion(
        orden=11, nombre="Buscar en Consultar caso RHI",
        descripcion=f"Seleccionar tipo documento, escribir '{cc_paciente}', click en 'Buscar'",
        accion="form",
        detalle={
            "tipo_doc": "Cédula de Ciudadanía",
            "numero_doc": cc_paciente,
            "campo_doc": "textbox 'Número de Documento'",
            "boton_buscar": "button 'Buscar'",
        }
    ))
    
    pasos.append(PasoExtraccion(
        orden=12, nombre="Extraer tabla MATRICULAS",
        descripcion="Extraer todas las filas de la tabla MATRICULAS: No Matrícula, Fecha, Siniestro, Diagnóstico, Calif. Origen",
        accion="extraer",
        detalle={
            "columnas": ["No Matrícula", "Fecha Matrícula", "No Siniestro", "Fecha Siniestro", "Diagnóstico", "Calificación Origen", "Acciones"],
        }
    ))
    
    return pasos


# ═══════════════════════════════════════════════════════════════════════════
# PARSEO Y FUSIÓN
# ═══════════════════════════════════════════════════════════════════════════

def parsear_siniestros_positiva(filas_tabla: List[List[str]]) -> List[dict]:
    """
    Convierte las filas de la tabla SINIESTROS a una lista de dicts.
    Columnas esperadas: [Documento, Siniestro, Fecha, Tipo, Indicador, TipoAcc, %PCL, Estado, Calif, Diag, Gravedad, Acciones]
    """
    siniestros = []
    for fila in filas_tabla:
        if len(fila) >= 6 and fila[1] and fila[1].isdigit():
            siniestros.append({
                "documento": fila[0] if len(fila) > 0 else "",
                "id_siniestro": fila[1] if len(fila) > 1 else "",
                "fecha_evento": fila[2] if len(fila) > 2 else "",
                "tipo_evento": fila[3] if len(fila) > 3 else "",
                "pcl": fila[6] if len(fila) > 6 else "",
                "estado": fila[7] if len(fila) > 7 else "",
                "diagnostico": fila[9] if len(fila) > 9 else "",
                "gravedad": fila[10] if len(fila) > 10 else "",
            })
    return siniestros


def parsear_rehab_integral_positiva(filas_tabla: List[List[str]]) -> List[dict]:
    """
    Convierte las filas de REHABILITACIÓN INTEGRAL a lista de dicts.
    Columnas: [Asegurado, IdIngreso, FechaIngreso, Siniestro, FechaSin, Proveedor, Diag, Calif, Estado, Acciones]
    """
    ingresos = []
    for fila in filas_tabla:
        if len(fila) >= 5 and fila[3] and fila[3].isdigit():
            ingresos.append({
                "id_ingreso": fila[1] if len(fila) > 1 else "",
                "fecha_ingreso": fila[2] if len(fila) > 2 else "",
                "id_siniestro": fila[3] if len(fila) > 3 else "",
                "fecha_siniestro": fila[4] if len(fila) > 4 else "",
                "proveedor": fila[5] if len(fila) > 5 else "",
                "diagnostico_cie10": fila[6] if len(fila) > 6 else "",
                "calificacion_origen": fila[7] if len(fila) > 7 else "",
                "estado": fila[8] if len(fila) > 8 else "",
            })
    return ingresos


def extraer_cie10_de_diagnostico(diagnostico: str) -> str:
    """Extrae el código CIE10 del texto de diagnóstico. Ej: 'S611 HERIDA DE DEDO...' → 'S611'"""
    match = re.match(r'^([A-Z]\d{2,3})', diagnostico.strip())
    return match.group(1) if match else ""


def fusionar_datos_positiva(
    datos_asegurado: dict,
    siniestros: List[dict],
    rehab_integral: List[dict],
    autorizaciones: List[dict] = None,
    evoluciones: List[dict] = None,
    bitacoras: List[dict] = None,
    matriculas: List[dict] = None,
) -> dict:
    """
    Fusiona todos los datos extraídos de Positiva en un JSON compatible
    con el doc_generator.
    """
    resultado = {
        "paciente": {},
        "siniestro": {},
        "empresa": {},
        "laboral": {},
        "rehabilitacion": {},
    }
    
    # 1. Datos del asegurado
    if datos_asegurado:
        resultado["paciente"].update({
            "documento": datos_asegurado.get("Número Identificación", ""),
            "nombre": datos_asegurado.get("Nombre", ""),
            "fecha_nacimiento": datos_asegurado.get("Fecha de Nacimiento", ""),
            "direccion": datos_asegurado.get("Dirección de Residencia", ""),
            "telefono": datos_asegurado.get("Teléfono Fijo Particular") or datos_asegurado.get("Celular Particular", ""),
            "email": datos_asegurado.get("Correo Electronico", ""),
            "ciudad": datos_asegurado.get("Ciudad/ Municipio", ""),
            "zona": datos_asegurado.get("Zona", ""),
        })
    
    # 2. Siniestros (tomar el más reciente o el primer AT)
    if siniestros:
        principal = siniestros[0]
        # Buscar siniestro de tipo AT (Accidente de Trabajo)
        for s in siniestros:
            if s.get("tipo_evento") == "AT":
                principal = s
                break
        
        resultado["siniestro"].update({
            "id_siniestro": principal.get("id_siniestro", ""),
            "fecha_evento": principal.get("fecha_evento", ""),
            "tipo": principal.get("tipo_evento", ""),
            "diagnosticos": principal.get("diagnostico", ""),
            "pcl": principal.get("pcl", ""),
            "estado": principal.get("estado", ""),
        })
        
        # Todos los siniestros para referencia
        resultado["siniestro"]["todos"] = siniestros
    
    # 3. Rehabilitación integral
    if rehab_integral:
        principal_ri = rehab_integral[0]
        diag = principal_ri.get("diagnostico_cie10", "")
        resultado["siniestro"]["codigos_cie10"] = [extraer_cie10_de_diagnostico(diag)] if diag else []
        resultado["siniestro"]["diagnosticos"] = diag  # El CIE10 + descripción es más preciso
        
        resultado["rehabilitacion"].update({
            "id_ingreso": principal_ri.get("id_ingreso", ""),
            "fecha_ingreso": principal_ri.get("fecha_ingreso", ""),
            "proveedor": principal_ri.get("proveedor", ""),
            "estado": principal_ri.get("estado", ""),
        })
    
    # 4. Autorizaciones
    if autorizaciones:
        resultado["rehabilitacion"]["autorizaciones"] = autorizaciones
    
    # 5. Evoluciones
    if evoluciones:
        resultado["rehabilitacion"]["evoluciones"] = evoluciones
    
    # 6. Bitácoras
    if bitacoras:
        resultado["rehabilitacion"]["bitacoras"] = bitacoras
    
    # 7. Matrículas RHI
    if matriculas:
        resultado["rehabilitacion"]["matriculas"] = matriculas
        if matriculas and not resultado["siniestro"].get("id_siniestro"):
            resultado["siniestro"]["id_siniestro"] = matriculas[0].get("No Siniestro", "")
    
    return resultado


# ═══════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

def extraer_datos_positiva(cc_paciente: str) -> dict:
    """Guía de extracción para el agente."""
    pasos = obtener_pasos_extraccion(cc_paciente)
    
    return {
        "portal": "positiva",
        "cc_paciente": cc_paciente,
        "total_pasos": len(pasos),
        "pasos": [
            {
                "orden": p.orden,
                "nombre": p.nombre,
                "descripcion": p.descripcion,
                "accion": p.accion,
                "detalle": p.detalle,
            }
            for p in pasos
        ],
        "output_esperado": {
            "siniestro": {"id_siniestro", "fecha_evento", "tipo", "diagnosticos", "codigos_cie10", "pcl"},
            "paciente": {"documento", "nombre", "fecha_nacimiento", "direccion", "telefono", "email"},
            "rehabilitacion": {"id_ingreso", "fecha_ingreso", "proveedor", "estado"},
        },
        "funciones_ayuda": {
            "parsear_siniestros_positiva": "Convierte filas de tabla SINIESTROS a lista de dicts",
            "parsear_rehab_integral_positiva": "Convierte filas de REHAB INTEGRAL a lista de dicts",
            "extraer_cie10_de_diagnostico": "Extrae código CIE10 del texto",
            "fusionar_datos_positiva": "Fusiona todos los datos en un solo JSON",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# PRUEBA
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    guia = extraer_datos_positiva("1193143688")
    print(f"=== GUÍA DE EXTRACCIÓN POSITIVA ===")
    print(f"Portal: {guia['portal']}")
    print(f"Paciente CC: {guia['cc_paciente']}")
    print(f"Total pasos: {guia['total_pasos']}\n")
    
    for paso in guia["pasos"]:
        print(f"  Paso {paso['orden']}: {paso['nombre']}")
        print(f"    {paso['descripcion']}")
        print()
    
    # Probar parseo
    print("=== PRUEBA PARSEO SINIESTROS ===")
    test_filas = [
        ["1193143688", "503463870", "02/03/2026", "AT", "Propios del Trabajo", "", "Sin determinar", "CALIFICADO", "", "Severo", ""],
        ["1193143688", "503476658", "08/04/2026", "AT", "Propios del Trabajo", "", "0", "CALIFICADO", "", "Alta Inmediata", ""],
    ]
    resultado = parsear_siniestros_positiva(test_filas)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    
    # Probar extracción CIE10
    print("\n=== PRUEBA CIE10 ===")
    print(f"  'S611 HERIDA DE DEDO...' → '{extraer_cie10_de_diagnostico('S611 HERIDA DE DEDO(S) DE LA MANO')}'")
