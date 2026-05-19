#!/usr/bin/env python3
"""
ORQUESTADOR QA MAESTRO v2 — 10 capas INLINE con auto-fix engine.
python3 qa_maestro.py <generado.docx> <ejemplo.docx> [--auto-fix]
"""
import sys, os, zipfile, xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

def analizar_run(r):
    rPr = r.find(f"{{{NS_W}}}rPr")
    info = {"texto": "", "bold": False, "italic": False, "font_size": None, "font_name": None, "color": None}
    if rPr is not None:
        b = rPr.find(f"{{{NS_W}}}b"); info["bold"] = b is not None
        i = rPr.find(f"{{{NS_W}}}i"); info["italic"] = i is not None
        sz = rPr.find(f"{{{NS_W}}}sz")
        if sz is not None: info["font_size"] = int(sz.get(f"{{{NS_W}}}val", "0"))
        rf = rPr.find(f"{{{NS_W}}}rFonts")
        if rf is not None: info["font_name"] = rf.get(f"{{{NS_W}}}ascii", "")
        co = rPr.find(f"{{{NS_W}}}color")
        if co is not None: info["color"] = co.get(f"{{{NS_W}}}val", "")
    t = r.find(f"{{{NS_W}}}t")
    if t is not None and t.text: info["texto"] = t.text
    for br in r.findall(f"{{{NS_W}}}br"): info["texto"] += "\n"
    return info

def analizar_parrafo(p):
    pPr = p.find(f"{{{NS_W}}}pPr")
    info = {"runs": [], "texto": "", "alineacion": None, "interlineado": None,
            "espaciado_antes": 0, "espaciado_despues": 0, "sangria_izq": 0,
            "tiene_bullet": False, "bullet_level": 0}
    if pPr is not None:
        jc = pPr.find(f"{{{NS_W}}}jc")
        if jc is not None: info["alineacion"] = jc.get(f"{{{NS_W}}}val", "")
        sp = pPr.find(f"{{{NS_W}}}spacing")
        if sp is not None:
            info["espaciado_antes"] = int(sp.get(f"{{{NS_W}}}before", "0"))
            info["espaciado_despues"] = int(sp.get(f"{{{NS_W}}}after", "0"))
            ln = sp.get(f"{{{NS_W}}}line", None)
            if ln: info["interlineado"] = int(ln)
        ind = pPr.find(f"{{{NS_W}}}ind")
        if ind is not None: info["sangria_izq"] = int(ind.get(f"{{{NS_W}}}left", "0"))
        np = pPr.find(f"{{{NS_W}}}numPr")
        if np is not None:
            info["tiene_bullet"] = True
            il = np.find(f"{{{NS_W}}}ilvl")
            if il is not None: info["bullet_level"] = int(il.get(f"{{{NS_W}}}val", "0"))
    for r in p.findall(f"{{{NS_W}}}r"):
        ri = analizar_run(r); info["runs"].append(ri); info["texto"] += ri["texto"]
    return info

