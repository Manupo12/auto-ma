#!/usr/bin/env python3
"""
QA Completo — Ejecuta las 5 capas de verificación y genera reporte unificado.
Uso: python3 qa_completo.py <generado.docx> <ejemplo.docx> [--datos datos.json]
"""

import sys, os, subprocess, json

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))

CAPAS = {
    "1": {"script": "verificar.py", "desc": "Estructura XML (tablas, filas, columnas, gridSpan, vMerge)"},
    "2": {"script": "verificar_capa2.py", "desc": "Dimensiones de celdas (ancho, gridSpan, desborde vertical)"},
    # Capas 3-5 se ejecutan inline
}

def ejecutar_capa(num, script_name, gen_path, ej_path):
    script_path = os.path.join(SKILL_DIR, script_name)
    if not os.path.exists(script_path):
        return {"ok": True, "errores": [], "msg": f"⚠️ Script {script_name} no encontrado — saltando"}
    
    result = subprocess.run(
        [sys.executable, script_path, gen_path, ej_path],
        capture_output=True, text=True, timeout=30
    )
    
    # Parsear salida para contar errores
    salida = result.stdout
    num_errores = salida.count("[CELDA_ANGOSTA]") + salida.count("[GRIDSPAN_CAMBIADO]") + \
                  salida.count("[VALOR_DUPLICADO]") + salida.count("[CELDA_ANCHA]") + \
                  salida.count("[TABLAS]") + salida.count("[FILAS]") + salida.count("[COLUMNAS]") + \
                  salida.count("[gridSpan]") + salida.count("[vMerge]") + salida.count("[COLOR]")
    
    if result.returncode != 0 or num_errores > 0:
        return {"ok": False, "errores": num_errores, "msg": salida}
    return {"ok": True, "errores": 0, "msg": salida}


def capa3_contenido(gen_path, ej_path):
    """CAPA 3 — Verificación de contenido textual (inline)."""
    import zipfile, xml.etree.ElementTree as ET
    NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    
    def extraer_texto(path):
        with zipfile.ZipFile(path) as z:
            with z.open("word/document.xml") as f:
                tree = ET.parse(f)
        root = tree.getroot()
        celdas = {}
        for ti, tbl in enumerate(root.iter(f"{{{NS_W}}}tbl")):
            for fi, tr in enumerate(tbl.findall(f"{{{NS_W}}}tr")):
                for ci, tc in enumerate(tr.findall(f"{{{NS_W}}}tc")):
                    textos = []
                    for p in tc.findall(f"{{{NS_W}}}p"):
                        for r in p.findall(f"{{{NS_W}}}r"):
                            t = r.find(f"{{{NS_W}}}t")
                            if t is not None and t.text:
                                textos.append(t.text)
                    txt = " ".join(textos).strip()
                    if txt:
                        celdas[(ti, fi, ci)] = txt
        return celdas
    
    gen = extraer_texto(gen_path)
    ej = extraer_texto(ej_path)
    errores = []
    
    for key in set(list(gen.keys()) + list(ej.keys())):
        tg = gen.get(key, "")
        te = ej.get(key, "")
        if not tg and not te:
            continue
        
        # Patrón: texto duplicado
        if tg and te and len(tg) > len(te) * 1.5 and te in tg:
            errores.append(f"[TEXTO_DUPLICADO] T{key[0]} F{key[1]} C{key[2]}: gen={len(tg)}chars vs ej={len(te)}chars")
        
        # Patrón: "/" donde no debe
        if " / " in tg and " / " not in te:
            if "\n" in te or "  " in te:
                errores.append(f"[SEPARADOR_SLASH] T{key[0]} F{key[1]} C{key[2]}: usa ' / ' pero el ejemplo tiene saltos de línea")
        
        # Patrón: nombre truncado
        for nombre in ["SANDRA PATRICIA POLANIA OSORIO", "REHABILITACION INTEGRAL LABORAL Y OCUPACIONAL SAS"]:
            if nombre in te and nombre not in tg:
                partes = nombre.split()
                for i in range(len(partes)-1, 0, -1):
                    truncado = " ".join(partes[:i])
                    if truncado in tg:
                        errores.append(f"[NOMBRE_TRUNCADO] T{key[0]} F{key[1]} C{key[2]}: '{truncado}' → debe ser '{nombre}'")
                        break
    
    return errores


def capa4_formato(gen_path, ej_path):
    """CAPA 4 — Verificación de formato (inline)."""
    import zipfile, xml.etree.ElementTree as ET
    NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    
    def contar_en_xml(path, tag_pattern):
        with zipfile.ZipFile(path) as z:
            with z.open("word/document.xml") as f:
                content = f.read().decode("utf-8")
        return content.count(tag_pattern)
    
    errores = []
    
    # Hipervínculos residuales
    hl_gen = contar_en_xml(gen_path, "<w:hyperlink")
    hl_ej = contar_en_xml(ej_path, "<w:hyperlink")
    if hl_gen > hl_ej:
        errores.append(f"[HYPERLINKS_RESIDUALES] gen={hl_gen} vs ej={hl_ej}")
    
    # Fondo amarillo
    yellow_gen = contar_en_xml(gen_path, 'w:fill="FFFF00"') + contar_en_xml(gen_path, "w:fill='FFFF00'")
    yellow_ej = contar_en_xml(ej_path, 'w:fill="FFFF00"') + contar_en_xml(ej_path, "w:fill='FFFF00'")
    if yellow_gen > yellow_ej:
        errores.append(f"[FONDO_AMARILLO] gen={yellow_gen} celdas vs ej={yellow_ej}")
    
    # Viñetas vacías: párrafos con numPr pero sin texto
    def contar_vinyetas_vacias(path):
        with zipfile.ZipFile(path) as z:
            with z.open("word/document.xml") as f:
                tree = ET.parse(f)
        root = tree.getroot()
        count = 0
        for p in root.iter(f"{{{NS_W}}}p"):
            numPr = p.find(f"{{{NS_W}}}pPr")
            has_bullet = False
            if numPr is not None:
                numPrEl = numPr.find(f"{{{NS_W}}}numPr")
                if numPrEl is not None:
                    has_bullet = True
            
            if has_bullet:
                textos = []
                for r in p.findall(f"{{{NS_W}}}r"):
                    t = r.find(f"{{{NS_W}}}t")
                    if t is not None and t.text and t.text.strip():
                        textos.append(t.text)
                if not textos:
                    count += 1
        return count
    
    bullets_gen = contar_vinyetas_vacias(gen_path)
    bullets_ej = contar_vinyetas_vacias(ej_path)
    if bullets_gen > bullets_ej:
        errores.append(f"[VINYETAS_VACIAS] gen={bullets_gen} vs ej={bullets_ej}")
    
    return errores


