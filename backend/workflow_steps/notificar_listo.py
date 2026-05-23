"""
Paso 9: Telegram a Sandra cuando el workflow termina.

Mensaje incluye:
  - Nombre del paciente
  - Cantidad de formatos generados
  - Warnings (si los hay)
  - URL del dashboard para revisar
"""
import os
from datetime import datetime
from typing import List


def _log(msg: str):
    import sys
    print(f"[NOTIFICAR {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def notificar(task_id: str, paciente_nombre: str, paciente_cc: str,
              formatos_generados: List[dict], warnings: List[str],
              dashboard_url: str = None) -> bool:
    from backend.notificador import enviar_telegram

    url = dashboard_url or os.getenv("DASHBOARD_URL", "http://localhost:3000")
    url_paciente = f"{url}/paciente/{paciente_cc}"

    cantidad = len(formatos_generados)
    nombre = paciente_nombre or f"CC {paciente_cc}"

    lines = [f"✅ Listo! Procesé los datos de {nombre}."]
    if cantidad == 1:
        lines.append("1 formato generado.")
    else:
        lines.append(f"{cantidad} formatos generados.")

    if warnings:
        lines.append(f"\n⚠️ {len(warnings)} advertencia(s):")
        for w in warnings[:3]:
            lines.append(f"  • {w[:100]}")

    lines.append(f"\nRevisalos en: {url_paciente}")

    mensaje = "\n".join(lines)
    return enviar_telegram(mensaje)


def ejecutar(task_id: str, paciente_nombre: str, paciente_cc: str,
              formatos_generados: list, warnings: list,
              resumen_verificacion: dict = None, discrepancias: list = None) -> dict:
    ok = notificar(task_id, paciente_nombre, paciente_cc, formatos_generados, warnings)
    return {"ok": ok, "telegram_enviado": ok}