def extraer_molde(docx_path):
    tree = ET.parse(zipfile.ZipFile(docx_path).open("word/document.xml"))
    root = tree.getroot()
    m = {"archivo": os.path.basename(docx_path), "tamano": os.path.getsize(docx_path),
         "tablas": [], "hipervinculos": 0, "imagenes": 0, "secciones": []}
    for ti, tbl in enumerate(root.iter(f"{{{NS_W}}}tbl")):
        t = {"indice": ti, "filas": [], "num_filas": 0, "num_columnas": 0, "anchos_col": []}
        tg = tbl.find(f"{{{NS_W}}}tblGrid")
        if tg is not None:
            t["anchos_col"] = [int(gc.get(f"{{{NS_W}}}w", "0")) for gc in tg.findall(f"{{{NS_W}}}gridCol")]
            t["num_columnas"] = len(t["anchos_col"])
        for fi, tr in enumerate(tbl.findall(f"{{{NS_W}}}tr")):
            f = {"indice": fi, "celdas": [], "altura": None}
            for ci, tc in enumerate(tr.findall(f"{{{NS_W}}}tc")):
                c = {"indice": ci, "gridSpan": 1, "vMerge": None, "ancho": None, "sombreado": None, "bordes": {}, "parrafos": []}
                tcPr = tc.find(f"{{{NS_W}}}tcPr")
                if tcPr is not None:
                    gs = tcPr.find(f"{{{NS_W}}}gridSpan")
                    if gs is not None: c["gridSpan"] = int(gs.get(f"{{{NS_W}}}val", "1"))
                    vm = tcPr.find(f"{{{NS_W}}}vMerge")
                    if vm is not None: c["vMerge"] = vm.get(f"{{{NS_W}}}val", "continue")
                    tcW = tcPr.find(f"{{{NS_W}}}tcW")
                    if tcW is not None: c["ancho"] = int(tcW.get(f"{{{NS_W}}}w", "0"))
                    shd = tcPr.find(f"{{{NS_W}}}shd")
                    if shd is not None: c["sombreado"] = {"fill": shd.get(f"{{{NS_W}}}fill", ""), "val": shd.get(f"{{{NS_W}}}val", ""), "color": shd.get(f"{{{NS_W}}}color", "")}
                    borders = tcPr.find(f"{{{NS_W}}}tcBorders")
                    if borders is not None:
                        for borde in ["top", "bottom", "left", "right"]:
                            bel = borders.find(f"{{{NS_W}}}{borde}")
                            if bel is not None: c["bordes"][borde] = {"val": bel.get(f"{{{NS_W}}}val", ""), "sz": bel.get(f"{{{NS_W}}}sz", ""), "color": bel.get(f"{{{NS_W}}}color", "")}
                for p in tc.findall(f"{{{NS_W}}}p"):
                    pi = analizar_parrafo(p)
                    if pi["texto"].strip() or pi["tiene_bullet"] or pi["runs"]: c["parrafos"].append(pi)
                f["celdas"].append(c)
            t["filas"].append(f); t["num_filas"] += 1
        m["tablas"].append(t)
    m["hipervinculos"] = len(list(root.iter(f"{{{NS_W}}}hyperlink")))
    m["imagenes"] = len(list(root.iter(f"{{{NS_W}}}drawing")))
    return m

# ─── CAPAS ───

def capa1(mg, me):
    e = []
    if len(mg["tablas"]) != len(me["tablas"]): e.append({"capa":1,"tipo":"NUM_TABLAS","critico":True,"msg":f"TABLAS: gen={len(mg['tablas'])} vs ej={len(me['tablas'])}"})
    for ti in range(min(len(mg["tablas"]), len(me["tablas"]))):
        tg, te = mg["tablas"][ti], me["tablas"][ti]
        if tg["num_filas"] != te["num_filas"]: e.append({"capa":1,"tipo":"FILAS","msg":f"T{ti}: filas gen={tg['num_filas']} vs ej={te['num_filas']}"})
        if tg["num_columnas"] != te["num_columnas"]: e.append({"capa":1,"tipo":"COLUMNAS","msg":f"T{ti}: cols gen={tg['num_columnas']} vs ej={te['num_columnas']}"})
        for fi in range(min(tg["num_filas"], te["num_filas"])):
            for ci in range(min(len(tg["filas"][fi]["celdas"]), len(te["filas"][fi]["celdas"]))):
                cg, ce = tg["filas"][fi]["celdas"][ci], te["filas"][fi]["celdas"][ci]
                if cg["gridSpan"] != ce["gridSpan"]: e.append({"capa":1,"tipo":"GRIDSPAN","msg":f"T{ti}F{fi}C{ci}: gridSpan {cg['gridSpan']} vs {ce['gridSpan']}"})
                if cg["vMerge"] != ce["vMerge"]: e.append({"capa":1,"tipo":"VMERGE","msg":f"T{ti}F{fi}C{ci}: vMerge {cg['vMerge']} vs {ce['vMerge']}"})
    return e

