#!/usr/bin/env python3
"""
Orquestador principal del flujo v2.

Integra las 7 capas:
  ① Extractor Medifolios (browser — guiado por agente)
  ② Extractor Positiva (browser — guiado por agente)  
  ③ Fusionador de datos
  ④ Validador JSON
  ⑤ Selector de formato
  ⑥ Doc generator (existente)
  ⑦ Verificador QA (existente)

Uso:
  # Solo validar
  python backend/orquestador.py --datos storage/data/1193143688-completo.json --solo-validar
  
  # Fusionar y generar
  python backend/orquestador.py --medifolios data/m.json --positiva data/p.json --generar
  
  # Con estado explícito
  python backend/orquestador.py --datos data/paciente.json --estado SEGUIMIENTO --generar
"""

import sys
import os
import json
import argparse
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.json_validator import validar_para_formatos, reporte_legible
from backend.format_selector import seleccionar_con_contexto


def main():
    parser = argparse.ArgumentParser(description="Orquestador de documentos clínicos v2")
    parser.add_argument("--estado", choices=["NUEVO", "SEGUIMIENTO", "CIERRE", "PRUEBA_TRABAJO"],
                        help="Estado del caso (si no, auto-detecta)")
    parser.add_argument("--forzar", help="Formatos específicos separados por coma")
    parser.add_argument("--datos", help="Ruta al archivo JSON con datos del paciente")
    parser.add_argument("--solo-validar", action="store_true",
                        help="Solo validar, no generar documentos")
    parser.add_argument("--generar", action="store_true",
                        help="Generar documentos después de validar")
    parser.add_argument("--fusionar", action="store_true",
                        help="Fusionar datos de --medifolios y --positiva antes de validar")
    parser.add_argument("--medifolios", help="Ruta al JSON de Medifolios")
    parser.add_argument("--positiva", help="Ruta al JSON de Positiva")
    parser.add_argument("--audio", help="Ruta al JSON de audio (datos cualitativos)")
    args = parser.parse_args()

    # ── 0. Fusionar si es necesario ───────────────────────────────
    datos = None

    if args.fusionar:
        from backend.fusionador import fusionar_todo, guardar_datos_completos

        datos_med = None
        datos_pos = None
        datos_aud = None

        if args.medifolios:
            with open(args.medifolios, "r", encoding="utf-8") as f:
                datos_med = json.load(f)
        if args.positiva:
            with open(args.positiva, "r", encoding="utf-8") as f:
                datos_pos = json.load(f)
        if args.audio:
            with open(args.audio, "r", encoding="utf-8") as f:
                datos_aud = json.load(f)

        datos = fusionar_todo(datos_med, datos_pos, datos_aud, estado_caso=args.estado or "")
        cc = datos.get("paciente", {}).get("documento", "sin_cc")
        path = guardar_datos_completos(datos, cc)
        print(f"🔗 Datos fusionados y guardados: {path}")

    # ── 1. Cargar datos ──────────────────────────────────────────
    if datos is None:
        if args.datos:
            with open(args.datos, "r", encoding="utf-8") as f:
                datos = json.load(f)
            print(f"📂 Datos cargados: {args.datos}")
        else:
            print("❌ Se requiere --datos ruta/a/datos.json (o usar --fusionar con --medifolios/--positiva)")
            sys.exit(1)

    # ── 2. Seleccionar formatos ──────────────────────────────────
    forzar = args.forzar.split(",") if args.forzar else None
    ctx = seleccionar_con_contexto(datos, estado=args.estado, forzar=forzar)

    print(f"\n👤 Paciente: {ctx['paciente']}")
    print(f"📋 Estado detectado: {ctx['estado_detectado']}")
    print(f"📄 Formatos a generar ({ctx['total']}):")
    for nombre in ctx["nombres_formatos"]:
        print(f"   - {nombre}")

    # ── 3. Validar JSON ─────────────────────────────────────────
    print(f"\n{'='*60}")
    print("🔍 VALIDANDO JSON...")
    print(f"{'='*60}")

    resultados = validar_para_formatos(datos, ctx["formatos"])
    reporte = reporte_legible(resultados)
    print(reporte)

    # Guardar reporte
    reporte_path = Path("/root/fisioterapia/storage/reports")
    reporte_path.mkdir(parents=True, exist_ok=True)
    paciente_id = ctx['paciente'].replace(" ", "_").lower()[:30]
    reporte_file = reporte_path / f"validacion_{paciente_id}.txt"
    with open(reporte_file, "w") as f:
        f.write(reporte)
    print(f"\n📝 Reporte guardado: {reporte_file}")

    # ── 4. Determinar qué formatos se pueden generar ─────────────
    formatos_validos = []
    formatos_bloqueados = []

    for fmt, res in resultados.items():
        if res["ok"]:
            formatos_validos.append((fmt, res["json_corregido"]))
        else:
            formatos_bloqueados.append((fmt, res["errores"]))

    if formatos_bloqueados:
        print(f"\n🚫 {len(formatos_bloqueados)} formato(s) BLOQUEADOS por campos faltantes:")
        for fmt, errores in formatos_bloqueados:
            print(f"   ❌ {fmt}:")
            for e in errores:
                print(f"      {e}")

    if args.solo_validar:
        print("\n✅ Validación completada (modo --solo-validar). No se generaron documentos.")
        return

    # ── 5. Generar documentos ───────────────────────────────────
    if args.generar and formatos_validos:
        print(f"\n{'='*60}")
        print("📝 GENERANDO DOCUMENTOS...")
        print(f"{'='*60}")

        # Importar aquí para no forzar la dependencia si solo se valida
        try:
            from backend.doc_generator import generar_documento
        except ImportError as e:
            print(f"⚠️  No se pudo importar doc_generator: {e}")
            print("   Los documentos NO se generaron. Revise que doc_generator.py esté disponible.")
            return

        for fmt, json_corregido in formatos_validos:
            try:
                docx_path = generar_documento(fmt, json_corregido)
                print(f"   ✅ {fmt}: {docx_path}")
            except Exception as e:
                print(f"   ❌ {fmt}: ERROR - {e}")

    elif not formatos_validos:
        print("\n⚠️  Ningún formato se puede generar. Corrija los campos faltantes.")
    else:
        print("\n💡 Use --generar para crear los documentos, o --solo-validar para solo validar.")

    # ── 6. Resumen final ────────────────────────────────────────
    print(f"\n{'='*60}")
    print("📊 RESUMEN")
    print(f"{'='*60}")
    print(f"   Paciente: {ctx['paciente']}")
    print(f"   Estado: {ctx['estado_detectado']}")
    print(f"   Formatos OK: {len(formatos_validos)}")
    print(f"   Formatos bloqueados: {len(formatos_bloqueados)}")

    # Total de warnings
    total_warnings = sum(len(r["warnings"]) for r in resultados.values())
    if total_warnings > 0:
        print(f"   ⚠️  Campos auto-completados con [VERIFICAR]: {total_warnings}")


if __name__ == "__main__":
    main()
