#!/usr/bin/env python3
"""
ANALIZADOR PROFUNDO — Extrae la anatomía completa de un DOCX de ejemplo.
Genera un "molde" JSON que describe exactamente cómo está hecho el documento:
tablas, celdas, párrafos, runs, fuentes, colores, márgenes, encabezados, pies, etc.

Uso: python3 analizar_ejemplo.py <ejemplo.docx> [--output molde.json]
"""

import sys, os, zipfile, json, xml.etree.ElementTree as ET
from collections import defaultdict

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_WPML = "http://schemas.microsoft.com/office/word/2010/wordprocessingml"

def analizar_docx(docx_path):
    """Análisis completo de un DOCX. Retorna dict con toda la anatomía."""
    molde = {
        "archivo": os.path.basename(docx_path),
        "tamano_bytes": os.path.getsize(docx_path),
        "tablas": [],
        "parrafos_sueltos": [],
        "encabezados": [],
        "pies_pagina": [],
        "secciones": [],
        "estilos_usados": [],
        "hipervinculos": 0,
        "imagenes": 0,
    }
    
    with zipfile.ZipFile(docx_path) as z:
        # ─── Documento principal ───
        with z.open("word/document.xml") as f:
            tree = ET.parse(f)
        root = tree.getroot()
        
        # ─── Tablas ───
        for ti, tbl in enumerate(root.iter(f"{{{NS_W}}}tbl")):
            tabla = analizar_tabla(tbl, ti)
            molde["tablas"].append(tabla)
        
        # ─── Párrafos sueltos (fuera de tablas) ───
        # Los párrafos directos del body (no dentro de tbl)
        body = root.find(f"{{{NS_W}}}body")
        if body is not None:
            for p in body.findall(f"{{{NS_W}}}p"):
                # Verificar que no esté dentro de una tabla
                if not es_parte_de_tabla(p):
                    parr = analizar_parrafo(p)
                    if parr["texto"].strip():
                        molde["parrafos_sueltos"].append(parr)
        
        # ─── Hipervínculos ───
        molde["hipervinculos"] = len(list(root.iter(f"{{{NS_W}}}hyperlink")))
        
        # ─── Imágenes (referencias) ───
        molde["imagenes"] = len(list(root.iter(f"{{{NS_W}}}drawing")))
        
        # ─── Secciones ───
        for sectPr in root.iter(f"{{{NS_W}}}sectPr"):
            seccion = analizar_seccion(sectPr)
            molde["secciones"].append(seccion)
        
        # ─── Encabezados ───
        for fname in z.namelist():
            if "header" in fname and fname.endswith(".xml"):
                with z.open(fname) as f:
                    htree = ET.parse(f)
                hroot = htree.getroot()
                header_info = {
                    "archivo": fname,
                    "parrafos": [],
                    "tablas_en_header": 0,
                }
                for p in hroot.iter(f"{{{NS_W}}}p"):
                    parr = analizar_parrafo(p)
                    if parr["texto"].strip():
                        header_info["parrafos"].append(parr)
                header_info["tablas_en_header"] = len(list(hroot.iter(f"{{{NS_W}}}tbl")))
                molde["encabezados"].append(header_info)
        
        # ─── Pies de página ───
        for fname in z.namelist():
            if "footer" in fname and fname.endswith(".xml"):
                with z.open(fname) as f:
                    ftree = ET.parse(f)
                froot = ftree.getroot()
                footer_info = {
                    "archivo": fname,
                    "parrafos": [],
                }
                for p in froot.iter(f"{{{NS_W}}}p"):
                    parr = analizar_parrafo(p)
                    if parr["texto"].strip():
                        footer_info["parrafos"].append(parr)
                molde["pies_pagina"].append(footer_info)
        
        # ─── Estilos ───
        if "word/styles.xml" in z.namelist():
            with z.open("word/styles.xml") as f:
                stree = ET.parse(f)
            for style in stree.getroot().findall(f"{{{NS_W}}}style"):
                style_id = style.get(f"{{{NS_W}}}styleId", "")
                if style_id:
                    molde["estilos_usados"].append(style_id)
    
    return molde