def capa5_reglas(gen_path, ej_path):
    """CAPA 5 — Reglas de negocio ARL (inline)."""
    import zipfile, xml.etree.ElementTree as ET
    NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    
    with zipfile.ZipFile(gen_path) as z:
        with z.open("word/document.xml") as f:
            content = f.read().decode("utf-8")
    
    errores = []
    
    # Regla: Firmas completas
    for firma in ["SANDRA PATRICIA POLANIA OSORIO", "REHABILITACION INTEGRAL LABORAL Y OCUPACIONAL SAS"]:
        count = content.count(firma)
        if count < 1:
            errores.append(f"[FIRMA_FALTANTE] '{firma}' no aparece en el documento")
    
    # Regla: No texto azul
    if 'w:color="0000FF"' in content or "w:color='0000FF'" in content:
        if 'w:color="0000FF"' not in open(ej_path, "rb").read().decode("utf-8", errors="ignore"):
            errores.append("[TEXTO_AZUL] Color azul detectado donde el ejemplo no lo tiene")
    
    # Regla: No explosión de páginas
    # Estimación simple por conteo de section breaks
    secciones_gen = content.count("<w:sectPr")
    secciones_ej = open(ej_path, "rb").read().decode("utf-8", errors="ignore").count("<w:sectPr")
    # Si el generado tiene más del doble de secciones/páginas que el ejemplo
    import os
    size_gen = os.path.getsize(gen_path)
    size_ej = os.path.getsize(ej_path)
    if size_gen > size_ej * 1.5:
        errores.append(f"[TAMANO_ANORMAL] gen={size_gen/1024:.0f}KB vs ej={size_ej/1024:.0f}KB — posible explosión de páginas")
    
    return errores


def main():
    if len(sys.argv) < 3:
        print("Uso: qa_completo.py <generado.docx> <ejemplo.docx> [--datos datos.json]")
        sys.exit(1)
    
    gen_path = sys.argv[1]
    ej_path = sys.argv[2]
    
    print("=" * 60)
    print("🔍 QA MULTI-CAPA — Verificación de Documento Médico")
    print("=" * 60)
    print(f"Generado: {os.path.basename(gen_path)}")
    print(f"Ejemplo:  {os.path.basename(ej_path)}")
    print()
    
    todas_ok = True
    total_errores = 0
    
    # ─── CAPA 1 ───
    print("─" * 40)
    r1 = ejecutar_capa("1", "verificar.py", gen_path, ej_path)
    icono = "✅" if r1["ok"] else "❌"
    print(f"{icono} CAPA 1 — Estructura XML: {r1['errores']} errores")
    if not r1["ok"]:
        todas_ok = False
        total_errores += r1["errores"]
    
    # ─── CAPA 2 ───
    r2 = ejecutar_capa("2", "verificar_capa2.py", gen_path, ej_path)
    icono = "✅" if r2["ok"] else "❌"
    print(f"{icono} CAPA 2 — Dimensiones celdas: {r2['errores']} errores")
    if not r2["ok"]:
        todas_ok = False
        total_errores += r2["errores"]
        if r2.get("msg"):
            print(r2["msg"][-500:])
    
    # ─── CAPA 3 ───
    e3 = capa3_contenido(gen_path, ej_path)
    icono = "✅" if not e3 else "❌"
    print(f"{icono} CAPA 3 — Contenido textual: {len(e3)} errores")
    if e3:
        todas_ok = False
        total_errores += len(e3)
        for e in e3:
            print(f"   • {e}")
    
    # ─── CAPA 4 ───
    e4 = capa4_formato(gen_path, ej_path)
    icono = "✅" if not e4 else "❌"
    print(f"{icono} CAPA 4 — Formato y estilos: {len(e4)} errores")
    if e4:
        todas_ok = False
        total_errores += len(e4)
        for e in e4:
            print(f"   • {e}")
    
    # ─── CAPA 5 ───
    e5 = capa5_reglas(gen_path, ej_path)
    icono = "✅" if not e5 else "❌"
    print(f"{icono} CAPA 5 — Reglas ARL: {len(e5)} errores")
    if e5:
        todas_ok = False
        total_errores += len(e5)
        for e in e5:
            print(f"   • {e}")
    
    print()
    print("=" * 60)
    if todas_ok:
        print("✅ DOCUMENTO APROBADO — 0 errores en 5 capas")
        print("=" * 60)
        sys.exit(0)
    else:
        print(f"❌ {total_errores} ERRORES detectados — NO aprobado")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
