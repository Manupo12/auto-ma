"""
[DEPRECATED] — Reemplazado por backend/playwright_real/medifolios.py

Este archivo se mantiene como referencia documental de los pasos de extracción.
La implementación real ahora usa Playwright (ver playwright_real/).

Extractor Medifolios — Sub-flujo A del flujo v2.

Extrae datos del paciente desde Medifolios usando browser automation.
El agente sigue estos pasos para navegar y extraer información.

Fuentes de datos en Medifolios:
   1. Agenda Citas → Popup Detalle Solicitud → SINIESTRO (en Observaciones)
   2. Pacientes → Formulario → DATOS PERSONALES + DATOS GENERALES
   3. Pacientes → Historia Clínica → Visión Clinica General

Output: JSON parcial que se fusiona con los datos de Positiva y Audio.

Uso por el agente:
  from backend.extractor_medifolios import extraer_datos_medifolios
  
  # El agente ejecuta cada paso con browser tools
  datos = extraer_datos_medifolios(cc_paciente="1193143688")
  # → devuelve instrucciones paso a paso
"""

import json
import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════

MEDIFOLIOS_URL = "https://www.server0medifolios.net/"
MEDIFOLIOS_USER = "55162801-2"
MEDIFOLIOS_PASS = "55162801-2"
PROFESIONAL_NOMBRE = "SANDRA PATRICIA POLANIA"

