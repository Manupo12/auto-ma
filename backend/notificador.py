"""
Sistema de notificaciones — Telegram + Dashboard.

Flujo:
1. 8:30 PM → Revisa agenda de mañana vía Gmail
2. Si hay citas → Notifica por Telegram + actualiza dashboard
3. Si no hay → "Sin citas mañana ☀️"
4. Recordatorios: 1 día antes + 1 hora antes de cada cita
"""
import os
import json
import requests
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Optional

from backend.email_reader import (
    obtener_agenda_manana, obtener_agenda_fecha, Cita, AgendaDia,
    formatear_mensaje_telegram
)

# ─── Configuración ──────────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./storage"))


def enviar_telegram(mensaje: str) -> bool:
    """Envía un mensaje por Telegram a Sandra."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️  Telegram no configurado. Falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    # Partir mensajes largos
    lineas = mensaje.split("\n")
    chunks = []
    chunk = ""
    for linea in lineas:
        if len(chunk) + len(linea) + 1 > 4000:
            chunks.append(chunk)
            chunk = linea
        else:
            chunk = chunk + "\n" + linea if chunk else linea
    if chunk:
        chunks.append(chunk)
    
    for i, chunk in enumerate(chunks):
        try:
            resp = requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": chunk,
                "parse_mode": "Markdown" if i == 0 else None,
            }, timeout=10)
            if resp.status_code != 200:
                print(f"❌ Telegram error: {resp.text}")
                return False
        except Exception as e:
            print(f"❌ Telegram fallo: {e}")
            return False
    
    return True


# ─── Almacenamiento de agenda ───────────────────────────────────

def guardar_agenda(agenda: AgendaDia):
    """Guarda la agenda en storage para que el dashboard la lea."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    archivo = STORAGE_DIR / "agenda_actual.json"
    
    data = {
        "fecha": agenda.fecha,
        "total": agenda.total,
        "actualizado": datetime.now().isoformat(),
        "citas": [
            {
                "paciente": c.paciente,
                "telefono": c.telefono,
                "hora": c.hora,
                "servicio": c.servicio,
                "fecha": c.fecha,
                "es_nueva": c.es_nueva,
            }
            for c in agenda.citas
        ]
    }
    
    archivo.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def cargar_agenda_guardada() -> Optional[Dict]:
    """Carga la última agenda guardada."""
    archivo = STORAGE_DIR / "agenda_actual.json"
    if archivo.exists():
        return json.loads(archivo.read_text())
    return None


# ─── Detección de pacientes nuevos ──────────────────────────────

def cargar_historial_pacientes() -> set:
    """Carga el set de pacientes ya conocidos."""
    archivo = STORAGE_DIR / "pacientes_historial.json"
    if archivo.exists():
        data = json.loads(archivo.read_text())
        return set(data.get("pacientes", []))
    return set()