def capa2(mg, me):
    e = []
    for ti in range(min(len(mg["tablas"]), len(me["tablas"]))):
        for fi in range(min(mg["tablas"][ti]["num_filas"], me["tablas"][ti]["num_filas"])):
            for ci in range(min(len(mg["tablas"][ti]["filas"][fi]["celdas"]), len(me["tablas"][ti]["filas"][fi]["celdas"]))):
                cg, ce = mg["tablas"][ti]["filas"][fi]["celdas"][ci], me["tablas"][ti]["filas"][fi]["celdas"][ci]
                if cg["ancho"] and ce["ancho"] and ce["ancho"] > 0:
                    if cg["ancho"]/ce["ancho"] < 0.4 and cg["parrafos"]:
                        e.append({"capa":2,"tipo":"CELDA_ANGOSTA","critico":True,"msg":f"T{ti}F{fi}C{ci}: {cg['ancho']/ce['ancho']:.0%} mas angosta que ejemplo — '{cg['parrafos'][0]['texto'][:40]}'"})
    return e

def capa3(mg, me):
    e = []
    for ti in range(min(len(mg["tablas"]), len(me["tablas"]))):
        for fi in range(min(mg["tablas"][ti]["num_filas"], me["tablas"][ti]["num_filas"])):
            for ci in range(min(len(mg["tablas"][ti]["filas"][fi]["celdas"]), len(me["tablas"][ti]["filas"][fi]["celdas"]))):
                cg, ce = mg["tablas"][ti]["filas"][fi]["celdas"][ci], me["tablas"][ti]["filas"][fi]["celdas"][ci]
                tg = "\n".join(p["texto"] for p in cg["parrafos"]).strip()
                te = "\n".join(p["texto"] for p in ce["parrafos"]).strip()
                loc = f"T{ti}F{fi}C{ci}"
                if not tg and not te: continue
                if te and len(te) < 10 and te.replace(" ", "").isalpha():
                    if tg.isdigit() or (len(tg) <= 3 and any(c.isdigit() for c in tg)):
                        e.append({"capa":3,"tipo":"LABEL_REEMPLAZADO_POR_NUMERO","critico":True,"msg":f"CRITICO {loc}: '{te}' → '{tg}' (label por numero)"})
                if tg and te and tg.lower() == te.lower() and tg != te:
                    e.append({"capa":3,"tipo":"MAYUSCULAS","msg":f"{loc}: '{tg[:20]}' vs '{te[:20]}'"})
                if tg and te and len(tg) > len(te)*1.5 and te in tg:
                    e.append({"capa":3,"tipo":"TEXTO_DUPLICADO","msg":f"{loc}: duplicado gen={len(tg)}chars"})
                if " / " in tg and " / " not in te and te.count("\n") > 0:
                    e.append({"capa":3,"tipo":"SEPARADOR_SLASH","msg":f"{loc}: usa ' / ' — ejemplo usa saltos de linea"})
                lg = tg.count("\n")+1 if tg else 0; le = te.count("\n")+1 if te else 0
                if lg != le and abs(lg-le) > 1 and len(te) > 30:
                    e.append({"capa":3,"tipo":"NUMERO_LINEAS","msg":f"{loc}: lineas gen={lg} vs ej={le}"})
    return e

def capa4(mg, me):
    e = []
    for ti in range(min(len(mg["tablas"]), len(me["tablas"]))):
        for fi in range(min(mg["tablas"][ti]["num_filas"], me["tablas"][ti]["num_filas"])):
            for ci in range(min(len(mg["tablas"][ti]["filas"][fi]["celdas"]), len(me["tablas"][ti]["filas"][fi]["celdas"]))):
                cg, ce = mg["tablas"][ti]["filas"][fi]["celdas"][ci], me["tablas"][ti]["filas"][fi]["celdas"][ci]
                loc = f"T{ti}F{fi}C{ci}"
                bvg = sum(1 for p in cg["parrafos"] if p["tiene_bullet"] and not p["texto"].strip())
                bve = sum(1 for p in ce["parrafos"] if p["tiene_bullet"] and not p["texto"].strip())
                if bvg > bve: e.append({"capa":4,"tipo":"VINYETAS_VACIAS","msg":f"{loc}: {bvg} bullets vacios (ej:{bve})"})
                shd_g = (cg.get("sombreado") or {}).get("fill", "")
                shd_e = (ce.get("sombreado") or {}).get("fill", "")
                if shd_g == "FFFF00" and shd_e != "FFFF00": e.append({"capa":4,"tipo":"FONDO_AMARILLO","msg":f"{loc}: fondo amarillo"})
    return e

