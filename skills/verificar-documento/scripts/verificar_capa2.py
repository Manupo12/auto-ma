#!/usr/bin/env python3
"""CAPA 2 — Verificación de dimensiones de celdas.
Detecta celdas con ancho incorrecto que pueden causar desborde vertical.
Uso: python3 verificar_capa2.py <generado.docx> <ejemplo.docx>
"""

import sys, zipfile, xml.etree.ElementTree as ET

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

def extraer_dimensiones(docx_path):
    """Extrae ancho y gridSpan de cada celda."""
    with zipfile.ZipFile(docx_path) as z:
        with z.open("word/document.xml") as f:
            tree = ET.parse(f)
    
    root = tree.getroot()
    celdas = {}
    
    for ti, tbl in enumerate(root.iter(f"{{{NS_W}}}tbl")):
        for fi, tr in enumerate(tbl.findall(f"{{{NS_W}}}tr")):
            for ci, tc in enumerate(tr.findall(f"{{{NS_W}}}tc")):
                tcPr = tc.find(f"{{{NS_W}}}tcPr")
                width = None
                gs = None
                width_type = None
                
                if tcPr is not None:
                    gs_el = tcPr.find(f"{{{NS_W}}}gridSpan")
                    if gs_el is not None:
                        gs = int(gs_el.get(f"{{{NS_W}}}val", "1"))
                    
                    tcW = tcPr.find(f"{{{NS_W}}}tcW")
                    if tcW is not None:
                        width = tcW.get(f"{{{NS_W}}}w")
                        width_type = tcW.get(f"{{{NS_W}}}type", "dxa")
                
                # Texto
                textos = []
                for p in tc.findall(f"{{{NS_W}}}p"):
                    for r in p.findall(f"{{{NS_W}}}r"):
                        t = r.find(f"{{{NS_W}}}t")
                        if t is not None and t.text:
                            textos.append(t.text)
                
                celdas[(ti, fi, ci)] = {
                    "width": width, "gridSpan": gs,
                    "width_type": width_type,
                    "texto": " ".join(textos).strip()[:100]
                }
    
    return celdas


def comparar_dimensiones(gen_path, ej_path):
    gen = extraer_dimensiones(gen_path)
    ej = extraer_dimensiones(ej_path)
    errores = []
    
    for key, cg in gen.items():
        ce = ej.get(key)
        if not ce:
            continue
        
        # Comparar ancho
        if cg["width"] and ce["width"]:
            try:
                wg = int(cg["width"])
                we = int(ce["width"])
                if we > 0:
                    ratio = wg / we
                    # Celda demasiado angosta (< 40% del ejemplo)
                    if ratio < 0.4 and len(cg["texto"]) > 5:
                        errores.append({
                            "tipo": "CELDA_ANGOSTA",
                            "critico": True,
                            "tabla": key[0], "fila": key[1], "col": key[2],
                            "width_gen": wg, "width_ej": we,
                            "ratio": f"{ratio:.0%}",
                            "texto": cg["texto"][:60],
                            "fix": "Usar acceso directo doc.tables[T].rows[F].cells[C] en vez de _buscar_y_reemplazar"
                        })
                    # Celda más ancha de lo esperado (posible merge horizontal roto)
                    elif ratio > 2.0 and len(cg["texto"]) > 5:
                        errores.append({
                            "tipo": "CELDA_ANCHA",
                            "critico": False,
                            "tabla": key[0], "fila": key[1], "col": key[2],
                            "width_gen": wg, "width_ej": we,
                            "ratio": f"{ratio:.0%}",
                            "texto": cg["texto"][:60]
                        })
            except (ValueError, TypeError):
                pass
        
        # Comparar gridSpan
        if cg["gridSpan"] and ce["gridSpan"] and cg["gridSpan"] != ce["gridSpan"]:
            errores.append({
                "tipo": "GRIDSPAN_CAMBIADO",
                "critico": True,
                "tabla": key[0], "fila": key[1], "col": key[2],
                "gs_gen": cg["gridSpan"], "gs_ej": ce["gridSpan"]
            })
    
    # Detectar valores duplicados (mismo texto en más celdas que el ejemplo)
    gen_textos = {}
    ej_textos = {}
    for key, c in gen.items():
        t = c["texto"]
        if t and not t.startswith(" ") and len(t) > 1:
            gen_textos[t] = gen_textos.get(t, 0) + 1
    for key, c in ej.items():
        t = c["texto"]
        if t and len(t) > 1:
            ej_textos[t] = ej_textos.get(t, 0) + 1
    
    for texto, count_gen in gen_textos.items():
        count_ej = ej_textos.get(texto, 0)
        if count_gen > count_ej and count_ej == 1 and count_gen >= 2:
            errores.append({
                "tipo": "VALOR_DUPLICADO",
                "critico": False,
                "texto": texto[:60],
                "veces_gen": count_gen,
                "veces_ej": count_ej,
                "fix": "Verificar que _buscar_y_reemplazar no escriba en celda equivocada"
            })
    
    return errores


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: verificar_capa2.py <generado.docx> <ejemplo.docx>")
        sys.exit(1)
    
    errores = comparar_dimensiones(sys.argv[1], sys.argv[2])
    
    print("=" * 60)
    print("CAPA 2 — Dimensiones de celdas")
    print("=" * 60)
    
    if not errores:
        print("✅ 0 errores de dimensión")
        sys.exit(0)
    
    criticos = [e for e in errores if e.get("critico")]
    print(f"❌ {len(errores)} errores ({len(criticos)} críticos):\n")
    
    for e in errores:
        icono = "⚠️ " if e.get("critico") else "• "
        loc = f"T{e.get('tabla','?')} F{e.get('fila','?')} C{e.get('col','?')}"
        print(f"{icono}[{e['tipo']}] {loc}")
        if "ratio" in e:
            print(f"   Ancho: gen={e.get('width_gen')} vs ej={e.get('width_ej')} ({e['ratio']})")
        if "texto" in e:
            print(f"   Texto: '{e['texto']}'")
        if "fix" in e:
            print(f"   🔧 Fix: {e['fix']}")
        print()
    
    sys.exit(1)
