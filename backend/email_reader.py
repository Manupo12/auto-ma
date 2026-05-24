"""
Lector de correos Gmail — Extrae agenda de citas de Medifolios.

Los correos de Medifolios llegan con el asunto:
  "Citas programadas para el [DIA] [FECHA]"
Y el cuerpo contiene una tabla con:
  Hora | Paciente | Teléfono | Servicio

Este módulo:
1. Se conecta a Gmail vía IMAP
2. Busca correos de "medifolios" o "citas programadas"
3. Extrae pacientes, horas y servicios
4. Retorna lista estructurada para dashboard + notificaciones
"""
import imaplib
import email
import re
import os
import unicodedata
from datetime import datetime, timedelta, date
from email.header import decode_header
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class Cita:
    paciente: str
    telefono: str
    hora: str           # "08:10"
    servicio: str       # "TERAPIA FISICA INTEGRAL"
    fecha: str          # "2026-05-16"
    es_nueva: bool = False  # ¿Primera vez en el sistema?


@dataclass 
class AgendaDia:
    fecha: str
    citas: List[Cita] = field(default_factory=list)
    total: int = 0


# Patrones de parsing del correo de Medifolios
RE_FECHA_ASUNTO = re.compile(
    r'(?:SABADO|DOMINGO|LUNES|MARTES|MIERCOLES|JUEVES|VIERNES|S[AÁ]BADO|MIÉRCOLES)\s+'
    r'(\d{1,2})\s+DE\s+(\w+),\s*(?:DEL\s+)?(\d{4})',
    re.IGNORECASE
)

RE_LINEA_CITA = re.compile(
    r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+'   # Fecha Hora
    r'(.+?)\s+'                                   # Nombre paciente
    r'(\d{7,10})\s+'                              # Telefono
    r'(.+)',                                       # Servicio
    re.IGNORECASE
)

RE_LINEA_CITA_SIN_TELEFONO = re.compile(
    r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+'   # Fecha Hora
    r'(.+?)\s{2,}'                                # Nombre paciente (requiere doble espacio)
    r'(.+)',                                       # Servicio
    re.IGNORECASE
)

MESES = {
    'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
    'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
    'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
}


def conectar_gmail() -> Optional[imaplib.IMAP4_SSL]:
    """Conecta a Gmail vía IMAP usando credenciales de entorno."""
    email_addr = os.getenv("GMAIL_USER", "")
    app_pass = os.getenv("GMAIL_APP_PASSWORD", "")
    
    if not email_addr or not app_pass:
        print("⚠️  GMAIL_USER o GMAIL_APP_PASSWORD no configurados en .env")
        print("   Sandra necesita crear una 'contraseña de aplicación' en:")
        print("   https://myaccount.google.com/apppasswords")
        return None
    
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(email_addr, app_pass)
        mail.select("INBOX")
        return mail
    except Exception as e:
        print(f"❌ Error conectando a Gmail: {e}")
        return None


def buscar_correos_agenda(mail: imaplib.IMAP4_SSL, dias_atras: int = 3) -> List[Dict]:
    """
    Busca correos de agenda de Medifolios en los últimos N días.
    
    El asunto típico es:
      "Citas programadas para el SABADO 16 DE MAYO, DEL 2026"
    
    También busca en SPAM y en la carpeta principal.
    """
    resultados = []
    
    # También buscar en INBOX
    for carpeta in ["INBOX", "[Gmail]/Spam", "[Gmail]/Todos"]:
        try:
            mail.select(carpeta)
        except:
            continue
        
        # Buscar correos recientes con palabras clave
        for query in [
            'SUBJECT "citas programadas"',
            'SUBJECT "agenda" FROM "medifolios"',
            'FROM "noreply@medifolios"',
            'FROM "server0medifolios"',
            'SUBJECT "Citas programadas para el"',
        ]:
            try:
                status, messages = mail.search(None, query)
                if status != "OK" or not messages[0]:
                    continue
                
                for num in messages[0].split()[-20:]:  # Últimos 20 correos
                    status, data = mail.fetch(num, "(RFC822)")
                    if status != "OK":
                        continue
                    
                    for response_part in data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            asunto = decodificar_header(msg["Subject"])
                            fecha_envio = msg["Date"]
                            
                            resultados.append({
                                "asunto": asunto,
                                "fecha_envio": fecha_envio,
                                "msg": msg,
                                "carpeta": carpeta,
                            })
            except:
                continue
    
    return resultados


