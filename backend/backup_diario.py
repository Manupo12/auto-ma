"""
Backup diario de storage/ (excluye audios pesados).
Sube a destino local (./storage/backups/YYYYMMDD.tar.gz) y notifica a Manu.
"""
import os
import sys
import tarfile
import shutil
from pathlib import Path
from datetime import datetime


def _log(msg: str):
    print(f"[BACKUP {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def crear_backup() -> Path:
    storage = Path(os.getenv("STORAGE_DIR", "./storage"))
    backup_dir = Path(os.getenv("BACKUP_DESTINO", "./storage/backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)

    fecha = datetime.now().strftime("%Y%m%d_%H%M")
    archivo = backup_dir / f"backup_{fecha}.tar.gz"

    excluir = {"backups", "audios_temp", "workflow_audios", "playwright_sessions", "screenshots"}

    with tarfile.open(archivo, "w:gz") as tar:
        for item in storage.iterdir():
            if item.name in excluir:
                continue
            tar.add(item, arcname=item.name)

    tamano_mb = archivo.stat().st_size / 1024 / 1024
    _log(f"backup OK: {archivo.name} ({tamano_mb:.1f} MB)")
    return archivo


def limpiar_backups_viejos(retener: int = 14):
    backup_dir = Path(os.getenv("BACKUP_DESTINO", "./storage/backups"))
    archivos = sorted(backup_dir.glob("backup_*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    for viejo in archivos[retener:]:
        viejo.unlink()
        _log(f"borrado: {viejo.name}")


async def ejecutar_backup():
    try:
        archivo = crear_backup()
        limpiar_backups_viejos()
        from backend.notificador import enviar_telegram
        tamano_mb = archivo.stat().st_size / 1024 / 1024
        enviar_telegram(f"💾 Backup diario OK: {archivo.name} ({tamano_mb:.1f} MB). Backups retenidos: 14.")
    except Exception as e:
        _log(f"error: {e}")
        try:
            from backend.notificador import enviar_telegram
            enviar_telegram(f"⚠️ Backup diario FALLÓ: {e}")
        except Exception:
            pass
