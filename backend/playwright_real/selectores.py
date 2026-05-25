"""
Selectores CSS/XPath/JS de los portales Medifolios y ARL Positiva.

Origen: skills/flujo-browser/references/ (7 pasadas de exploración).
Cuando un portal cambie HTML, actualizar SOLO este archivo.

Cada selector tiene 3 fallbacks: CSS principal, XPath alternativo, texto visible.
"""

# ═══════════════════════════════════════════════════════════════════════
# MEDIFOLIOS
# ═══════════════════════════════════════════════════════════════════════

MEDI_URL = "https://www.server0medifolios.net/"

MEDI_LOGIN = {
    "usuario_input": "#txt_usuario_login, input[name='USUARIO'], input[type='text']",
    "password_input": "#txt_password_login, input[name='CONTRASEÑA'], input[type='password']",
    "submit_button": "button:has-text('Iniciar Sesión'), button[type='submit'], input[type='submit']",
    "popup_cambia_password_close": "button:has-text('Close'), .modal .close",
    "post_login_heartbeat": "text=Bienvenido, Sandra",
}

MEDI_PACIENTES = {
    "url": "https://www.server0medifolios.net/index.php/SALUD_HOME/paciente",
    "menu_pacientes": "a:has-text('Pacientes'), [href*='SALUD_HOME/paciente']",
    "numero_id_input": "#numero_id",
    "nombre1": "#nombre1",
    "nombre2": "#nombre2",
    "apellido1": "#apellido1",
    "apellido2": "#apellido2",
    "direccion": "#direccion",
    "telefono": "#telefono",
    "email": "#email",
    "fecha_nacimiento": "#fecha_nacimiento",
    "edad": "#edad",
    "sexo": "select[name='sexo'], #sexo",
}

MEDI_AGENDA = {
    "url": "https://www.server0medifolios.net/index.php/SALUD_GESTIONCITAS/agenda_cita",
    "menu_agenda": "a:has-text('Agenda Citas'), [href*='agenda_cita']",
    "select_profesional": "select",
    "valor_sandra": "168-0",
    "cita_link_template": "a:has-text('{cc}'), tr:has-text('{cc}') a",
    "popup_detalle_observaciones": "textarea[name='observaciones'], #observaciones",
}

# JS para forzar carga de paciente (Enter nativo no dispara búsqueda)
MEDI_JS_CARGAR_PACIENTE = """
(cc) => {
    const f = document.getElementById('numero_id');
    if (!f) return false;
    f.value = cc;
    f.dispatchEvent(new Event('input', {bubbles: true}));
    f.dispatchEvent(new Event('change', {bubbles: true}));
    f.blur();
    f.focus();
    f.blur();
    f.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', keyCode:13, bubbles:true}));
    return true;
}
"""

# JS para volcar todos los campos del form de pacientes
MEDI_JS_EXTRAER_FORM = """
() => {
    const ids = ['numero_id','nombre1','nombre2','apellido1','apellido2',
                 'fecha_nacimiento','telefono','direccion','email'];
    const d = {};
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) d[id] = el.value || (el.textContent || '').trim();
    });
    ['slct_eps_paciente','slct_afp_paciente','slct_arl_paciente','slct_empresa_paciente'].forEach(id => {
        const el = document.getElementById(id);
        if (el && el.options && el.selectedIndex >= 0) {
            d[id] = el.options[el.selectedIndex].text;
        }
    });
    return d;
}
"""

# Regex para extraer siniestro del campo observaciones
MEDI_REGEX_SINIESTRO = r'NO\.?\s*SINIESTRO\s*(\d+)'


# ═══════════════════════════════════════════════════════════════════════
# ARL POSITIVA
# ═══════════════════════════════════════════════════════════════════════

POS_URL = "https://positivacuida.positiva.gov.co/cas/login?service=https://positivacuida.positiva.gov.co/web/j_spring_cas_security_check"