def analizar_tabla(tbl, ti):
    """Analiza una tabla completa."""
    info = {
        "indice": ti,
        "num_filas": 0,
        "num_columnas": 0,
        "anchos_columna": [],
        "filas": [],
    }
    
    # Grid (columnas)
    tblGrid = tbl.find(f"{{{NS_W}}}tblGrid")
    if tblGrid is not None:
        for gc in tblGrid.findall(f"{{{NS_W}}}gridCol"):
            info["anchos_columna"].append(int(gc.get(f"{{{NS_W}}}w", "0")))
        info["num_columnas"] = len(info["anchos_columna"])
    
    # Propiedades de tabla
    tblPr = tbl.find(f"{{{NS_W}}}tblPr")
    if tblPr is not None:
        tblW = tblPr.find(f"{{{NS_W}}}tblW")
        if tblW is not None:
            info["ancho_total"] = int(tblW.get(f"{{{NS_W}}}w", "0"))
    
    # Filas
    for fi, tr in enumerate(tbl.findall(f"{{{NS_W}}}tr")):
        fila = analizar_fila(tr, fi)
        info["filas"].append(fila)
        info["num_filas"] += 1
    
    return info


def analizar_fila(tr, fi):
    """Analiza una fila completa con todas sus celdas."""
    fila = {"indice": fi, "celdas": []}
    
    # Altura de fila
    trPr = tr.find(f"{{{NS_W}}}trPr")
    if trPr is not None:
        trHeight = trPr.find(f"{{{NS_W}}}trHeight")
        if trHeight is not None:
            fila["altura"] = int(trHeight.get(f"{{{NS_W}}}val", "0"))
    
    for ci, tc in enumerate(tr.findall(f"{{{NS_W}}}tc")):
        celda = analizar_celda(tc, ci)
        fila["celdas"].append(celda)
    
    return fila


def analizar_celda(tc, ci):
    """Analiza una celda: dimensiones, formato, contenido."""
    tcPr = tc.find(f"{{{NS_W}}}tcPr")
    celda = {
        "indice": ci,
        "gridSpan": 1,
        "vMerge": None,
        "ancho": None,
        "tipo_ancho": "dxa",
        "sombreado": None,
        "bordes": {},
        "alineacion_vertical": None,
        "parrafos": [],
    }
    
    if tcPr is not None:
        # gridSpan
        gs = tcPr.find(f"{{{NS_W}}}gridSpan")
        if gs is not None:
            celda["gridSpan"] = int(gs.get(f"{{{NS_W}}}val", "1"))
        
        # vMerge
        vm = tcPr.find(f"{{{NS_W}}}vMerge")
        if vm is not None:
            celda["vMerge"] = vm.get(f"{{{NS_W}}}val", "continue")
        
        # Ancho
        tcW = tcPr.find(f"{{{NS_W}}}tcW")
        if tcW is not None:
            celda["ancho"] = int(tcW.get(f"{{{NS_W}}}w", "0"))
            celda["tipo_ancho"] = tcW.get(f"{{{NS_W}}}type", "dxa")
        
        # Sombreado
        shd = tcPr.find(f"{{{NS_W}}}shd")
        if shd is not None:
            celda["sombreado"] = {
                "fill": shd.get(f"{{{NS_W}}}fill", ""),
                "val": shd.get(f"{{{NS_W}}}val", ""),
                "color": shd.get(f"{{{NS_W}}}color", ""),
            }
        
        # Bordes
        tcBorders = tcPr.find(f"{{{NS_W}}}tcBorders")
        if tcBorders is not None:
            for borde in ["top", "bottom", "left", "right"]:
                bEl = tcBorders.find(f"{{{NS_W}}}{borde}")
                if bEl is not None:
                    celda["bordes"][borde] = {
                        "val": bEl.get(f"{{{NS_W}}}val", ""),
                        "sz": bEl.get(f"{{{NS_W}}}sz", ""),
                        "color": bEl.get(f"{{{NS_W}}}color", ""),
                    }
        
        # Alineación vertical
        vAlign = tcPr.find(f"{{{NS_W}}}vAlign")
        if vAlign is not None:
            celda["alineacion_vertical"] = vAlign.get(f"{{{NS_W}}}val", "")
    
    # Párrafos dentro de la celda
    for pi, p in enumerate(tc.findall(f"{{{NS_W}}}p")):
        parr = analizar_parrafo(p)
        if parr["texto"].strip() or parr["tiene_bullet"] or parr["runs"]:
            celda["parrafos"].append(parr)
    
    return celda


