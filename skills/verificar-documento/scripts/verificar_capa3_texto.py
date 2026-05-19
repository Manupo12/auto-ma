#!/usr/bin/env python3
"""
CAPA 3 MEJORADA — Comparación de contenido textual celda por celda.
Detecta: texto faltante, texto sobrante, mayúsculas incorrectas, números donde
debían ir labels (ej: "5" en vez de "Día"), espaciado incorrecto, y más.

Uso: python3 verificar_capa3_texto.py <generado.docx> <ejemplo.docx>
"""

import sys, os, zipfile, xml.etree.ElementTree as ET
from collections import defaultdict

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def extraer_texto_celdas(docx_path):
    """Extrae texto de cada celda, preservando saltos de línea."""
    with zipfile.ZipFile(docx_path) as z:
        with z.open("word/document.xml") as f:
            tree = ET.parse(f)
    
    root = tree.getroot()
    celdas = {}
    
    for ti, tbl in enumerate(root.iter(f"{{{NS_W}}}tbl")):
        for fi, tr in enumerate(tbl.findall(f"{{{NS_W}}}tr")):
            for ci, tc in enumerate(tr.findall(f"{{{NS_W}}}tc")):
                # Extraer texto párrafo por párrafo
                parrafos = []
                for p in tc.findall(f"{{{NS_W}}}p"):
                    runs_text = []
                    for r in p.findall(f"{{{NS_W}}}r"):
                        t = r.find(f"{{{NS_W}}}t")
                        if t is not None and t.text:
                            runs_text.append(t.text)
                        # También capturar line breaks
                        for br in r.findall(f"{{{NS_W}}}br"):
                            runs_text.append("\n")
                    if runs_text:
                        parrafos.append("".join(runs_text))
                
                texto_completo = "\n".join(parrafos).strip()
                
                # También extraer información de formato del primer run
                primer_run_info = {}
                for p in tc.findall(f"{{{NS_W}}}p"):
                    for r in p.findall(f"{{{NS_W}}}r"):
                        rPr = r.find(f"{{{NS_W}}}rPr")
                        if rPr is not None:
                            sz = rPr.find(f"{{{NS_W}}}sz")
                            if sz is not None:
                                primer_run_info["font_size"] = int(sz.get(f"{{{NS_W}}}val", "0"))
                            b = rPr.find(f"{{{NS_W}}}b")
                            primer_run_info["bold"] = b is not None
                            color = rPr.find(f"{{{NS_W}}}color")
                            if color is not None:
                                primer_run_info["color"] = color.get(f"{{{NS_W}}}val", "")
                        break
                    break
                
                celdas[(ti, fi, ci)] = {
                    "texto": texto_completo,
                    "num_parrafos": len(parrafos),
                    "num_lineas": texto_completo.count("\n") + 1 if texto_completo else 0,
                    **primer_run_info
                }
    
    return celdas