POS_LOGIN = {
    "usuario_input": "input[name='username'], #username",
    "password_input": "input[name='password'], #password",
    "submit_button": "button[type='submit'], input[name='submit']",
    "post_login_heartbeat": "text=MARIA GREIDY",
}

POS_CONSULTA_INTEGRAL = {
    "menu": "a:has-text('Consulta integral')",
    "tipo_id_select": "select[name='tipoIdentificacion']",
    "numero_id_input": "input[name='numeroIdentificacion'], #numeroIdentificacion",
    "buscar_button": "button:has-text('Buscar'), input[value='Buscar']",
}

POS_TABS = {
    "datos_asegurado": "a:has-text('DATOS ASEGURADO'), [data-tab='datos']",
    "siniestros": "a:has-text('SINIESTROS')",
    "rehab_integral": "a:has-text('REHABILITACIÓN INTEGRAL')",
    "gestion_aut": "a:has-text('GESTIÓN AUTORIZACIONES')",
    "evoluciones": "a:has-text('EVOLUCIONES')",
    "bitacoras": "a:has-text('BITACORAS')",
}

# Selectores por columna en la tabla SINIESTROS de Positiva
POS_TABLA_SINIESTROS = {
    "filas": "table.siniestros tbody tr, [data-tab='siniestros'] tbody tr",
    "col_siniestro": 1,
    "col_fecha": 2,
    "col_tipo_evento": 3,
    "col_pcl": 6,
    "col_diagnostico": 8,
}


# ═══════════════════════════════════════════════════════════════════════
# TIMEOUTS Y REINTENTOS
# ═══════════════════════════════════════════════════════════════════════

TIMEOUT_NAVEGACION_MS = 30_000
TIMEOUT_ELEMENTO_MS = 10_000
REINTENTOS = [2, 5, 15]  # segundos entre reintentos


# ═══════════════════════════════════════════════════════════════════════
# MEDIFOLIOS — Historia Clinica
# ═══════════════════════════════════════════════════════════════════════

MEDI_HC = {
    "urls_posibles": [
        "https://www.server0medifolios.net/index.php/SALUD_HOME/historia_clinica",
        "https://www.server0medifolios.net/index.php/SALUD_HISTORIA/historia",
    ],
    "menu_hc": "a:has-text('Historia Clinica'), a:has-text('Historia clinica'), a:has-text('HC')",
    "tabla_dx": "table:has(th:has-text('Diagnostico')), table:has(th:has-text('CIE'))",
    "input_cc_hc": "#numero_id, input[name='cc'], input[name='numero_id']",
}

MEDI_AGENDA_DETALLE = {
    "selector_filas": "table.tabla-agenda tbody tr, table tbody tr",
    "campo_observaciones": [
        "textarea[name='observaciones']",
        "#observaciones",
        "textarea:near(:text('Observaciones'))",
        ".modal textarea",
        "[class*='detalle'] textarea",
    ],
    "boton_cerrar_modal": "button:has-text('Cerrar'), button:has-text('Close'), .modal .close, .btn-close",
}

# ═══════════════════════════════════════════════════════════════════════
# ARL POSITIVA — Secciones adicionales
# ═══════════════════════════════════════════════════════════════════════

POS_REHAB_INTEGRAL = {
    "tab": [
        "a:has-text('REHABILITACION INTEGRAL')",
        "a:has-text('Rehabilitacion Integral')",
        "a:has-text('REHABILITACION INTEGRAL')",
    ],
}

POS_AUTORIZACIONES = {
    "tab": [
        "a:has-text('GESTION AUTORIZACIONES')",
        "a:has-text('Gestion Autorizaciones')",
    ],
}

POS_RHI_COMPLETO = {
    "url": "https://positivacuida.positiva.gov.co/web/rhi/consultarCaso/init",
    "input_cc": "#numeroDocumento, input[name='numeroDocumento']",
    "buscar": "button:has-text('Buscar'), button:has-text('Consultar')",
}

# Screenshot debug dir
PLAYWRIGHT_DEBUG_DIR = "./storage/playwright_debug"
