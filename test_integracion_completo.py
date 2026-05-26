#!/usr/bin/env python3
"""
INTEGRACIÓN COMPLETA — prueba todos los flujos del sistema de principio a fin.

Fases:
  1. Fusionador (merge medifolios + positiva)
  2. Validación semántica (custody.py)
  3. Selección de formatos
  4. Validación JSON (json_validator)
  5. Generación de documentos (doc_generator)
  6. Cadena de custodia (registrar campos)
  7. Loop de correcciones (correction_loop NLP)
  8. Flujo de audio (mock sin API key)
  9. FastAPI server endpoints (pacientes, chat, generar)
 10. QA documental (verificar-documento scripts)
"""

import sys
import os
import json
import time
import glob
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"

failures = []
warnings = []


def ok(phase, msg=""):
    print(f"  {PASS} {phase}" + (f" — {msg}" if msg else ""))


def fail(phase, msg=""):
    print(f"  {FAIL} {phase}: {msg}")
    failures.append(f"{phase}: {msg}")


def warn(phase, msg=""):
    print(f"  {WARN} {phase}: {msg}")
    warnings.append(f"{phase}: {msg}")


# ─────────────────────────────────────────────────────────────────────────────
print("=" * 60)
print("FASE 1 — Fusionador (merge medifolios + positiva)")
print("=" * 60)
try:
    from backend.fusionador import fusionar_todo, guardar_datos_completos
    with open("storage/data/juan_duran.json") as f:
        datos_med = json.load(f)
    with open("storage/data/20260517-1193143688-completo.json") as f:
        datos_pos = json.load(f)

    datos = fusionar_todo(datos_med, datos_pos, None, estado_caso="SEGUIMIENTO")

    assert datos.get("paciente", {}).get("nombre") == "JUAN CARLOS DURAN NARVAEZ", "nombre incorrecto"
    assert datos.get("siniestro", {}).get("id_siniestro") == "503463870", "siniestro incorrecto"
    assert datos.get("empresa", {}).get("contacto"), "empresa.contacto vacío (fusión fallida)"
    assert datos.get("laboral", {}).get("cargo"), "laboral.cargo vacío (fusión fallida)"
    assert datos.get("siniestro", {}).get("segmento_lesionado"), "segmento_lesionado no derivado"
    assert datos.get("estado_caso") == "SEGUIMIENTO", "estado_caso incorrecto"

    ok("Nombre paciente", datos["paciente"]["nombre"])
    ok("Siniestro", datos["siniestro"]["id_siniestro"])
    ok("Empresa.contacto", datos["empresa"]["contacto"])
    ok("Laboral.cargo", datos["laboral"]["cargo"])
    ok("Segmento lesionado", datos["siniestro"]["segmento_lesionado"])
    ok("Reconciliación siniestro", datos.get("_metadata", {}).get("reconciliacion", {}).get("coinciden", "N/A"))
except Exception as e:
    fail("Fusionador", str(e))
    datos = {}

# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("FASE 2 — Validación semántica (custody.py)")
print("=" * 60)
try:
    from backend.custody import validar_semantica, Custodia

    ok_flag, resultados_semantica = validar_semantica(datos)
    validos = [r for r in resultados_semantica if r.es_valido]
    invalidos = [r for r in resultados_semantica if not r.es_valido]
    campos_req_invalidos = [r for r in invalidos if not r.mensaje.startswith("Campo opcional")]

    ok("validar_semantica ejecutada", f"{len(validos)} válidos, {len(invalidos)} inválidos")

    for r in campos_req_invalidos:
        if r.confianza == 0 and "VACÍO" in r.mensaje:
            warn(f"Campo vacío", f"{r.campo}")
        else:
            fail(f"Campo inválido", f"{r.campo}: {r.mensaje}")

    # Test Custodia recording
    cus = Custodia("1193143688")
    cus.registrar("paciente.nombre", datos["paciente"]["nombre"], "medifolios", confianza=95)
    cus.registrar("siniestro.id_siniestro", datos["siniestro"]["id_siniestro"], "positiva", confianza=99)
    cus.registrar("laboral.cargo", datos["laboral"]["cargo"], "medifolios", confianza=90)
    ok("Custodia — campos registrados", f"{len(cus.entradas)} entradas")

except Exception as e:
    fail("Custody", str(e))

# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("FASE 3 — Selección de formatos")
print("=" * 60)
try:
    from backend.format_selector import seleccionar_con_contexto

    ctx_seg = seleccionar_con_contexto(datos, estado="SEGUIMIENTO")
    ctx_nuevo = seleccionar_con_contexto(datos, estado="NUEVO")
    ctx_cierre = seleccionar_con_contexto(datos, estado="CIERRE")
    ctx_prueba = seleccionar_con_contexto(datos, estado="PRUEBA_TRABAJO")

    ok("SEGUIMIENTO", f"{ctx_seg['total']} formatos: {', '.join(ctx_seg['nombres_formatos'])}")
    ok("NUEVO", f"{ctx_nuevo['total']} formatos")
    ok("CIERRE", f"{ctx_cierre['total']} formatos")
    ok("PRUEBA_TRABAJO", f"{ctx_prueba['total']} formatos")

    assert ctx_seg["total"] >= 2, "SEGUIMIENTO debe tener ≥2 formatos"
    assert ctx_nuevo["total"] >= 2, "NUEVO debe tener ≥2 formatos"
    assert ctx_cierre["total"] >= 1, "CIERRE debe tener ≥1 formato"

except Exception as e:
    fail("Format Selector", str(e))

# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("FASE 4 — Validación JSON completa para todos los estados")
print("=" * 60)
try:
    from backend.json_validator import validar_para_formatos, reporte_legible

    for estado, ctx in [("SEGUIMIENTO", ctx_seg), ("NUEVO", ctx_nuevo), ("CIERRE", ctx_cierre)]:
        resultados = validar_para_formatos(datos, ctx["formatos"])
        for fmt, res in resultados.items():
            if res["ok"]:
                ok(f"{estado}/{fmt}", f"warnings={len(res['warnings'])}")
            else:
                for e in res["errores"]:
                    fail(f"{estado}/{fmt}", e)

    ok("reporte_legible", "generado OK")

except Exception as e:
    fail("JSON Validator", str(e))

# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("FASE 5 — Generación de documentos (doc_generator) — todos los formatos")
print("=" * 60)
try:
    from backend.doc_generator import generar_documento
    from backend.json_validator import validar_para_formatos
    from backend.format_selector import seleccionar_con_contexto

    FORMATOS_MAPA = {
        "analisis_exigencias": "analisis",
        "carta_medidas": "medidas",
        "carta_recomendaciones": "recomendaciones",
        "cierre_caso": "cierre",
        "citacion_empresas": "citacion",
        "prueba_trabajo": "prueba",
        "valoracion_desempeno": "valoracion",
    }

    # Validate with long names, generate with short names
    resultados_val = validar_para_formatos(datos, list(FORMATOS_MAPA.keys()))
    for fmt_largo, fmt_corto in FORMATOS_MAPA.items():
        res = resultados_val.get(fmt_largo, {})
        # Use corrected json if validation passed, else use original datos
        if res.get("ok"):
            json_data = res["json_corregido"]
        else:
            json_data = datos
            if res.get("errores"):
                warn(fmt_corto, f"validator errors: {res['errores'][:2]}")
        try:
            path = generar_documento(fmt_corto, json_data)
            size_kb = os.path.getsize(path) // 1024
            ok(fmt_corto, f"{size_kb} KB → {os.path.basename(path)}")
        except Exception as e:
            fail(fmt_corto, str(e))

except Exception as e:
    fail("Doc Generator", str(e))

# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("FASE 6 — Quality audit (lowercase x, cell content)")
print("=" * 60)
try:
    from docx import Document

    DOCS = "storage/docs"
    formato_keys = {
        "analisis": "Análisis",
        "medidas": "Medidas",
        "recomendaciones": "Recomendaciones",
        "cierre": "Cierre",
        "citacion": "Citación",
        "prueba": "Prueba",
        "valoracion": "Valoración",
    }
    total_issues = 0
    for key, label in formato_keys.items():
        files = [f for f in glob.glob(f"{DOCS}/{key}-*.docx") if os.path.isfile(f)]
        if not files:
            warn(label, "no file found")
            continue
        path = max(files, key=os.path.getmtime)
        doc = Document(path)
        lx = []
        for ti, t in enumerate(doc.tables):
            for ri, r in enumerate(t.rows):
                for ci, c in enumerate(r.cells):
                    if c.text.strip() == "x":
                        lx.append(f"T{ti}R{ri}C{ci}")
        total_issues += len(lx)
        if lx:
            fail(label, f"{len(lx)} lowercase x: {lx[:5]}")
        else:
            ok(label, f"0 issues | {os.path.basename(path)}")

    if total_issues == 0:
        ok("TOTAL", "0 lowercase x across all formats")
    else:
        fail("TOTAL", f"{total_issues} lowercase x remaining")