def decodificar_header(header_val) -> str:
    """Decodifica headers MIME (pueden estar en base64/quoted-printable)."""
    if not header_val:
        return ""
    try:
        decoded_parts = decode_header(header_val)
        return " ".join(
            part.decode(charset or "utf-8") if isinstance(part, bytes) else str(part)
            for part, charset in decoded_parts
        )
    except:
        return str(header_val)


def extraer_citas_de_correo(msg) -> AgendaDia:
    """
    Extrae citas del cuerpo de un correo de Medifolios.
    
    El formato típico:
    Hora\tPaciente\tTeléfono\tServicio
    """
    agenda = AgendaDia(fecha="", citas=[], total=0)
    
    # Extraer cuerpo del correo
    cuerpo = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    cuerpo = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                except:
                    pass
                break
    else:
        try:
            cuerpo = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
        except:
            pass
    
    if not cuerpo:
        return agenda
    
    # Extraer fecha del asunto
    asunto = decodificar_header(msg["Subject"])
    match_fecha = RE_FECHA_ASUNTO.search(asunto)
    if match_fecha:
        dia, mes_nombre, anio = match_fecha.groups()
        mes_normalizado = "".join(
            c for c in unicodedata.normalize("NFD", mes_nombre.lower())
            if unicodedata.category(c) != "Mn"
        )
        mes_num = MESES.get(mes_normalizado, "01")
        agenda.fecha = f"{anio}-{mes_num.zfill(2)}-{dia.zfill(2)}"
    
    # Extraer citas línea por línea
    # Patrón: "2026-05-16 08:10  JAIRO ZUÑIGA CAIZA  3143733241  TERAPIA FISICA INTEGRAL"
    lineas = cuerpo.split("\n")
    for linea in lineas:
        match = RE_LINEA_CITA.search(linea)
        if match:
            fecha_hora, paciente, telefono, servicio = match.groups()
        else:
            match = RE_LINEA_CITA_SIN_TELEFONO.search(linea)
            if not match:
                continue
            fecha_hora, paciente, servicio = match.groups()
            telefono = ""
        fecha_str = fecha_hora[:10]  # "2026-05-16"
        hora_str = fecha_hora[11:16]  # "08:10"
        
        cita = Cita(
            paciente=paciente.strip(),
            telefono=(telefono or "").strip(),
            hora=hora_str,
            servicio=servicio.strip(),
            fecha=fecha_str,
        )
        agenda.citas.append(cita)
    
    # También intentar el formato alternativo (solo texto)
    if not agenda.citas:
        # Formato: "2026-05-16 08:10\tJAIRO ZUÑIGA CAIZA\n3143733241\t\tTERAPIA..."
        bloques = re.split(r'\n\s*\n', cuerpo)
        for bloque in bloques:
            lineas_bloque = [l.strip() for l in bloque.split('\n') if l.strip()]
            for i, linea in enumerate(lineas_bloque):
                # Detectar línea de fecha + nombre
                match = re.match(
                    r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+(.+)',
                    linea
                )
                if match:
                    fecha_hora = match.group(1)
                    nombre = match.group(2).strip()
                    telefono = ""
                    servicio = ""
                    
                    # Siguiente línea puede ser teléfono
                    if i + 1 < len(lineas_bloque) and re.match(r'^\d{7,10}$', lineas_bloque[i+1]):
                        telefono = lineas_bloque[i+1]
                        # La línea después del teléfono es el servicio
                        if i + 2 < len(lineas_bloque):
                            servicio = lineas_bloque[i+2]
                    
                    # Si no, buscar en líneas siguientes
                    if not servicio and i + 1 < len(lineas_bloque):
                        for j in range(i+1, min(i+3, len(lineas_bloque))):
                            if any(kw in lineas_bloque[j].upper() for kw in ['TERAPIA', 'EVALUACIÓN', 'EVALUACION', 'CONSULTA']):
                                servicio = lineas_bloque[j]
                                break
                    
                    if nombre and not any(kw in nombre.upper() for kw in ['REHABILITACIÓN', 'SANDRA PATRICIA', 'ESTAS SON', 'TOTAL:', 'HORA']):
                        cita = Cita(
                            paciente=nombre,
                            telefono=telefono,
                            hora=fecha_hora[11:16],
                            servicio=servicio,
                            fecha=fecha_hora[:10],
                        )
                        agenda.citas.append(cita)
    
    agenda.total = len(agenda.citas)
    return agenda


