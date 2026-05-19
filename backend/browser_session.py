"""
[DEPRECATED] — Lógica migrada a backend/playwright_real/session.py

Este archivo se mantiene como referencia de la estrategia de sesión.
La implementación real ahora usa Playwright con storage_state persistente.

Manejo de sesión expirada para portales — capa ⑧ del flujo v2.

Los portales de salud (Medifolios, ARL Positiva) cierran sesión en 5-15 min.
Este módulo define la estrategia de detección y re-autenticación para que
el flujo de extracción no se rompa a la mitad.

ESTRATEGIA:
   1. Detección proactiva: antes de cada acción, verificar que estamos donde debemos
   2. Re-autenticación: si se detecta login, volver a loguear y restaurar estado
  3. Máximo 3 reintentos por sesión
  4. Guardar progreso parcial después de cada extracción exitosa

NO es un script que se ejecuta solo — es una guía de patrones que el agente
debe seguir al interactuar con los portales vía browser tools.
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Callable
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE SESIÓN POR PORTAL
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PortalSession:
    """Estado de una sesión con un portal."""
    portal: str                          # 'medifolios' o 'positiva'
    url: str
    username: str
    password: str
    last_login: Optional[datetime] = None
    current_url: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    session_timeout_minutes: int = 15    # Tiempo antes de que expire
    refresh_before_minutes: int = 10      # Refrescar preventivamente
    data_extracted: dict = field(default_factory=dict)
    extraction_progress: str = ""         # Último paso completado
    is_authenticated: bool = False

    @property
    def needs_refresh(self) -> bool:
        """¿Toca re-autenticar preventivamente?"""
        if not self.last_login or not self.is_authenticated:
            return True
        elapsed = (datetime.now() - self.last_login).total_seconds() / 60
        return elapsed > self.refresh_before_minutes

    @property
    def is_expired(self) -> bool:
        """¿La sesión ya expiró?"""
        if not self.last_login or not self.is_authenticated:
            return True
        elapsed = (datetime.now() - self.last_login).total_seconds() / 60
        return elapsed > self.session_timeout_minutes


# ═══════════════════════════════════════════════════════════════════════════
# DETECCIÓN DE LOGIN / SESIÓN EXPIRADA
# ═══════════════════════════════════════════════════════════════════════════

# Palabras clave que indican que estamos en la página de login
LOGIN_INDICATORS = [
    "iniciar sesión", "iniciar sesion", "ingresar", "acceder",
    "usuario", "contraseña", "password", "login", "log in",
    "su sesión ha expirado", "sesión expirada", "sesion expirada",
    "session expired", "timeout", "por favor inicie sesión",
    "ha sido desconectado", "vuelva a ingresar",
]

# Palabras clave que indican que estamos autenticados (post-login exitoso)
AUTH_SUCCESS_INDICATORS = [
    "bienvenido", "bienvenida", "dashboard", "panel", "inicio",
    "cerrar sesión", "cerrar sesion", "salir", "logout",
    "consultar", "buscar", "pacientes", "historias", "siniestros",
    "módulo", "modulo", "menú", "menu",
]

# URLs de login para cada portal
LOGIN_URLS = {
    "medifolios": "https://www.server0medifolios.net/",
    "positiva": "https://positivacuida.positiva.gov.co/cas/login",
}


def detectar_pagina_actual(snapshot_text: str, current_url: str) -> str:
    """
    Analiza el snapshot y URL para determinar en qué página estamos.
    
    Returns:
        'login' — estamos en la página de login
        'dashboard' — estamos autenticados y en el dashboard
        'expired' — sesión expiró (estamos en login pero teníamos sesión)
        'unknown' — no se puede determinar
        'error' — página de error
    """
    text_lower = snapshot_text.lower()
    url_lower = current_url.lower() if current_url else ""

    # ¿URL de login?
    for portal, login_url in LOGIN_URLS.items():
        if login_url.lower() in url_lower:
            return "login"

    # ¿Indicadores de login en el texto?
    login_hits = sum(1 for ind in LOGIN_INDICATORS if ind in text_lower)
    if login_hits >= 2:
        return "expired" if login_hits >= 3 else "login"
    if login_hits == 1:
        # Un solo hit puede ser falso positivo
        return "login" if "login" in url_lower or "session" in url_lower else "unknown"

    # ¿Dashboard?
    auth_hits = sum(1 for ind in AUTH_SUCCESS_INDICATORS if ind in text_lower)
    if auth_hits >= 2:
        return "dashboard"

    # ¿Error?
    if any(e in text_lower for e in ["error", "no disponible", "500", "403", "404"]):
        return "error"

    return "unknown"


# ═══════════════════════════════════════════════════════════════════════════
# PATRONES DE RE-AUTENTICACIÓN POR PORTAL
# ═══════════════════════════════════════════════════════════════════════════

def get_login_steps(portal: str) -> List[dict]:
    """
    Devuelve los pasos de login para cada portal.
    Cada paso es un dict para que el agente sepa qué hacer.
    """
    if portal == "medifolios":
        return [
            {
                "accion": "navegar",
                "url": "{MEDIFOLIOS_URL}",
                "descripcion": "Ir a la página de login de Medifolios",
            },
            {
                "accion": "esperar",
                "segundos": 3,
                "descripcion": "Esperar que cargue la página",
            },
            {
                "accion": "tomar_snapshot",
                "descripcion": "Ver si hay campos de login visibles",
            },
            {
                "accion": "llenar",
                "campo": "usuario / documento / username / user",
                "valor": "{MEDIFOLIOS_USER}",
                "descripcion": "Llenar campo de usuario/documento",
            },
            {
                "accion": "llenar",
                "campo": "contraseña / password / clave",
                "valor": "{MEDIFOLIOS_PASS}",
                "descripcion": "Llenar campo de contraseña",
            },
            {
                "accion": "click",
                "boton": "Ingresar / Enviar / Login / Entrar",
                "descripcion": "Click en botón de login",
            },
            {
                "accion": "esperar",
                "segundos": 5,
                "descripcion": "Esperar que cargue el dashboard",
            },
            {
                "accion": "verificar",
                "descripcion": "Verificar que estamos en el dashboard (snapshot + URL)",
            },
        ]
    elif portal == "positiva":
        return [
            {
                "accion": "navegar",
                "url": "{POSITIVA_URL}",
                "descripcion": "Ir a la página de login de ARL Positiva",
            },
            {
                "accion": "esperar",
                "segundos": 3,
                "descripcion": "Esperar que cargue el formulario CAS",
            },
            {
                "accion": "tomar_snapshot",
                "descripcion": "Identificar campos del formulario CAS",
            },
            {
                "accion": "llenar",
                "campo": "usuario / username / documento",
                "valor": "{POSITIVA_USER}",
                "descripcion": "Llenar campo de usuario",
            },
            {
                "accion": "llenar",
                "campo": "contraseña / password / clave",
                "valor": "{POSITIVA_PASS}",
                "descripcion": "Llenar campo de contraseña",
            },
            {
                "accion": "click",
                "boton": "Iniciar sesión / Ingresar / Entrar / Login",
                "descripcion": "Click en botón de login",
            },
            {
                "accion": "esperar",
                "segundos": 5,
                "descripcion": "Esperar redirección post-login",
            },
            {
                "accion": "verificar",
                "descripcion": "Verificar que estamos en el dashboard (snapshot + URL)",
            },
        ]
    return []


# ═══════════════════════════════════════════════════════════════════════════
# SAVEGUARDIA DE PROGRESO
# ═══════════════════════════════════════════════════════════════════════════

PROGRESS_FILE = "/root/fisioterapia/storage/browser_progress.json"


def guardar_progreso(session: PortalSession) -> None:
    """Guarda el progreso de extracción para poder retomar."""
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)

    progress = {
        "portal": session.portal,
        "last_login": session.last_login.isoformat() if session.last_login else None,
        "current_url": session.current_url,
        "retry_count": session.retry_count,
        "extraction_progress": session.extraction_progress,
        "data_extracted": session.data_extracted,
        "timestamp": datetime.now().isoformat(),
    }

    # Cargar progreso existente (puede haber de ambos portales)
    try:
        with open(PROGRESS_FILE, "r") as f:
            all_progress = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_progress = {}

    all_progress[session.portal] = progress

    with open(PROGRESS_FILE, "w") as f:
        json.dump(all_progress, f, indent=2, ensure_ascii=False)


def cargar_progreso(portal: str) -> Optional[dict]:
    """Carga el progreso guardado para un portal."""
    try:
        with open(PROGRESS_FILE, "r") as f:
            all_progress = json.load(f)
        return all_progress.get(portal)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# FLUJO DE VERIFICACIÓN PRE-ACCIÓN (patrón que el agente debe seguir)
# ═══════════════════════════════════════════════════════════════════════════

"""
PATRÓN VERIFICAR-ANTES-DE-ACTUAR:

ANTES de cada browser_click, browser_type, o extracción de datos:

1. browser_snapshot(full=false) → obtener estado actual de la página
2. browser_console() → ver si hay errores JS (sesión rota)
3. Si session.is_expired O detectar_pagina_actual() == 'login'/'expired':
   a. Guardar progreso actual (guardar_progreso)
   b. Ejecutar get_login_steps(portal) paso a paso
   c. Actualizar session.last_login = datetime.now()
   d. session.retry_count += 1
   e. Si retry_count > max_retries → alertar y abortar
   f. Si login exitoso → restaurar URL donde iba
   g. Reintentar acción que falló
4. Si NO expiró pero session.needs_refresh:
   a. Hacer una acción ligera (click en "Inicio" o refresh suave)
   b. Actualizar last_login
5. Si todo OK → ejecutar acción normalmente

EJEMPLO DE USO POR EL AGENTE:

# Antes de buscar un paciente:
snapshot = browser_snapshot()
estado = detectar_pagina_actual(snapshot, current_url)
if estado in ('login', 'expired'):
    # Re-autenticar
    browser_navigate(LOGIN_URLS[portal])
    browser_type("@username_field", creds['user'])
    browser_type("@password_field", creds['pass'])
    browser_click("@login_button")
    # Verificar
    snapshot = browser_snapshot()
    if detectar_pagina_actual(snapshot, current_url) == 'dashboard':
        session.last_login = datetime.now()
    else:
        session.retry_count += 1
        if session.retry_count > session.max_retries:
            raise Exception("No se pudo re-autenticar después de 3 intentos")