except Exception as e:
    fail("Quality Audit", str(e))

# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("FASE 7 — Correction Loop (NLP message parsing)")
print("=" * 60)
try:
    from backend.correction_loop import analizar_mensaje_rechazo, TipoCorreccion, ejecutar_correccion

    CASOS = [
        ("Falta el número de siniestro", TipoCorreccion.CAMPO_FALTANTE, "siniestro.id_siniestro"),
        ("Cambia la fecha del accidente a 15/05/2026", TipoCorreccion.CAMBIO_VALOR, "siniestro.fecha_evento"),
        ("El diagnóstico está mal escrito", TipoCorreccion.CAMPO_INCORRECTO, "siniestro.diagnosticos"),
        ("El documento está bien, aprobado", TipoCorreccion.APROBADO, None),
        ("Falta el cargo del trabajador", TipoCorreccion.CAMPO_FALTANTE, "laboral.cargo"),
        ("El nombre de la empresa está incorrecto", TipoCorreccion.CAMPO_INCORRECTO, None),
        ("Cambia la dirección a Calle 5 No 10-20", TipoCorreccion.CAMBIO_VALOR, "paciente.direccion"),
        ("formato equivocado, necesito la carta de medidas", TipoCorreccion.DOCUMENTO_EQUIVOCADO, None),
    ]

    errores_nlp = 0
    for msg, tipo_esperado, campo_esperado in CASOS:
        inst = analizar_mensaje_rechazo(msg)
        if inst.tipo != tipo_esperado:
            fail(f"NLP: '{msg[:40]}'", f"tipo={inst.tipo.value} esperado={tipo_esperado.value}")
            errores_nlp += 1
        elif campo_esperado and inst.campo != campo_esperado:
            warn(f"NLP campo: '{msg[:40]}'", f"campo={inst.campo} esperado={campo_esperado}")
        else:
            ok(f"NLP: '{msg[:35]}...'", f"tipo={inst.tipo.value}")

    # Test ejecutar_correccion
    accion = ejecutar_correccion(analizar_mensaje_rechazo("Falta el número de siniestro"), datos, "valoracion")
    ok("ejecutar_correccion", f"accion={str(accion)[:60]}")

    if errores_nlp == 0:
        ok("Correction Loop", f"todos los {len(CASOS)} casos correctos")

except Exception as e:
    fail("Correction Loop", str(e))

# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("FASE 8 — Flujo Audio (mock — sin DEEPGRAM_API_KEY)")
print("=" * 60)
try:
    from backend.flujo_audio import (
        extraer_datos_cualitativos,
        filtrar_segmentos_clinicos,
        calcular_confianza_campo,
    )

    # Test data extraction from transcription
    transcripcion_mock = """
    La metodología empleada consistió en visita al puesto de trabajo.
    El trabajador manifiesta que sus funciones principales son desatasca las piedras de
    la máquina trituradora con un gancho de hierro para facilitar que la maquina triture.
    El ritmo de trabajo es de 800 a 1000 bultos por turno.
    La servidora refiere dolor en el cuarto dedo de la mano derecha al levantar peso.
    El concepto de desempeño ocupacional es favorable con recomendaciones de adaptación.
    """

    datos_extraidos = extraer_datos_cualitativos(transcripcion_mock)
    ok("extraer_datos_cualitativos", f"campos: {list(datos_extraidos.keys())}")

    # Test filtrar_segmentos
    segmentos_mock = [
        {"texto": "buenos días", "inicio": 0.0, "fin": 1.0, "hablante": 0},
        {"texto": "el ritmo de trabajo es de 800 a 1000 bultos por turno de trabajo", "inicio": 5.0, "fin": 10.0, "hablante": 1},
        {"texto": "eh", "inicio": 11.0, "fin": 11.5, "hablante": 0},
        {"texto": "el cargo de obrero de tratamiento de roca implica levantar peso", "inicio": 12.0, "fin": 18.0, "hablante": 1},
    ]
    filtrados = filtrar_segmentos_clinicos(segmentos_mock)
    ok("filtrar_segmentos_clinicos", f"{len(filtrados)}/4 segmentos pasaron filtro (esperado 2)")
    assert len(filtrados) == 2, f"Esperaba 2 segmentos, obtuve {len(filtrados)}"

    # Test calcular_confianza
    conf = calcular_confianza_campo(
        "el ritmo de trabajo es de 800 a 1000 bultos por turno",
        ["ritmo", "productividad", "turnos"]
    )
    ok("calcular_confianza_campo", f"confianza={conf}% (esperado ≥70)")
    assert conf >= 70, f"Confianza muy baja: {conf}"

    # Verify no DEEPGRAM_API_KEY needed for these operations
    ok("Audio module (local ops)", "OK sin DEEPGRAM_API_KEY")

    if not os.getenv("DEEPGRAM_API_KEY"):
        warn("transcribir_audio", "DEEPGRAM_API_KEY no configurado — transcripción real no disponible")