def guardar_historial_pacientes(pacientes: set):
    """Guarda el historial de pacientes."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    archivo = STORAGE_DIR / "pacientes_historial.json"
    archivo.write_text(json.dumps({
        "pacientes": list(pacientes),
        "actualizado": datetime.now().isoformat(),
        "total": len(pacientes),
    }, indent=2, ensure_ascii=False))


def marcar_nuevos(agenda: AgendaDia):
    """Marca pacientes nuevos en la agenda y actualiza historial."""
    historial = cargar_historial_pacientes()
    nuevos_nombres = set()
    
    for cita in agenda.citas:
        nombre_key = cita.paciente.upper().strip()
        if nombre_key not in historial:
            cita.es_nueva = True
            nuevos_nombres.add(cita.paciente)
        historial.add(nombre_key)
    
    guardar_historial_pacientes(historial)
    return nuevos_nombres


# ─── Check programado (8:30 PM) ────────────────────────────────

def check_agenda_manana() -> Dict:
    """
    Revisa agenda de MAÑANA vía Gmail.
    Retorna resumen para API/dashboard.
    """
    print(f"🔍 [{datetime.now().strftime('%H:%M')}] Revisando agenda de mañana...")
    
    agenda = obtener_agenda_manana()
    
    if not agenda:
        return {
            "status": "error",
            "mensaje": "No se pudo obtener la agenda (¿Gmail configurado?)",
            "citas": [],
        }
    
    # Marcar pacientes nuevos
    nuevos = marcar_nuevos(agenda)
    
    # Guardar para dashboard
    guardar_agenda(agenda)
    
    # Notificar Telegram
    if agenda.citas:
        msg = formatear_mensaje_telegram(agenda)
        if nuevos:
            msg += f"\n🆕 *{len(nuevos)} paciente(s) nuevo(s):*\n"
            for n in nuevos:
                msg += f"  • {n}\n"
        enviar_telegram(msg)
    else:
        manana = date.today() + timedelta(days=1)
        enviar_telegram(f"📅 Mañana {manana.strftime('%d/%m/%Y')} — ¡Sin citas! ☀️")
    
    return {
        "status": "ok",
        "fecha": agenda.fecha,
        "total": agenda.total,
        "nuevos": len(nuevos),
        "nuevos_nombres": list(nuevos),
        "citas": [
            {
                "paciente": c.paciente,
                "hora": c.hora,
                "servicio": c.servicio,
                "telefono": c.telefono,
                "es_nueva": c.es_nueva,
            }
            for c in agenda.citas
        ]
    }


def check_recordatorios() -> List[Dict]:
    """
    Revisa si hay que enviar recordatorios.
    
    - 1 día antes: notifica agenda completa
    - 1 hora antes: notifica cita individual
    """
    ahora = datetime.now()
    recordatorios = []
    
    agenda_data = cargar_agenda_guardada()
    if not agenda_data:
        return recordatorios
    
    fecha_agenda = agenda_data.get("fecha", "")
    if not fecha_agenda:
        return recordatorios
    
    try:
        fecha_obj = datetime.strptime(fecha_agenda, "%Y-%m-%d")
    except:
        return recordatorios
    
    # ¿Es para mañana? → Recordatorio 1 día antes
    manana = date.today() + timedelta(days=1)
    if fecha_obj.date() == manana:
        total = agenda_data.get("total", 0)
        if total > 0:
            recordatorios.append({
                "tipo": "dia_antes",
                "mensaje": f"📅 Recordatorio: Mañana tienes {total} citas.",
                "hora_envio": ahora.strftime("%H:%M"),
            })
    
    # ¿Es hoy? → Recordatorios 1 hora antes
    hoy = date.today()
    if fecha_obj.date() == hoy:
        for cita in agenda_data.get("citas", []):
            try:
                hora_cita = datetime.strptime(
                    f"{fecha_agenda} {cita['hora']}", 
                    "%Y-%m-%d %H:%M"
                )
                minutos_faltan = (hora_cita - ahora).total_seconds() / 60
                
                # Entre 55 y 65 minutos antes → Recordatorio
                if 55 <= minutos_faltan <= 65:
                    msg = (
                        f"⏰ *Recordatorio de cita*\n\n"
                        f"📍 {cita['hora']} — *{cita['paciente']}*\n"
                        f"📞 {cita['telefono']}\n"
                        f"🏥 {cita['servicio']}"
                    )
                    enviar_telegram(msg)
                    recordatorios.append({
                        "tipo": "1_hora_antes",
                        "paciente": cita["paciente"],
                        "hora": cita["hora"],
                    })
            except:
                pass
    
    return recordatorios


# ─── API Endpoint helpers ──────────────────────────────────────

def api_check_ahora() -> Dict:
    """Forzar check de agenda ahora (para probar)."""
    return check_agenda_manana()


def api_get_agenda() -> Optional[Dict]:
    """Obtener agenda actual para el dashboard."""
    return cargar_agenda_guardada()