def analizar_parrafo(p):
    """Analiza un párrafo: runs, formato, bullets."""
    pPr = p.find(f"{{{NS_W}}}pPr")
    parr = {
        "runs": [],
        "texto": "",
        "tiene_bullet": False,
        "bullet_level": 0,
        "alineacion": None,
        "espaciado_antes": None,
        "espaciado_despues": None,
    }
    
    if pPr is not None:
        # Bullet / numeración
        numPr = pPr.find(f"{{{NS_W}}}numPr")
        if numPr is not None:
            parr["tiene_bullet"] = True
            ilvl = numPr.find(f"{{{NS_W}}}ilvl")
            if ilvl is not None:
                parr["bullet_level"] = int(ilvl.get(f"{{{NS_W}}}val", "0"))
        
        # Alineación
        jc = pPr.find(f"{{{NS_W}}}jc")
        if jc is not None:
            parr["alineacion"] = jc.get(f"{{{NS_W}}}val", "")
        
        # Espaciado
        spacing = pPr.find(f"{{{NS_W}}}spacing")
        if spacing is not None:
            parr["espaciado_antes"] = int(spacing.get(f"{{{NS_W}}}before", "0"))
            parr["espaciado_despues"] = int(spacing.get(f"{{{NS_W}}}after", "0"))
    
    # Runs (fragmentos de texto con formato)
    for r in p.findall(f"{{{NS_W}}}r"):
        run = analizar_run(r)
        parr["runs"].append(run)
        if run["texto"]:
            parr["texto"] += run["texto"]
    
    return parr


def analizar_run(r):
    """Analiza un run: texto, fuente, color, bold, italic, tamaño."""
    rPr = r.find(f"{{{NS_W}}}rPr")
    run = {
        "texto": "",
        "bold": False,
        "italic": False,
        "underline": False,
        "font_size": None,      # en half-points (24 = 12pt)
        "font_name": None,
        "color": None,
        "highlight": None,
        "strike": False,
        "superscript": False,
        "subscript": False,
    }
    
    if rPr is not None:
        b = rPr.find(f"{{{NS_W}}}b")
        if b is not None:
            run["bold"] = b.get(f"{{{NS_W}}}val", "1") != "0"
        
        i = rPr.find(f"{{{NS_W}}}i")
        if i is not None:
            run["italic"] = i.get(f"{{{NS_W}}}val", "1") != "0"
        
        u = rPr.find(f"{{{NS_W}}}u")
        if u is not None:
            run["underline"] = u.get(f"{{{NS_W}}}val", "single") != "none"
        
        sz = rPr.find(f"{{{NS_W}}}sz")
        if sz is not None:
            run["font_size"] = int(sz.get(f"{{{NS_W}}}val", "0"))
        
        rFonts = rPr.find(f"{{{NS_W}}}rFonts")
        if rFonts is not None:
            run["font_name"] = rFonts.get(f"{{{NS_W}}}ascii", "") or rFonts.get(f"{{{NS_W}}}cs", "")
        
        color = rPr.find(f"{{{NS_W}}}color")
        if color is not None:
            run["color"] = color.get(f"{{{NS_W}}}val", "")
        
        highlight = rPr.find(f"{{{NS_W}}}highlight")
        if highlight is not None:
            run["highlight"] = highlight.get(f"{{{NS_W}}}val", "")
        
        strike = rPr.find(f"{{{NS_W}}}strike")
        if strike is not None:
            run["strike"] = True
        
        vertAlign = rPr.find(f"{{{NS_W}}}vertAlign")
        if vertAlign is not None:
            va = vertAlign.get(f"{{{NS_W}}}val", "")
            if va == "superscript":
                run["superscript"] = True
            elif va == "subscript":
                run["subscript"] = True
    
    # Texto
    t = r.find(f"{{{NS_W}}}t")
    if t is not None and t.text:
        run["texto"] = t.text
    else:
        # Puede ser un tab, break, etc.
        for child in r:
            if child.tag == f"{{{NS_W}}}br":
                run["texto"] = "\n"
            elif child.tag == f"{{{NS_W}}}tab":
                run["texto"] = "\t"
    
    return run