def comparar_texto(gen_path, ej_path):
    """Compara el contenido textual de cada celda entre generado y ejemplo."""
    gen_celdas = extraer_texto_celdas(gen_path)
    ej_celdas = extraer_texto_celdas(ej_path)
    
    errores = []
    
    # Obtener todas las keys
    todas_keys = set(list(gen_celdas.keys()) + list(ej_celdas.keys()))
    
    for key in sorted(todas_keys):
        cg = gen_celdas.get(key)
        ce = ej_celdas.get(key)
        
        if not cg and not ce:
            continue
        
        tg = cg["texto"] if cg else ""
        te = ce["texto"] if ce else ""
        
        ti, fi, ci = key
        loc = f"T{ti} F{fi} C{ci}"
        
        # ═══════════════════════════════════════
        # 1. CELDA FALTANTE (está en ejemplo pero no en generado)
        # ═══════════════════════════════════════
        if not cg and ce and te:
            errores.append({
                "tipo": "TEXTO_FALTANTE",
                "ubicacion": loc,
                "ejemplo": te[:80],
                "msg": f"❌ {loc}: celda vacía en generado, ejemplo tiene: '{te[:60]}'"
            })
            continue
        
        # ═══════════════════════════════════════
        # 2. CELDA SOBRANTE (está en generado pero no en ejemplo)
        # ═══════════════════════════════════════
        if cg and not ce and tg:
            errores.append({
                "tipo": "TEXTO_SOBRANTE",
                "ubicacion": loc,
                "generado": tg[:80],
                "msg": f"⚠️  {loc}: texto sobrante en generado: '{tg[:60]}'"
            })
            continue
        
        if not tg and not te:
            continue
        
        # ═══════════════════════════════════════
        # 3. MAYÚSCULAS/MINÚSCULAS INCORRECTAS
        # ═══════════════════════════════════════
        if tg and te:
            # Comparar ignorando mayúsculas para ver si es el mismo texto
            if tg.lower() == te.lower() and tg != te:
                # Mismo texto, diferente capitalización
                diferencias = []
                for i, (cg_char, ce_char) in enumerate(zip(tg, te)):
                    if cg_char != ce_char:
                        diferencias.append(f"pos {i}: gen='{cg_char}' vs ej='{ce_char}'")
                if diferencias:
                    errores.append({
                        "tipo": "MAYUSCULAS",
                        "ubicacion": loc,
                        "gen": tg[:40],
                        "ej": te[:40],
                        "msg": f"🔤 {loc}: mayúsculas incorrectas — gen='{tg[:30]}' vs ej='{te[:30]}'"
                    })
        
        # ═══════════════════════════════════════
        # 4. LABEL REEMPLAZADO POR VALOR (ej: "Día" → "5")
        # ═══════════════════════════════════════
        if tg and te:
            # Si el ejemplo tiene texto corto tipo label (<10 chars) y el generado 
            # tiene un número en su lugar
            if len(te) < 10 and te.isalpha() and not te.isdigit() and te.strip():
                if tg.isdigit() or (len(tg) <= 2 and any(c.isdigit() for c in tg)):
                    errores.append({
                        "tipo": "LABEL_REEMPLAZADO_POR_NUMERO",
                        "ubicacion": loc,
                        "gen": tg,
                        "ej": te,
                        "critico": True,
                        "msg": f"❌ {loc}: '{te}' (label del ejemplo) fue reemplazado por '{tg}' (número) — ¡esto rompe el formato!"
                    })
                elif tg != te and len(te) <= 4 and te.lower() in ["día", "dia", "mes", "año", "ano", "edad"]:
                    errores.append({
                        "tipo": "LABEL_FECHA_REEMPLAZADO",
                        "ubicacion": loc,
                        "gen": tg,
                        "ej": te,
                        "critico": True,
                        "msg": f"❌ {loc}: label de fecha '{te}' fue reemplazado por '{tg}' — usar _poner_fecha_celdas correctamente"
                    })
        
        # ═══════════════════════════════════════
        # 5. TEXTO DUPLICADO / PEGADO
        # ═══════════════════════════════════════
        if tg and te:
            if len(tg) > len(te) * 1.5 and te in tg and len(te) > 2:
                errores.append({
                    "tipo": "TEXTO_DUPLICADO",
                    "ubicacion": loc,
                    "gen_len": len(tg),
                    "ej_len": len(te),
                    "msg": f"❌ {loc}: texto duplicado — gen={len(tg)} chars vs ej={len(te)} (contiene el texto del ejemplo + extra)"
                })
        
        # ═══════════════════════════════════════
        # 6. ESPACIADO INCORRECTO
        # ═══════════════════════════════════════
        if tg and te:
            # Detectar espacios extra o faltantes
            tg_normalizado = " ".join(tg.split())
            te_normalizado = " ".join(te.split())
            
            if tg_normalizado == te_normalizado and tg != te:
                # El texto es el mismo pero el espaciado difiere
                espacios_gen = len(tg) - len(tg.replace(" ", ""))
                espacios_ej = len(te) - len(te.replace(" ", ""))
                if abs(espacios_gen - espacios_ej) > 1:
                    errores.append({
                        "tipo": "ESPACIADO",
                        "ubicacion": loc,
                        "espacios_gen": espacios_gen,
                        "espacios_ej": espacios_ej,
                        "msg": f"⚠️  {loc}: espaciado diferente — gen={espacios_gen} espacios vs ej={espacios_ej}"
                    })
        
        # ═══════════════════════════════════════
        # 7. SEPARADOR "/" DONDE DEBERÍA HABER SALTOS DE LÍNEA
        # ═══════════════════════════════════════
        if tg and te:
            if " / " in tg and " / " not in te:
                if "\n" in te or cg.get("num_lineas", 1) > ce.get("num_lineas", 1):
                    errores.append({
                        "tipo": "SEPARADOR_SLASH",
                        "ubicacion": loc,
                        "msg": f"❌ {loc}: usa ' / ' como separador — el ejemplo tiene {ce.get('num_lineas', 1)} líneas (posiblemente con saltos de línea)"
                    })
        
        # ═══════════════════════════════════════
        # 8. NÚMERO DE LÍNEAS DIFERENTE
        # ═══════════════════════════════════════
        if tg and te and len(tg) > 20 and len(te) > 20:
            lineas_gen = cg.get("num_lineas", 1)
            lineas_ej = ce.get("num_lineas", 1)
            if lineas_gen != lineas_ej and abs(lineas_gen - lineas_ej) > 1:
                errores.append({
                    "tipo": "NUMERO_LINEAS",
                    "ubicacion": loc,
                    "gen": lineas_gen,
                    "ej": lineas_ej,
                    "msg": f"⚠️  {loc}: líneas gen={lineas_gen} vs ej={lineas_ej}"
                })
        
        # ═══════════════════════════════════════
        # 9. NOMBRE TRUNCADO
        # ═══════════════════════════════════════
        nombres_clave = [
            "SANDRA PATRICIA POLANIA OSORIO",
            "REHABILITACION INTEGRAL LABORAL Y OCUPACIONAL SAS",
            "Fisioterapeuta Esp."
        ]
        for nombre in nombres_clave:
            if nombre.lower() in te.lower() and nombre.lower() not in tg.lower():
                # Buscar si hay una versión truncada
                partes = nombre.split()
                for i in range(len(partes) - 1, 0, -1):
                    truncado = " ".join(partes[:i])
                    if truncado.lower() in tg.lower() and nombre.lower() not in tg.lower():
                        errores.append({
                            "tipo": "NOMBRE_TRUNCADO",
                            "ubicacion": loc,
                            "gen": truncado,
                            "ej": nombre,
                            "msg": f"❌ {loc}: nombre truncado — gen='{truncado}' vs ej='{nombre}'"
                        })
                        break
        
        # ═══════════════════════════════════════
        # 10. TEXTO COMPLETAMENTE DIFERENTE (misma posición, texto no relacionado)
        # ═══════════════════════════════════════
        if tg and te and len(te) > 3 and len(tg) > 3:
            # Si comparten menos del 30% de palabras
            palabras_gen = set(tg.lower().split())
            palabras_ej = set(te.lower().split())
            if palabras_gen and palabras_ej:
                interseccion = palabras_gen & palabras_ej
                union = palabras_gen | palabras_ej
                similitud = len(interseccion) / len(union) if union else 0
                if similitud < 0.3 and len(te) > 10 and len(tg) > 10:
                    errores.append({
                        "tipo": "TEXTO_DIFERENTE",
                        "ubicacion": loc,
                        "similitud": f"{similitud:.0%}",
                        "msg": f"⚠️  {loc}: texto muy diferente al ejemplo (similitud {similitud:.0%})"
                    })
    
    return errores


def main():
    if len(sys.argv) != 3:
        print("Uso: verificar_capa3_texto.py <generado.docx> <ejemplo.docx>")
        sys.exit(1)
    
    gen_path, ej_path = sys.argv[1], sys.argv[2]
    errores = comparar_texto(gen_path, ej_path)
    
    print("=" * 60)
    print("CAPA 3 — Contenido textual (MEJORADA)")
    print("=" * 60)
    
    if not errores:
        print("✅ 0 errores de contenido textual")
        sys.exit(0)
    
    # Agrupar por tipo
    from collections import Counter
    tipos = Counter(e["tipo"] for e in errores)
    
    criticos = [e for e in errores if e.get("critico")]
    
    print(f"❌ {len(errores)} errores ({len(criticos)} críticos):\n")
    print("Resumen por tipo:")
    for tipo, count in tipos.most_common():
        print(f"   {tipo}: {count}")
    
    print(f"\n{'─'*40}")
    print("Detalle (críticos primero):")
    for e in sorted(errores, key=lambda x: (not x.get("critico"), x["ubicacion"])):
        icono = "⚠️ " if e.get("critico") else "• "
        print(f"{icono}{e['msg']}")
    
    sys.exit(1)


if __name__ == "__main__":
    main()