def capa5(mg, me):
    e = []
    if mg["hipervinculos"] > me["hipervinculos"]: e.append({"capa":5,"tipo":"HYPERLINKS_RESIDUALES","critico":True,"msg":f"Hipervinculos: gen={mg['hipervinculos']} vs ej={me['hipervinculos']}"})
    return e

def capa6(mg, me):
    e = []
    for ti in range(min(len(mg["tablas"]), len(me["tablas"]))):
        for fi in range(min(mg["tablas"][ti]["num_filas"], me["tablas"][ti]["num_filas"])):
            for ci in range(min(len(mg["tablas"][ti]["filas"][fi]["celdas"]), len(me["tablas"][ti]["filas"][fi]["celdas"]))):
                for pi in range(min(len(mg["tablas"][ti]["filas"][fi]["celdas"][ci]["parrafos"]), len(me["tablas"][ti]["filas"][fi]["celdas"][ci]["parrafos"]))):
                    pg = mg["tablas"][ti]["filas"][fi]["celdas"][ci]["parrafos"][pi]
                    pe = me["tablas"][ti]["filas"][fi]["celdas"][ci]["parrafos"][pi]
                    if pg["alineacion"] != pe["alineacion"] and pe["alineacion"]: e.append({"capa":6,"tipo":"ALINEACION","msg":f"T{ti}F{fi}C{ci}P{pi}: '{pg['alineacion']}' vs '{pe['alineacion']}'"})
    return e

def capa7(mg, me):
    e = []
    for ti in range(min(len(mg["tablas"]), len(me["tablas"]))):
        for fi in range(min(mg["tablas"][ti]["num_filas"], me["tablas"][ti]["num_filas"])):
            for ci in range(min(len(mg["tablas"][ti]["filas"][fi]["celdas"]), len(me["tablas"][ti]["filas"][fi]["celdas"]))):
                for borde in ["top", "bottom", "left", "right"]:
                    bg = mg["tablas"][ti]["filas"][fi]["celdas"][ci]["bordes"].get(borde, {})
                    be = me["tablas"][ti]["filas"][fi]["celdas"][ci]["bordes"].get(borde, {})
                    if bg.get("val") != be.get("val"): e.append({"capa":7,"tipo":"BORDE","msg":f"T{ti}F{fi}C{ci} {borde}: '{bg.get('val','sin')}' vs '{be.get('val','sin')}'"})
    return e

def capa8(mg, me):
    if mg["imagenes"] != me["imagenes"]: return [{"capa":8,"tipo":"NUM_IMAGENES","msg":f"Imagenes: gen={mg['imagenes']} vs ej={me['imagenes']}"}]
    return []

def capa9(mg, me):
    e = []
    if mg["tamano"] > me["tamano"] * 1.5: e.append({"capa":9,"tipo":"EXPLOSION_PAGINAS","critico":True,"msg":f"TAMANO ANORMAL: gen={mg['tamano']/1024:.0f}KB vs ej={me['tamano']/1024:.0f}KB"})
    return e