def analizar_seccion(sectPr):
    """Analiza propiedades de sección: márgenes, tamaño página, orientación."""
    seccion = {}
    
    pgSz = sectPr.find(f"{{{NS_W}}}pgSz")
    if pgSz is not None:
        seccion["ancho_pagina"] = int(pgSz.get(f"{{{NS_W}}}w", "0"))
        seccion["alto_pagina"] = int(pgSz.get(f"{{{NS_W}}}h", "0"))
        seccion["orientacion"] = "landscape" if seccion.get("ancho_pagina", 0) > seccion.get("alto_pagina", 0) else "portrait"
    
    pgMar = sectPr.find(f"{{{NS_W}}}pgMar")
    if pgMar is not None:
        seccion["margen_sup"] = int(pgMar.get(f"{{{NS_W}}}top", "0"))
        seccion["margen_inf"] = int(pgMar.get(f"{{{NS_W}}}bottom", "0"))
        seccion["margen_izq"] = int(pgMar.get(f"{{{NS_W}}}left", "0"))
        seccion["margen_der"] = int(pgMar.get(f"{{{NS_W}}}right", "0"))
    
    # Headers/footers references
    for ref_name in ["headerReference", "footerReference", "firstHeaderReference", "firstFooterReference"]:
        ref = sectPr.find(f"{{{NS_W}}}{ref_name}")
        if ref is not None:
            seccion[ref_name] = ref.get(f"{{{NS_R}}}id", "")
    
    return seccion


def es_parte_de_tabla(elemento):
    """Determina si un elemento está dentro de una tabla."""
    parent = elemento
    while parent is not None:
        if parent.tag == f"{{{NS_W}}}tbl" or parent.tag == f"{{{NS_W}}}tc":
            return True
        # Subir al padre (simplificado — en realidad necesitaríamos el árbol completo)
        break
    return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: analizar_ejemplo.py <ejemplo.docx> [--output molde.json]")
        sys.exit(1)
    
    docx_path = sys.argv[1]
    output_path = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_path = sys.argv[idx + 1]
    
    molde = analizar_docx(docx_path)
    
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(molde, f, indent=2, ensure_ascii=False)
        print(f"✅ Molde guardado en {output_path}")
    else:
        # Resumen en consola
        print(f"📄 {molde['archivo']} ({molde['tamano_bytes']/1024:.0f} KB)")
        print(f"   Tablas: {len(molde['tablas'])}")
        for t in molde["tablas"]:
            print(f"      T{t['indice']}: {t['num_filas']}f × {t['num_columnas']}c (ancho={t.get('ancho_total','?')})")
        print(f"   Párrafos sueltos: {len(molde['parrafos_sueltos'])}")
        print(f"   Encabezados: {len(molde['encabezados'])}")
        print(f"   Pies de página: {len(molde['pies_pagina'])}")
        print(f"   Secciones: {len(molde['secciones'])}")
        for s in molde["secciones"]:
            print(f"      {s.get('ancho_pagina','?')}×{s.get('alto_pagina','?')} ({s.get('orientacion','?')})")
        print(f"   Hipervínculos: {molde['hipervinculos']}")
        print(f"   Imágenes: {molde['imagenes']}")
        
        # Estadísticas de celdas
        total_celdas = sum(len(f["celdas"]) for t in molde["tablas"] for f in t["filas"])
        celdas_con_sombreado = sum(1 for t in molde["tablas"] for f in t["filas"] for c in f["celdas"] if c["sombreado"] and c["sombreado"]["fill"])
        celdas_con_bullet = sum(1 for t in molde["tablas"] for f in t["filas"] for c in f["celdas"] for p in c["parrafos"] if p["tiene_bullet"])
        celdas_con_bold = sum(1 for t in molde["tablas"] for f in t["filas"] for c in f["celdas"] for p in c["parrafos"] for r in p["runs"] if r["bold"])
        
        print(f"\n   Total celdas: {total_celdas}")
        print(f"   Celdas con sombreado: {celdas_con_sombreado}")
        print(f"   Celdas con viñetas: {celdas_con_bullet}")
        print(f"   Celdas con negrita: {celdas_con_bold}")
