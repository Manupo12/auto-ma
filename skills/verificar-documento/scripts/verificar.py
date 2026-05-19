#!/usr/bin/env python3
"""
Script standalone de verificación de documentos médicos.
Compara un DOCX generado contra su plantilla de ejemplo.
Uso: python3 scripts/verificar.py <generado.docx> <ejemplo.docx>
"""

import sys, os, subprocess, zipfile, xml.etree.ElementTree as ET

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def extraer_estructura(docx_path):
    """Extrae estructura completa de tablas de un DOCX."""
    with zipfile.ZipFile(docx_path) as z:
        with z.open("word/document.xml") as f:
            tree = ET.parse(f)
    
    root = tree.getroot()
    tablas = []
    
    for tbl in root.iter(f"{{{NS_W}}}tbl"):
        info = {"filas": [], "num_filas": 0, "num_columnas": 0}
        
        tblGrid = tbl.find(f"{{{NS_W}}}tblGrid")
        if tblGrid is not None:
            cols = tblGrid.findall(f"{{{NS_W}}}gridCol")
            info["num_columnas"] = len(cols)
        
        for tr in tbl.findall(f"{{{NS_W}}}tr"):
            fila = {"celdas": []}
            for tc in tr.findall(f"{{{NS_W}}}tc"):
                tcPr = tc.find(f"{{{NS_W}}}tcPr")
                gs, vm, shd_fill, width = None, None, None, None
                
                if tcPr is not None:
                    gs_el = tcPr.find(f"{{{NS_W}}}gridSpan")
                    if gs_el is not None:
                        gs = int(gs_el.get(f"{{{NS_W}}}val", "1"))
                    
                    vm_el = tcPr.find(f"{{{NS_W}}}vMerge")
                    if vm_el is not None:
                        vm = vm_el.get(f"{{{NS_W}}}val", "continue")
                    
                    shd_el = tcPr.find(f"{{{NS_W}}}shd")
                    if shd_el is not None:
                        shd_fill = shd_el.get(f"{{{NS_W}}}fill")
                    
                    tcW_el = tcPr.find(f"{{{NS_W}}}tcW")
                    if tcW_el is not None:
                        width = tcW_el.get(f"{{{NS_W}}}w")
                
                textos = []
                for p in tc.findall(f"{{{NS_W}}}p"):
                    for r in p.findall(f"{{{NS_W}}}r"):
                        t = r.find(f"{{{NS_W}}}t")
                        if t is not None and t.text:
                            textos.append(t.text)
                
                fila["celdas"].append({
                    "gridSpan": gs, "vMerge": vm,
                    "shd_fill": shd_fill, "width": width,
                    "texto": " ".join(textos).strip()[:80]
                })
            
            info["filas"].append(fila)
            info["num_filas"] += 1
        
        tablas.append(info)
    
    return tablas


def comparar_estructura(gen_path, ej_path):
    gen = extraer_estructura(gen_path)
    ej = extraer_estructura(ej_path)
    diffs = []
    
    if len(gen) != len(ej):
        diffs.append(("TABLAS", "", "", "", f"gen={len(gen)}", f"ej={len(ej)}"))
        return diffs, gen, ej
    
    for ti, (tg, te) in enumerate(zip(gen, ej)):
        if tg["num_filas"] != te["num_filas"]:
            diffs.append(("FILAS", f"T{ti}", "", "", f"gen={tg['num_filas']}", f"ej={te['num_filas']}"))
        
        if tg["num_columnas"] != te["num_columnas"]:
            diffs.append(("COLUMNAS", f"T{ti}", "", "", f"gen={tg['num_columnas']}", f"ej={te['num_columnas']}"))
        
        nf = min(tg["num_filas"], te["num_filas"])
        for fi in range(nf):
            fg, fe = tg["filas"][fi], te["filas"][fi]
            nc = min(len(fg["celdas"]), len(fe["celdas"]))
            
            if len(fg["celdas"]) != len(fe["celdas"]):
                diffs.append(("CELDAS", f"T{ti}", f"F{fi}", "", f"{len(fg['celdas'])}", f"{len(fe['celdas'])}"))
            
            for ci in range(nc):
                cg, ce = fg["celdas"][ci], fe["celdas"][ci]
                
                if cg["gridSpan"] != ce["gridSpan"]:
                    diffs.append(("gridSpan", f"T{ti}", f"F{fi}", f"C{ci}", str(cg["gridSpan"]), str(ce["gridSpan"])))
                
                if cg["vMerge"] != ce["vMerge"]:
                    diffs.append(("vMerge", f"T{ti}", f"F{fi}", f"C{ci}", str(cg["vMerge"]), str(ce["vMerge"])))
                
                if cg["shd_fill"] != ce["shd_fill"]:
                    diffs.append(("COLOR", f"T{ti}", f"F{fi}", f"C{ci}", str(cg["shd_fill"]), str(ce["shd_fill"])))
    
    return diffs, gen, ej


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: verificar.py <generado.docx> <ejemplo.docx>")
        sys.exit(1)
    
    gen_path, ej_path = sys.argv[1], sys.argv[2]
    
    print("=" * 60)
    print("VERIFICACION DE DOCUMENTO MEDICO")
    print("=" * 60)
    print(f"Generado: {gen_path}")
    print(f"Ejemplo:  {ej_path}")
    
    print(f"\nFASE 1 — Comparacion estructural (XML)...")
    diffs, gen_est, ej_est = comparar_estructura(gen_path, ej_path)
    
    if not diffs:
        print("   ✅ 0 diferencias estructurales")
    else:
        print(f"   ❌ {len(diffs)} diferencias estructurales:")
        for tipo, tabla, fila, col, vgen, vej in diffs:
            loc = f"{tabla} {fila} {col}".strip()
            print(f"      [{tipo}] {loc}: gen={vgen} vs ej={vej}")
    
    print(f"\nRESUMEN:")
    print(f"   Tablas: gen={len(gen_est)} | ej={len(ej_est)}")
    print(f"   Diferencias totales: {len(diffs)}")
    
    sys.exit(1 if diffs else 0)