def obtener_agenda_manana() -> Optional[AgendaDia]:
    """
    Busca el correo de agenda de Medifolios para MAÑANA.
    Retorna AgendaDia con las citas o None si no hay.
    """
    mail = conectar_gmail()
    if not mail:
        return None
    
    try:
        manana = date.today() + timedelta(days=1)
        correos = buscar_correos_agenda(mail, dias_atras=3)
        mail.logout()
        
        for correo in correos:
            agenda = extraer_citas_de_correo(correo["msg"])
            if agenda.fecha:
                try:
                    fecha_agenda = datetime.strptime(agenda.fecha, "%Y-%m-%d").date()
                    if fecha_agenda == manana:
                        return agenda
                except:
                    pass
        
        return None
    except Exception as e:
        print(f"❌ Error obteniendo agenda: {e}")
        return None


def obtener_agenda_fecha(fecha_buscar: date) -> Optional[AgendaDia]:
    """Busca agenda para una fecha específica."""
    mail = conectar_gmail()
    if not mail:
        return None
    
    try:
        correos = buscar_correos_agenda(mail, dias_atras=7)
        mail.logout()
        
        for correo in correos:
            agenda = extraer_citas_de_correo(correo["msg"])
            if agenda.fecha:
                try:
                    fecha_agenda = datetime.strptime(agenda.fecha, "%Y-%m-%d").date()
                    if fecha_agenda == fecha_buscar:
                        return agenda
                except:
                    pass
        
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def formatear_mensaje_telegram(agenda: AgendaDia) -> str:
    """Formatea una agenda para enviar por Telegram."""
    if not agenda.citas:
        return f"📅 Mañana {agenda.fecha} — ¡Sin citas programadas! ☀️"
    
    fecha_obj = datetime.strptime(agenda.fecha, "%Y-%m-%d")
    dia_semana = fecha_obj.strftime("%A").upper()
    dia_semana_es = {
        'MONDAY': 'LUNES', 'TUESDAY': 'MARTES', 'WEDNESDAY': 'MIÉRCOLES',
        'THURSDAY': 'JUEVES', 'FRIDAY': 'VIERNES', 'SATURDAY': 'SÁBADO', 
        'SUNDAY': 'DOMINGO'
    }
    dia_es = dia_semana_es.get(dia_semana, dia_semana)
    
    msg = f"📅 *Agenda {dia_es} {fecha_obj.strftime('%d/%m/%Y')}*\n"
    msg += f"Total: {agenda.total} citas\n\n"
    
    for cita in agenda.citas[:15]:  # Máximo 15 para no saturar
        emoji = "🆕 " if cita.es_nueva else "   "
        msg += f"{emoji}⏰ {cita.hora} — *{cita.paciente}*\n"
        msg += f"          📞 {cita.telefono}\n"
        msg += f"          🏥 {cita.servicio}\n\n"
    
    if len(agenda.citas) > 15:
        msg += f"... y {len(agenda.citas) - 15} citas más\n"
    
    return msg


# ─── Prueba rápida ────────────────────────────────────────────────
if __name__ == "__main__":
    agenda = obtener_agenda_manana()
    if agenda:
        print(formatear_mensaje_telegram(agenda))
    else:
        print("No se encontró agenda para mañana.")