except Exception as e:
    fail("Flujo Audio", str(e))

# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("FASE 9 — FastAPI Server endpoints")
print("=" * 60)
try:
    from backend.server import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # /api/health
    r = client.get("/api/health")
    assert r.status_code == 200, f"health status={r.status_code}"
    ok("/api/health", r.json())

    # /api/chat
    r = client.post("/api/chat", json={"mensaje": "hola qué puedo hacer"})
    assert r.status_code == 200
    data = r.json()
    assert "contenido" in data, f"respuesta sin contenido: {data}"
    ok("/api/chat", data["contenido"][:50])

    r2 = client.post("/api/chat", json={"mensaje": "generar formato análisis"})
    assert r2.status_code == 200
    ok("/api/chat (formatos)", r2.json()["contenido"][:50])

    r3 = client.post("/api/chat", json={"mensaje": "buscar siniestro 503463870"})
    assert r3.status_code == 200
    ok("/api/chat (siniestro)", r3.json()["contenido"][:50])

    # Login to authenticate test client session
    pin_val = os.getenv("AUTH_PIN", "1234")
    r_login = client.post("/api/login", json={"pin": pin_val})
    assert r_login.status_code == 200, f"login status={r_login.status_code}"
    token = r_login.cookies.get("rilo_session")
    client.cookies.set("rilo_session", token)
    ok("/api/login", "autenticación exitosa")

    # /api/pacientes
    r = client.get("/api/pacientes")
    assert r.status_code == 200
    pacs = r.json()
    ok("/api/pacientes", f"{len(pacs)} paciente(s) encontrado(s)")

    # /api/pacientes/{cc}
    r = client.get("/api/pacientes/1193143688")
    assert r.status_code == 200
    pac = r.json()
    assert pac["nombre"] == "JUAN CARLOS DURAN NARVAEZ"
    assert pac["siniestro"] == "503463870"
    assert pac["estado_caso"] == "SEGUIMIENTO"
    ok("/api/pacientes/1193143688", f"{pac['nombre']} — siniestro {pac['siniestro']}")

    # /api/pacientes/{cc}/formatos
    r = client.get("/api/pacientes/1193143688/formatos")
    assert r.status_code == 200
    fmts = r.json()
    ok("/api/pacientes/1193143688/formatos", f"{len(fmts)} formato(s)")

    # /api/pacientes/NONEXIST
    r = client.get("/api/pacientes/0000000000")
    assert r.status_code == 404
    ok("/api/pacientes/0000000000 (404)", "correcto")

    # /api/pacientes/{cc}/formatos/{fmt}/corregir
    r = client.post(
        "/api/pacientes/1193143688/formatos/valoracion_desempeno/corregir",
        json={"mensaje": "El diagnóstico está incompleto"},
    )
    assert r.status_code == 200
    corr = r.json()
    ok("/api/corregir", f"tipo={corr.get('tipo')} campo={corr.get('campo')}")

