"""
Backup diario de storage/ (excluye audios pesados).
Sube a destino local (./storage/backups/YYYYMMDD.tar.gz) y notifica a Manu.
"""
import os
import sys
import json
import tarfile
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime, timezone


def _vacuumar_db(db_path: Path, temp_dir: Path) -> Path:
    """Copia limpia via VACUUM INTO para evitar inconsistencia con DB en uso."""
    respaldo = temp_dir / db_path.name
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(f"VACUUM INTO '{respaldo}'")
    finally:
        conn.close()
    return respaldo


def crear_backup() -> Path:
    storage = Path(os.getenv("STORAGE_DIR", "./storage"))
    backup_dir = Path(os.getenv("BACKUP_DESTINO", "./storage/backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)

    fecha = datetime.now().strftime("%Y%m%d_%H%M")
    archivo = backup_dir / f"backup_{fecha}.tar.gz"

    excluir = {"backups", "audios_temp", "workflow_audios", "playwright_sessions", "screenshots"}

    # Vacuumar todos los .db antes de backupear
    temp_dir = backup_dir / ".tmp_vacuum"
    temp_dir.mkdir(exist_ok=True)
    db_replacements = {}
    try:
        for item in storage.rglob("*.db"):
            if any(p.name in excluir for p in item.parents):
                continue
            try:
                db_replacements[str(item)] = _vacuumar_db(item, temp_dir)
            except Exception as e:
                _log(f"aviso: no se pudo vacuumar {item.name}: {e}")

        with tarfile.open(archivo, "w:gz") as tar:
            for item in storage.iterdir():
                if item.name in excluir:
                    continue
                tar.add(item, arcname=item.name)
            for orig_str, vac_path in db_replacements.items():
                arcname = str(Path(orig_str).relative_to(storage))
                tar.add(vac_path, arcname=arcname)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    tamano_mb = archivo.stat().st_size / 1024 / 1024
    _log(f"backup OK: {archivo.name} ({tamano_mb:.1f} MB)")
    return archivo


def limpiar_backups_viejos(retener: int = 14):
    backup_dir = Path(os.getenv("BACKUP_DESTINO", "./storage/backups"))
    archivos = sorted(backup_dir.glob("backup_*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    for viejo in archivos[retener:]:
        viejo.unlink()
        _log(f"borrado: {viejo.name}")


async def _notificar_fallo(error: str):
    try:
        from backend.notificador import enviar_telegram
        enviar_telegram(f"Backup RILO fallo: {error}")
    except: pass

def ejecutar_backup():
    try:
        archivo = crear_backup()
        limpiar_backups_viejos()

        # Registrar estado del backup
        status_path = Path(os.getenv("STORAGE_DIR", "./storage")) / "backup_status.json"
        try:
            status_path.write_text(json.dumps({
                "ultimo_ok": datetime.now(timezone.utc).isoformat(),
                "tamano_bytes": archivo.stat().st_size,
                "archivo": archivo.name,
            }, indent=2))
        except Exception as e:
            _log(f"aviso: no se pudo escribir backup_status.json: {e}")

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