# Campos que extraemos de cada sección
CAMPOS_PACIENTES = {
    "datos_personales": [
        ("numero_id", "paciente.documento"),
        ("nombre1", "paciente.nombre1"),
        ("nombre2", "paciente.nombre2"),
        ("apellido1", "paciente.apellido1"),
        ("apellido2", "paciente.apellido2"),
        ("fecha_nacimiento", "paciente.fecha_nacimiento"),
        ("telefono", "paciente.telefono"),
        ("direccion", "paciente.direccion"),
        ("email", "paciente.email"),
        ("vereda", "paciente.barrio"),
        # Sexo, RH, Estado Civil, Zona: de comboboxes
    ],
    "datos_generales": [
        ("slct_eps_paciente", "paciente.eps_ips"),
        ("slct_afp_paciente", "paciente.afp"),
        ("slct_arl_paciente", "paciente.arl"),
        ("slct_empresa_paciente", "empresa.nombre"),
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
# PASOS DE EXTRACCIÓN (guía para el agente)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PasoExtraccion:
    """Un paso que el agente debe ejecutar con browser tools."""
    orden: int
    nombre: str
    descripcion: str
    accion: str  # 'navegar', 'login', 'click', 'extraer', 'verificar', 'js'
    detalle: dict = field(default_factory=dict)
    datos_extraidos: dict = field(default_factory=dict)


def obtener_pasos_extraccion(cc_paciente: str) -> List[PasoExtraccion]:
    """
    Devuelve la lista de pasos que el agente debe seguir para extraer
    todos los datos de un paciente desde Medifolios.
    
    Args:
        cc_paciente: Cédula del paciente a buscar (sin puntos ni guiones)
    """
    pasos = []
    
    # ── FASE 1: Login ─────────────────────────────────────────────
    pasos.append(PasoExtraccion(
        orden=1, nombre="Login Medifolios",
        descripcion="Navegar a Medifolios e iniciar sesión",
        accion="login",
        detalle={
            "url": MEDIFOLIOS_URL,
            "usuario": MEDIFOLIOS_USER,
            "contraseña": MEDIFOLIOS_PASS,
            "campo_usuario": "textbox 'USUARIO'",
            "campo_password": "textbox 'CONTRASEÑA'",
            "boton_login": "button 'Ingresar'",
            "popup_cerrar": "dialog 'Cambia tu contraseña' → button 'Close'",
        }
    ))
    
    # ── FASE 2: Extraer SINIESTRO desde Agenda Citas ───────────────
    pasos.append(PasoExtraccion(
        orden=2, nombre="Navegar a Agenda Citas",
        descripcion="Menú hamburguesa → Agenda Citas",
        accion="click",
        detalle={
            "menu": "link 'Bienvenido, Sandra'",
            "opcion": "link 'Agenda Citas'",
        }
    ))
    
    pasos.append(PasoExtraccion(
        orden=3, nombre="Seleccionar profesional",
        descripcion="En el dropdown, seleccionar SANDRA PATRICIA POLANIA",
        accion="click",
        detalle={
            "selector": "link 'SELECCIONE PROFESIONAL/EQUIPO'",
            "opcion_sandra": "SANDRA PATRICIA POLANIA - TODOS LOS PUNTOS DE ATENCION (value='168-0')",
            "metodo_alternativo": "Usar JS: select.value='168-0'; select.dispatchEvent(new Event('change'))",
        }
    ))
    
    pasos.append(PasoExtraccion(
        orden=4, nombre="Buscar cita del paciente",
        descripcion="En el calendario semanal, buscar al paciente por nombre o scroll. Hacer click en su cita.",
        accion="click",
        detalle={
            "metodo": "Buscar en eventos .fc-event que contengan el nombre del paciente",
            "alternativo": "Navegar a otra fecha si no aparece en la semana actual",
            "js_helper": "document.querySelectorAll('.fc-event').forEach(e => { if(e.textContent.includes('NOMBRE')) e.click(); })",
        }
    ))
    
    pasos.append(PasoExtraccion(
        orden=5, nombre="Extraer datos del popup Detalle Solicitud",
        descripcion="En el popup, extraer todos los campos visibles y el siniestro de Observaciones",
        accion="extraer",
        detalle={
            "campos": [
                "IDENTIFICACIÓN (#txt_num_identificacion)",
                "NOMBRES (#txt_nombre_completo)",
                "EDAD (#txt_edad_paciente)",
                "TELEFONO (#txt_telefono)",
                "EMAIL (#txt_email)",
                "EMPRESA CLIENTE (link con nombre de empresa)",
                "SERVICIO (#slct_servicio_agenda_medico)",
                "No. AUTORIZACIÓN (#txt_num_autorizacion)",
                "PROFESIONAL (link)",
                "OBSERVACIONES (#txt_observaciones) ← contiene 'NO. SINIESTROXXXXX'",
            ],
            "extraer_siniestro": "Buscar en observaciones con regex: r'NO\\.?\\s*SINIESTRO\\s*(\\d+)'",
            "tabs_extra": ["Historial de Citas", "Solicitudes Pendientes"],
        }
    ))
    
    # ── FASE 3: Extraer DATOS desde Pacientes ──────────────────────
    pasos.append(PasoExtraccion(
        orden=6, nombre="Navegar a Pacientes",
        descripcion="Menú hamburguesa → Pacientes",
        accion="click",
        detalle={
            "menu": "link 'Bienvenido, Sandra'",
            "opcion": "link 'Pacientes'",
        }
    ))
    
    pasos.append(PasoExtraccion(
        orden=7, nombre="Buscar paciente en formulario",
        descripcion=f"En el campo Núm. Documento, escribir '{cc_paciente}' y presionar Enter o click en lupa",
        accion="js",
        detalle={
            "campo": "input#numero_id",
            "valor": cc_paciente,
            "js": f"""
                var f = document.getElementById('numero_id');
                f.value = '{cc_paciente}';
                f.dispatchEvent(new Event('input', {{bubbles:true}}));
                f.dispatchEvent(new Event('change', {{bubbles:true}}));
                f.dispatchEvent(new KeyboardEvent('keydown', {{key:'Enter',keyCode:13,bubbles:true}}));
            """,
            "verificar": "Verificar que nombre1.value no esté vacío",
        }
    ))
    
    pasos.append(PasoExtraccion(
        orden=8, nombre="Extraer DATOS PERSONALES",
        descripcion="Extraer todos los campos del formulario DATOS PERSONALES",
        accion="extraer",
        detalle={
            "js_extract": """
                var d = {};
                ['numero_id','nombre1','nombre2','apellido1','apellido2',
                 'fecha_nacimiento','telefono','tel3_paciente','direccion',
                 'email','vereda'].forEach(function(id) {
                    var el = document.getElementById(id);
                    if (el) d[id] = el.value || el.textContent?.trim();
                });
                // Comboboxes
                ['slct_sexo_biologico','slct_identidad_genero','slct_rh',
                 'slct_estado_civil','slct_zona'].forEach(function(id) {
                    var el = document.getElementById(id);
                    if (el) d[id] = el.options?.[el.selectedIndex]?.text || el.value;
                });
                JSON.stringify(d);
            """,
        }
    ))
    
    pasos.append(PasoExtraccion(
        orden=9, nombre="Extraer DATOS GENERALES",
        descripcion="Extraer EPS, AFP, ARL, Empresa Cliente y demás",
        accion="extraer",
        detalle={
            "js_extract": """
                var d = {};
                ['slct_eps_paciente','slct_afp_paciente','slct_arl_paciente',
                 'slct_empresa_paciente','slct_regimen'].forEach(function(id) {
                    var el = document.getElementById(id);
                    if (el) d[id] = el.options?.[el.selectedIndex]?.text || el.value;
                });
                JSON.stringify(d);
            """,
        }
    ))
    
    # ── FASE 4: Extraer HISTORIA CLÍNICA ───────────────────────────
    pasos.append(PasoExtraccion(
        orden=10, nombre="Navegar a Historia Clínica",
        descripcion="En el sidebar, click en 'Historia Clínica', luego pestaña 'Visión Clinica General'",
        accion="click",
        detalle={
            "sidebar": "link 'Historia Clínica' (ref del accordion)",
            "tab": "tab 'Visión Clinica General'",
        }
    ))
    
    pasos.append(PasoExtraccion(
        orden=11, nombre="Extraer Visión Clinica General",
        descripcion="Extraer alertas, alergias, antecedentes, evaluación, etc.",
        accion="extraer",
        detalle={
            "js_extract": """
                var iframe = document.querySelector('#content_historias iframe');
                var doc = iframe?.contentDocument || document;
                var d = {};
                // Extraer texto de todas las secciones
                doc.querySelectorAll('h5, strong, [class*="alert"]').forEach(function(el) {
                    var key = el.textContent.trim().substring(0, 50);
                    var val = el.parentElement?.textContent?.trim()?.substring(0, 500);
                    if (key && val) d[key] = val;
                });
                JSON.stringify(d);
            """,
        }
    ))
    
    return pasos


# ═══════════════════════════════════════════════════════════════════════════
# PARSEO DE DATOS EXTRAÍDOS
# ═══════════════════════════════════════════════════════════════════════════

def parsear_siniestro_observaciones(observaciones: str) -> Optional[str]:
    """Extrae el número de siniestro del campo observaciones."""
    match = re.search(r'NO\.?\s*SINIESTRO\s*(\d+)', observaciones, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def parsear_datos_pacientes_medifolios(js_output: dict) -> dict:
    """Convierte los datos extraídos del formulario al formato JSON estándar."""
    paciente = {}
    empresa = {}
    
    # Mapeo de campos del formulario → JSON estándar
    mapeo = {
        "numero_id": ("paciente", "documento"),
        "nombre1": ("paciente", "nombre1"),
        "nombre2": ("paciente", "nombre2"),
        "apellido1": ("paciente", "apellido1"),
        "apellido2": ("paciente", "apellido2"),
        "fecha_nacimiento": ("paciente", "fecha_nacimiento"),
        "telefono": ("paciente", "telefono"),
        "tel3_paciente": ("paciente", "telefono_aux"),
        "direccion": ("paciente", "direccion"),
        "email": ("paciente", "email"),
        "vereda": ("paciente", "barrio"),
        "slct_sexo_biologico": ("paciente", "sexo"),
        "slct_rh": ("paciente", "rh"),
        "slct_estado_civil": ("paciente", "estado_civil"),
        "slct_zona": ("paciente", "zona"),
        "slct_eps_paciente": ("paciente", "eps_ips"),
        "slct_afp_paciente": ("paciente", "afp"),
        "slct_arl_paciente": ("paciente", "arl"),
        "slct_empresa_paciente": ("empresa", "nombre"),
        "slct_regimen": ("paciente", "regimen"),
    }
    
    for campo_js, (seccion, campo_json) in mapeo.items():
        valor = js_output.get(campo_js, "")
        if valor:
            if seccion == "paciente":
                paciente[campo_json] = valor
            else:
                empresa[campo_json] = valor
    
    # Construir nombre completo
    nombres = []
    for k in ["nombre1", "nombre2"]:
        if paciente.get(k):
            nombres.append(paciente.pop(k))
    apellidos = []
    for k in ["apellido1", "apellido2"]:
        if paciente.get(k):
            apellidos.append(paciente.pop(k))
    
    if nombres or apellidos:
        paciente["nombre"] = " ".join(nombres + apellidos)
    
    return {"paciente": paciente, "empresa": empresa}


def fusionar_datos_medifolios(
    datos_agenda: dict,
    datos_pacientes: dict,
    datos_historia: dict,
) -> dict:
    """
    Fusiona los datos extraídos de las 3 fuentes de Medifolios
    en un solo JSON compatible con el doc_generator.
    """
    resultado = {
        "paciente": {},
        "empresa": {},
        "siniestro": {},
        "consulta": {},
    }
    
    # 1. Datos de Agenda Citas (siniestro + datos básicos)
    if datos_agenda:
        resultado["siniestro"]["id_siniestro"] = datos_agenda.get("siniestro", "")
        resultado["paciente"]["documento"] = datos_agenda.get("identificacion", "")
        resultado["paciente"]["nombre"] = datos_agenda.get("nombres", "")
        resultado["paciente"]["edad"] = datos_agenda.get("edad", "")
        resultado["paciente"]["telefono"] = datos_agenda.get("telefono", "")
        resultado["paciente"]["email"] = datos_agenda.get("email", "")
        resultado["empresa"]["nombre"] = datos_agenda.get("empresa", "")
        resultado["siniestro"]["num_autorizacion"] = datos_agenda.get("autorizacion", "")
        resultado["consulta"]["servicio"] = datos_agenda.get("servicio", "")
    
    # 2. Datos de Pacientes (formulario completo)
    if datos_pacientes:
        pac = datos_pacientes.get("paciente", {})
        emp = datos_pacientes.get("empresa", {})
        for k, v in pac.items():
            if v and not resultado["paciente"].get(k):
                resultado["paciente"][k] = v
        for k, v in emp.items():
            if v and not resultado["empresa"].get(k):
                resultado["empresa"][k] = v
    
    # 3. Datos de Historia Clínica
    if datos_historia:
        resultado["historia_clinica"] = datos_historia
    
    return resultado


# ═══════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL (guía para el agente)
# ═══════════════════════════════════════════════════════════════════════════

def extraer_datos_medifolios(cc_paciente: str) -> dict:
    """
    Guía de extracción para el agente.
    Devuelve los pasos a seguir y la estructura esperada del JSON.
    
    El agente debe:
    1. Ejecutar cada paso con browser tools
    2. Recopilar los datos extraídos
    3. Llamar a fusionar_datos_medifolios() con los datos recopilados
    4. Guardar el JSON en storage/data/[cc]-medifolios.json
    """
    pasos = obtener_pasos_extraccion(cc_paciente)
    
    return {
        "portal": "medifolios",
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
            "siniestro": {"id_siniestro": "string"},
            "paciente": {"documento", "nombre", "fecha_nacimiento", "edad", "telefono", "direccion", "email", "eps_ips", "afp", "arl"},
            "empresa": {"nombre"},
            "consulta": {"servicio"},
            "historia_clinica": "dict con datos de Visión Clinica General",
        },
        "funciones_ayuda": {
            "parsear_siniestro_observaciones": "Extrae siniestro de texto 'NO. SINIESTROXXXXX'",
            "parsear_datos_pacientes_medifolios": "Convierte output JS a JSON estándar",
            "fusionar_datos_medifolios": "Fusiona las 3 fuentes en un solo JSON",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# PRUEBA
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Mostrar la guía de extracción
    guia = extraer_datos_medifolios("1193143688")
    print(f"=== GUÍA DE EXTRACCIÓN MEDIFOLIOS ===")
    print(f"Portal: {guia['portal']}")
    print(f"Paciente CC: {guia['cc_paciente']}")
    print(f"Total pasos: {guia['total_pasos']}\n")
    
    for paso in guia["pasos"]:
        print(f"  Paso {paso['orden']}: {paso['nombre']}")
        print(f"    {paso['descripcion']}")
        print(f"    Acción: {paso['accion']}")
        if paso['detalle']:
            for k, v in paso['detalle'].items():
                if isinstance(v, str) and len(v) > 100:
                    v = v[:100] + "..."
                print(f"    {k}: {v}")
        print()
    
    # Probar parseo de siniestro
    print("=== PRUEBA PARSEO SINIESTRO ===")
    test_obs = "12 SESIONES\nNO. SINIESTRO503401505\nADMISION 28397"
    siniestro = parsear_siniestro_observaciones(test_obs)
    print(f"  Input: {test_obs}")
    print(f"  Output: {siniestro}")
    
    # Probar parseo de datos
    print("\n=== PRUEBA PARSEO DATOS ===")
    test_js = {
        "numero_id": "36169589",
        "nombre1": "NUBIA", "nombre2": "MARIA",
        "apellido1": "RIVERA", "apellido2": "SUAREZ",
        "fecha_nacimiento": "1961-08-01",
        "telefono": "3144054406",
        "direccion": "CALLE 1H 24 14",
        "email": "RIVERANUBIAMARIA@GMAIL.COM",
        "slct_eps_paciente": "Famisanar",
        "slct_afp_paciente": "Protección",
        "slct_empresa_paciente": "POSITIVA COMPANIA DE SEGUROS SA",
    }
    resultado = parsear_datos_pacientes_medifolios(test_js)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
