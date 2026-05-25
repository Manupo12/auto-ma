"""
Paso 10: Telegram a Sandra cuando el workflow termina.
"""
import os
from datetime import datetime
from typing import List


def _log(msg: str):
    import sys
    print(f"[NOTIFICAR {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def notificar(task_id: str, paciente_nombre: str, paciente_cc: str,
              formatos_generados: List[dict], warnings: List[str],
              dashboard_url: str = None, resumen_verificacion: dict = None,
              discrepancias: list = None, requiere_confirmacion_motivo: str = "") -> bool:
    from backend.notificador import enviar_telegram

    url = dashboard_url or os.getenv("DASHBOARD_URL", "")
    cantidad = len(formatos_generados)
    nombre = paciente_nombre or f"CC {paciente_cc}"

    lines = [f"Listo! Procese los datos de {nombre}."]
    if cantidad == 1:
        lines.append("1 formato generado.")
    else:
        lines.append(f"{cantidad} formatos generados.")

    if resumen_verificacion:
        r = resumen_verificacion
        lines.append(f"\nVerificacion portales: {r.get('confirmados',0)}/{r.get('total',0)} OK")
        if r.get('discrepancias', 0) > 0:
            lines.append(f"ATENCION: {r['discrepancias']} discrepancia(s)")
        if r.get('faltantes', 0) > 0:
            lines.append(f"Faltan completar {r['faltantes']} campos")

    if requiere_confirmacion_motivo:
        lines.append(f"\nCONFIRMACION REQUERIDA: {requiere_confirmacion_motivo}")

    if warnings:
        lines.append(f"\n{len(warnings)} advertencia(s):")
        for w in warnings[:3]:
            lines.append(f"  - {w[:100]}")

    if url:
        lines.append(f"\nAbre el dashboard: {url}/paciente/{paciente_cc}")
    else:
        lines.append("\n(Abre el dashboard en tu computador para revisarlos)")

    mensaje = "\n".join(lines)
    return enviar_telegram(mensaje)


def ejecutar(task_id: str, paciente_nombre: str, paciente_cc: str,
              formatos_generados: list, warnings: list,
              resumen_verificacion: dict = None, discrepancias: list = None,
              requiere_confirmacion_motivo: str = "") -> dict:
    ok = notificar(task_id, paciente_nombre, paciente_cc, formatos_generados, warnings,
                   resumen_verificacion=resumen_verificacion, discrepancias=discrepancias,
                   requiere_confirmacion_motivo=requiere_confirmacion_motivo)
    return {"ok": ok, "telegram_enviado": ok}