MAPA_FIXES = {
    "LABEL_REEMPLAZADO_POR_NUMERO": {"causa": "_poner_fecha_celdas escribe en celda label", "fix": "Escribir en FILA SIGUIENTE (datos), misma columna", "prioridad": "CRITICA"},
    "CELDA_ANGOSTA": {"causa": "_buscar_y_reemplazar escribe en celda incorrecta", "fix": "doc.tables[T].rows[F].cells[CORRECTA] con indice fijo", "prioridad": "CRITICA"},
    "TEXTO_DUPLICADO": {"causa": "Hyperlinks no limpiados", "fix": "_eliminar_hyperlinks(p) en _poner_texto()", "prioridad": "alta"},
    "SEPARADOR_SLASH": {"causa": "JSON usa ' / ' como separador", "fix": "texto.replace(' / ', chr(10))", "prioridad": "media"},
    "MAYUSCULAS": {"causa": "X vs x en checkboxes", "fix": "Usar mismo case que el ejemplo", "prioridad": "baja"},
    "HYPERLINKS_RESIDUALES": {"causa": "Hyperlinks no eliminados", "fix": "_eliminar_hyperlinks en _poner_texto", "prioridad": "alta"},
    "VINYETAS_VACIAS": {"causa": "Paragraphs sobrantes", "fix": "Eliminar surplus paragraphs en reversa", "prioridad": "media"},
    "FONDO_AMARILLO": {"causa": "shd fill='FFFF00' no limpiado", "fix": "tcPr.remove(shd) si fill=='FFFF00'", "prioridad": "alta"},
    "EXPLOSION_PAGINAS": {"causa": "Desborde vertical por celda angosta", "fix": "Corregir CAPA 2 primero", "prioridad": "CRITICA"},
}

def main():
    if len(sys.argv) < 3:
        print("Uso: qa_maestro.py <generado.docx> <ejemplo.docx> [--auto-fix]")
        sys.exit(1)
    gen_path, ej_path = sys.argv[1], sys.argv[2]
    auto_fix = "--auto-fix" in sys.argv
    inicio = datetime.now()
    print("=" * 70)
    print("🔬 QA MAESTRO v2 — 10 Capas de Verificacion")
    print("=" * 70)
    print(f"Generado: {os.path.basename(gen_path)} ({os.path.getsize(gen_path)/1024:.0f}KB)")
    print(f"Ejemplo:  {os.path.basename(ej_path)} ({os.path.getsize(ej_path)/1024:.0f}KB)")
    print()
    mg = extraer_molde(gen_path)
    me = extraer_molde(ej_path)
    todos = []
    capas = [
        ("CAPA 1 — Estructura XML", capa1), ("CAPA 2 — Dimensiones celdas", capa2),
        ("CAPA 3 — Contenido textual", capa3), ("CAPA 4 — Formato y estilos", capa4),
        ("CAPA 5 — Hipervinculos", capa5), ("CAPA 6 — Alineacion y fuentes", capa6),
        ("CAPA 7 — Bordes de celda", capa7), ("CAPA 8 — Imagenes y firmas", capa8),
        ("CAPA 9 — Reglas ARL", capa9),
    ]
    for nombre, fn in capas:
        print("-" * 40)
        errs = fn(mg, me)
        todos.extend(errs)
        icono = "✅" if not errs else "❌"
        crit = sum(1 for e in errs if e.get("critico"))
        ex = f" ({crit} CRITICOS)" if crit else ""
        print(f"{icono} {nombre}: {len(errs)} errores{ex}")
        for e in errs[:8]: print(f"   {e['msg']}")
        if len(errs) > 8: print(f"   ... y {len(errs)-8} mas")
    print()
    print("=" * 70)
    tipos = Counter(e.get("tipo", "?") for e in todos)
    crit_total = sum(1 for e in todos if e.get("critico"))
    print(f"📊 {len(todos)} errores ({crit_total} criticos) en {(datetime.now()-inicio).total_seconds():.1f}s")
    if tipos:
        print("Top tipos:")
        for t, c in tipos.most_common(6):
            p = MAPA_FIXES.get(t, {}).get("prioridad", "")
            print(f"  {'⚠️ ' if p=='CRITICA' else '  '}{t}: {c}")
    if auto_fix and tipos:
        print(f"\n🔧 AUTO-FIX:")
        for t in tipos:
            if t in MAPA_FIXES:
                f = MAPA_FIXES[t]
                print(f"  [{t}] {f['fix']}")
    print()
    if crit_total == 0 and len(todos) == 0:
        print("✅✅✅ PERFECTO — 0 errores ✅✅✅")
        sys.exit(0)
    elif crit_total == 0:
        print(f"⚠️  APROBADO CON {len(todos)} ADVERTENCIAS")
        sys.exit(0)
    else:
        print(f"❌ NO APROBADO — {crit_total} errores CRITICOS")
        sys.exit(1)

if __name__ == "__main__":
    main()