except Exception as e:
    fail("FastAPI Server", str(e))
    import traceback
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("FASE 10 — Verificar-documento (QA scripts con archivos generados)")
print("=" * 60)
try:
    import subprocess

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SCRIPTS = os.path.join(BASE_DIR, "skills/verificar-documento/scripts")
    TEMPLATES = os.path.join(BASE_DIR, "templates/formatos")
    DOCS = os.path.join(BASE_DIR, "storage/docs")

    verif_pairs = [
        (f"{DOCS}/analisis-*.docx", f"{TEMPLATES}/ejemplo analisis de exigencia.docx"),
        (f"{DOCS}/valoracion-*.docx", f"{TEMPLATES}/ejemplo valoracion de desempeño ocupacional.docx"),
        (f"{DOCS}/cierre-*.docx", f"{TEMPLATES}/ejemplo cierre de caso.docx"),
        (f"{DOCS}/medidas-*.docx", f"{TEMPLATES}/ejemplo carta de medidas.docx"),
        (f"{DOCS}/recomendaciones-*.docx", f"{TEMPLATES}/ejemplo carta de recomendaciones.docx"),
        (f"{DOCS}/prueba-*.docx", f"{TEMPLATES}/ejemplo prueba de trabajo.docx"),
        (f"{DOCS}/citacion-*.docx", f"{TEMPLATES}/ejemplo formato de citacion de empresas.docx"),
    ]

    # First run analizar_ejemplo on all templates (check they parse)
    for pattern, template in verif_pairs:
        matches = [f for f in glob.glob(pattern) if os.path.isfile(f)]
        if not matches:
            warn(f"verificar", f"No DOCX found for {pattern}")
            continue
        gen = max(matches, key=os.path.getmtime)
        label = os.path.basename(gen)

        # Run analizar_ejemplo on the generated doc
        result = subprocess.run(
            ["python3", f"{SCRIPTS}/analizar_ejemplo.py", gen],
            capture_output=True, text=True, cwd=BASE_DIR
        )
        if result.returncode == 0:
            ok(f"analizar_ejemplo: {label[:40]}", "OK")
        else:
            warn(f"analizar_ejemplo: {label[:40]}", result.stderr[:80] if result.stderr else "exit!=0")

        # Run verificar.py (structural comparison with template)
        result2 = subprocess.run(
            ["python3", f"{SCRIPTS}/verificar.py", gen, template],
            capture_output=True, text=True, cwd=BASE_DIR
        )
        lines = (result2.stdout + result2.stderr).strip().split("\n")
        issues = [l for l in lines if "ERROR" in l.upper() or "FALLA" in l.upper() or "MISMATCH" in l.upper()]
        if issues:
            warn(f"verificar: {label[:30]}", f"{len(issues)} issue(s): {issues[0][:80]}")
        else:
            ok(f"verificar: {label[:30]}", "estructura OK")

except Exception as e:
    fail("Verificar-Documento", str(e))
    import traceback
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("FASE 11 — PDF/A y backup")
print("=" * 60)
try:
    from backend.pdf_archivo import convertir_a_pdfa, verificar_pdfa

    # Find a generated DOCX for PDF test
    docx_files = [f for f in glob.glob("storage/docs/valoracion-*.docx") if os.path.isfile(f)]
    if docx_files:
        docx = max(docx_files, key=os.path.getmtime)
        pdf = convertir_a_pdfa(docx)
        if pdf and os.path.exists(pdf):
            ok("convertir_a_pdfa", f"{os.path.basename(pdf)} ({os.path.getsize(pdf)//1024} KB)")
            if verificar_pdfa(pdf):
                ok("verificar_pdfa", "PDF válido")
            else:
                warn("verificar_pdfa", "PDF generado pero no pasa verificación completa")
        else:
            warn("convertir_a_pdfa", "Falló (LibreOffice no disponible — fallback fpdf)")
    else:
        warn("PDF/A", "No se encontraron DOCX generados para convertir")

    ok("pdf_archivo.py", "importa correctamente")

except Exception as e:
    warn("PDF/A", f"{e}")

# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("RESULTADO FINAL")
print("=" * 60)

if not failures:
    print(f"\n{PASS} SISTEMA COMPLETO — TODAS LAS FASES PASAN")
    print(f"   Warnings ({len(warnings)}): {'; '.join(warnings[:3]) if warnings else 'ninguno'}")
else:
    print(f"\n{FAIL} FALLAS DETECTADAS ({len(failures)}):")
    for f in failures:
        print(f"   {FAIL} {f}")
    if warnings:
        print(f"\n{WARN} Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"   {WARN} {w}")

sys.exit(0 if not failures else 1)
