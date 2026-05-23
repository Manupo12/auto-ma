"""
Cron de pre-extracción nocturna — APScheduler dentro de FastAPI.

Triggers (hora COL):
  21:00 → revisar_email_y_extraer: lee agenda del día siguiente, extrae cada paciente
  06:30 → recordatorio_matinal: Telegram con resumen de citas del día

Configurable vía .env: CRON_HORA_NOCHE, CRON_COOLDOWN_PACIENTES_S, FASE_A_CRON_ENABLED
"""
import os
import sys
import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz


COL = pytz.timezone("America/Bogota")

scheduler = AsyncIOScheduler(timezone=COL)

CRON_ENABLED = os.getenv("FASE_A_CRON_ENABLED", "false").lower() == "true"
HORA_NOCHE = int(os.getenv("CRON_HORA_NOCHE", "21"))
COOLDOWN_S = int(os.getenv("CRON_COOLDOWN_PACIENTES_S", "30"))


def _log(msg: str):
    print(f"[CRON {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


async def _extraer_paciente(cc: str):
    """Extrae un paciente y espera el cooldown."""
    from backend.playwright_real.orquestador import extraer_paciente_completo
    _log(f"extrayendo CC {cc}...")
    try:
        datos = await extraer_paciente_completo(cc, guardar=True)
        disc = datos.get("_meta", {}).get("discrepancias", [])
        parcial = datos.get("_meta", {}).get("parcial", False)
        if disc:
            _log(f"CC {cc}: {len(disc)} discrepancia(s) — {json.dumps(disc, ensure_ascii=False)}")
        if parcial:
            _log(f"CC {cc}: extracción PARCIAL")
        else:
            _log(f"CC {cc}: OK")
    except Exception as e:
        _log(f"CC {cc}: error {type(e).__name__}: {e}")


async def revisar_email_y_extraer():
    """Job nocturno: revisar agenda, extraer cada paciente."""
    if not CRON_ENABLED:
        _log("CRON: desactivado (FASE_A_CRON_ENABLED=false)")
        return

    _log("═══ CRON NOCTURNO INICIADO ═══")

    try:
        from backend.notificador import api_check_ahora
        agenda = api_check_ahora()
        citas = agenda.get("citas", [])
        if not citas:
            _log("CRON: sin citas mañana")
            try:
                from backend.notificador import enviar_telegram
                enviar_telegram("🌙 Sin citas para mañana. Noche tranquila.")
            except Exception:
                pass
            return

        _log(f"CRON: {len(citas)} cita(s) mañana")

        # Notificar inicio
        try:
            from backend.notificador import enviar_telegram
            pacientes = [c["paciente"] for c in citas]
            enviar_telegram(
                f"🌙 Mañana {len(citas)} cita(s): {', '.join(pacientes)}.\n"
                f"Empiezo a buscar sus datos en los portales..."
            )
        except Exception:
            pass

        # Extraer cada paciente
        for i, cita in enumerate(citas):
            cc = cita.get("cc", "")
            if cc and len(cc) >= 6:
                _log(f"CRON: [{i+1}/{len(citas)}] CC {cc}")
                await _extraer_paciente(cc)
                if i < len(citas) - 1:
                    await asyncio.sleep(COOLDOWN_S)

        # Notificar fin
        try:
            from backend.notificador import enviar_telegram
            enviar_telegram(
                f"✅ Listo. Datos cargados para los {len(citas)} pacientes de mañana."
            )
        except Exception:
            pass

    except Exception as e:
        _log(f"CRON: error en lote: {type(e).__name__}: {e}")
        try:
            from backend.notificador import enviar_telegram
            enviar_telegram(f"⚠️ El proceso nocturno tuvo un error: {e}")
        except Exception:
            pass

    _log("═══ CRON NOCTURNO FINALIZADO ═══")


async def recordatorio_matinal():
    """Job matinal: recordatorio de citas del día."""
    if not CRON_ENABLED:
        return
    try:
        from backend.notificador import api_get_agenda
        agenda = api_get_agenda()
        if agenda and agenda.get("citas"):
            citas = agenda["citas"]
            from backend.notificador import enviar_telegram
            enviar_telegram(
                f"☀️ Buenos días, Sandra. Hoy tienes {len(citas)} cita(s):\n"
                + "\n".join(f"  🕐 {c.get('hora', '?')} — {c.get('paciente', '?')} (CC {c.get('cc', '?')})"
                           for c in citas)
                + "\n\nLos datos de los pacientes ya están cargados ✅"
            )
    except Exception as e:
        _log(f"MATINAL: error {e}")


def _guardar_ultimo_run():
    import json, os
    p = os.path.join(os.getenv("STORAGE_DIR","./storage"), "last_cron_run.json")
    with open(p, "w") as f: json.dump({"fecha": str(__import__("datetime").datetime.now())}, f)

def iniciar_scheduler():
    """Configura y arranca los jobs. Llámame desde server.py startup."""
    if not CRON_ENABLED:
        _log("SCHEDULER: desactivado (FASE_A_CRON_ENABLED=false)")
        return

    scheduler.add_job(
        revisar_email_y_extraer,
        CronTrigger(hour=HORA_NOCHE, minute=0, timezone=COL),
        id="pre_extraccion_nocturna",
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        recordatorio_matinal,
        CronTrigger(hour=6, minute=30, timezone=COL),
        id="recordatorio_matinal",
        misfire_grace_time=1800,
    )

    scheduler.add_job(
        ejecutar_backup_diario,
        CronTrigger(hour=int(os.getenv("BACKUP_HORA", "23")), minute=0, timezone=COL),
        id="backup_diario",
        misfire_grace_time=3600,
    )

    scheduler.start()
    _log(f"SCHEDULER: iniciado. Noche a las {HORA_NOCHE}:00, matinal 06:30, backup 23:00 COL")


async def ejecutar_backup_diario():
    from backend.backup_diario import ejecutar_backup
    await ejecutar_backup()


def obtener_estado() -> dict:
    """Estado del scheduler (para /api/cron/estado)."""
    jobs = scheduler.get_jobs()
    return {
        "activo": CRON_ENABLED,
        "jobs": [
            {
                "id": j.id,
                "proxima": j.next_run_time.isoformat() if j.next_run_time else None,
            }
            for j in jobs
        ],
    }