# Continuar con la acción original...
"""


# ═══════════════════════════════════════════════════════════════════════════
# PRUEBA DE CONCEPTOS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Probar detección de página
    tests = [
        ("Iniciar sesión - Usuario: [____] Contraseña: [____] [Ingresar]", "https://www.server0medifolios.net/"),
        ("Bienvenido, SANDRA PATRICIA | Cerrar sesión | Dashboard | Consultar Pacientes", "https://www.server0medifolios.net/dashboard"),
        ("Su sesión ha expirado. Por favor inicie sesión nuevamente.", "https://www.server0medifolios.net/login?expired=1"),
        ("Error 500 - Internal Server Error", "https://positivacuida.positiva.gov.co/error"),
        ("Panel de control - Buscar siniestro - Módulo de consultas", "https://positivacuida.positiva.gov.co/dashboard"),
    ]

    print("=== DETECCIÓN DE PÁGINA ===")
    for texto, url in tests:
        estado = detectar_pagina_actual(texto, url)
        print(f"  URL: {url[:50]}...")
        print(f"  Estado: {estado}\n")

    # Probar PortalSession
    print("=== PORTAL SESSION ===")
    session = PortalSession(
        portal="medifolios",
        url="https://www.server0medifolios.net/",
        username="55162801-2",
        password="55162801-2",
    )
    print(f"  Needs refresh (sin login): {session.needs_refresh}")
    print(f"  Is expired (sin login): {session.is_expired}")

    session.last_login = datetime.now() - timedelta(minutes=12)
    print(f"  Needs refresh (12 min): {session.needs_refresh}")
    print(f"  Is expired (12 min): {session.is_expired}")

    session.last_login = datetime.now() - timedelta(minutes=2)
    print(f"  Needs refresh (2 min): {session.needs_refresh}")
    print(f"  Is expired (2 min): {session.is_expired}")

    # Probar get_login_steps
    print("\n=== LOGIN STEPS MEDIFOLIOS ===")
    for step in get_login_steps("medifolios"):
        print(f"  [{step['accion']}] {step['descripcion']}")

    print("\n=== LOGIN STEPS POSITIVA ===")
    for step in get_login_steps("positiva"):
        print(f"  [{step['accion']}] {step['descripcion']}")
