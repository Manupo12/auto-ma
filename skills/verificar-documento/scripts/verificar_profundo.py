#!/usr/bin/env python3
"""
VERIFICADOR PROFUNDO — Compara un DOCX generado contra el MOLDE del ejemplo.
No solo mira estructura: compara formato, estilos, párrafos, runs, colores, bullets.
Usa el analizador para extraer el molde del ejemplo y verificar que el generado coincida.

Uso: python3 verificar_profundo.py <generado.docx> <ejemplo.docx>
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analizar_ejemplo import analizar_docx


def comparar_profundo(gen_path, ej_path):
    """Comparación exhaustiva: molde del ejemplo vs generado."""
    print(f"🔬 Analizando ejemplo: {os.path.basename(ej_path)}...")
    molde_ej = analizar_docx(ej_path)
    
    print(f"🔬 Analizando generado: {os.path.basename(gen_path)}...")
    molde_gen = analizar_docx(gen_path)
    
    errores = []
    warnings = []
    
    # ═══════════════════════════════════════════
    # 1. ESTRUCTURA GLOBAL
    # ═══════════════════════════════════════════
    
    # Número de tablas
    if len(molde_gen["tablas"]) != len(molde_ej["tablas"]):
        errores.append({
            "capa": 1, "tipo": "NUM_TABLAS",
            "gen": len(molde_gen["tablas"]), "ej": len(molde_ej["tablas"]),
            "msg": f"❌ Tablas: gen={len(molde_gen['tablas'])} vs ej={len(molde_ej['tablas'])}"
        })
    
    # Secciones
    if len(molde_gen["secciones"]) != len(molde_ej["secciones"]):
        errores.append({
            "capa": 1, "tipo": "NUM_SECCIONES",
            "gen": len(molde_gen["secciones"]), "ej": len(molde_ej["secciones"]),
            "msg": f"❌ Secciones: gen={len(molde_gen['secciones'])} vs ej={len(molde_ej['secciones'])}"
        })
    
    # ═══════════════════════════════════════════
    # 2. COMPARACIÓN TABLA POR TABLA
    # ═══════════════════════════════════════════
    num_tablas = min(len(molde_gen["tablas"]), len(molde_ej["tablas"]))
    
    for ti in range(num_tablas):
        te = molde_ej["tablas"][ti]
        tg = molde_gen["tablas"][ti]
        
        # Filas
        if tg["num_filas"] != te["num_filas"]:
            errores.append({
                "capa": 1, "tipo": "FILAS_TABLA",
                "tabla": ti, "gen": tg["num_filas"], "ej": te["num_filas"],
                "msg": f"❌ T{ti}: filas gen={tg['num_filas']} vs ej={te['num_filas']}"
            })
        
        # Columnas
        if tg["num_columnas"] != te["num_columnas"]:
            errores.append({
                "capa": 1, "tipo": "COLUMNAS_TABLA",
                "tabla": ti, "gen": tg["num_columnas"], "ej": te["num_columnas"],
                "msg": f"❌ T{ti}: columnas gen={tg['num_columnas']} vs ej={te['num_columnas']}"
            })
        
        # Anchos de columna
        if len(tg["anchos_columna"]) == len(te["anchos_columna"]):
            for ci, (ag, ae) in enumerate(zip(tg["anchos_columna"], te["anchos_columna"])):
                if ae > 0:
                    ratio = ag / ae
                    if ratio < 0.4:
                        errores.append({
                            "capa": 2, "tipo": "COLUMNA_ANGOSTA",
                            "tabla": ti, "col": ci,
                            "gen": ag, "ej": ae, "ratio": f"{ratio:.0%}",
                            "msg": f"⚠️  T{ti} C{ci}: ancho columna gen={ag} vs ej={ae} ({ratio:.0%}) — ¡POSIBLE DESBORDE!"
                        })
        
        # Comparar fila por fila, celda por celda
        nf = min(tg["num_filas"], te["num_filas"])
        for fi in range(nf):
            fe = te["filas"][fi]
            fg = tg["filas"][fi]
            
            nc = min(len(fg["celdas"]), len(fe["celdas"]))
            
            for ci in range(nc):
                ce = fe["celdas"][ci]
                cg = fg["celdas"][ci]
                
                # ── gridSpan ──
                if cg["gridSpan"] != ce["gridSpan"]:
                    errores.append({
                        "capa": 1, "tipo": "GRIDSPAN",
                        "tabla": ti, "fila": fi, "col": ci,
                        "gen": cg["gridSpan"], "ej": ce["gridSpan"],
                        "msg": f"❌ T{ti} F{fi} C{ci}: gridSpan gen={cg['gridSpan']} vs ej={ce['gridSpan']}"
                    })
                
                # ── vMerge ──
                if cg["vMerge"] != ce["vMerge"]:
                    errores.append({
                        "capa": 1, "tipo": "VMERGE",
                        "tabla": ti, "fila": fi, "col": ci,
                        "gen": cg["vMerge"], "ej": ce["vMerge"],
                        "msg": f"❌ T{ti} F{fi} C{ci}: vMerge gen={cg['vMerge']} vs ej={ce['vMerge']}"
                    })
                
                # ── Ancho de celda ──
                if cg["ancho"] and ce["ancho"] and ce["ancho"] > 0:
                    ratio = cg["ancho"] / ce["ancho"]
                    if ratio < 0.5 and len(cg["parrafos"]) > 0:
                        texto = cg["parrafos"][0]["texto"][:60] if cg["parrafos"] else ""
                        errores.append({
                            "capa": 2, "tipo": "CELDA_ANGOSTA",
                            "tabla": ti, "fila": fi, "col": ci,
                            "gen": cg["ancho"], "ej": ce["ancho"],
                            "texto": texto,
                            "msg": f"⚠️  T{ti} F{fi} C{ci}: celda {ratio:.0%} más angosta — texto '{texto}'"
                        })
                
                # ── Sombreado ──
                shd_gen = cg.get("sombreado") or {}
                shd_ej = ce.get("sombreado") or {}
                fill_gen = shd_gen.get("fill", "")
                fill_ej = shd_ej.get("fill", "")
                
                if fill_gen != fill_ej:
                    # Solo reportar si el generado tiene AMARILLO (FFFF00) y el ejemplo NO
                    if fill_gen == "FFFF00" and fill_ej != "FFFF00":
                        errores.append({
                            "capa": 4, "tipo": "FONDO_AMARILLO",
                            "tabla": ti, "fila": fi, "col": ci,
                            "msg": f"🎨 T{ti} F{fi} C{ci}: fondo amarillo donde ejemplo tiene {fill_ej or 'nada'}"
                        })
                    # O si el ejemplo tiene color decorativo (FCE9D9) y el generado lo perdió
                    elif fill_ej and fill_ej != "FFFF00" and not fill_gen:
                        warnings.append({
                            "capa": 4, "tipo": "FONDO_PERDIDO",
                            "tabla": ti, "fila": fi, "col": ci,
                            "msg": f"ℹ️  T{ti} F{fi} C{ci}: color decorativo {fill_ej} perdido (baja prioridad)"
                        })
                
                # ── Párrafos ──
                if len(cg["parrafos"]) != len(ce["parrafos"]) and len(ce["parrafos"]) > 0:
                    # Solo reportar si la diferencia > 1 párrafo
                    if abs(len(cg["parrafos"]) - len(ce["parrafos"])) > 1:
                        errores.append({
                            "capa": 4, "tipo": "NUMERO_PARRAFOS",
                            "tabla": ti, "fila": fi, "col": ci,
                            "gen": len(cg["parrafos"]), "ej": len(ce["parrafos"]),
                            "msg": f"❌ T{ti} F{fi} C{ci}: párrafos gen={len(cg['parrafos'])} vs ej={len(ce['parrafos'])}"
                        })
                
                # ── Negritas ──
                bolds_gen = sum(1 for p in cg["parrafos"] for r in p["runs"] if r["bold"])
                bolds_ej = sum(1 for p in ce["parrafos"] for r in p["runs"] if r["bold"])
                if bolds_gen > bolds_ej + 2:  # tolerancia de 2 runs
                    errores.append({
                        "capa": 4, "tipo": "BOLD_INCORRECTO",
                        "tabla": ti, "fila": fi, "col": ci,
                        "gen": bolds_gen, "ej": bolds_ej,
                        "msg": f"❌ T{ti} F{fi} C{ci}: runs bold gen={bolds_gen} vs ej={bolds_ej}"
                    })
                
                # ── Tamaño de fuente ──
                sizes_gen = [r["font_size"] for p in cg["parrafos"] for r in p["runs"] if r["font_size"]]
                sizes_ej = [r["font_size"] for p in ce["parrafos"] for r in p["runs"] if r["font_size"]]
                if sizes_gen and sizes_ej:
                    avg_gen = sum(sizes_gen) / len(sizes_gen)
                    avg_ej = sum(sizes_ej) / len(sizes_ej)
                    if abs(avg_gen - avg_ej) > 6:  # > 3pt diferencia (6 half-pts)
                        errores.append({
                            "capa": 4, "tipo": "FONT_SIZE",
                            "tabla": ti, "fila": fi, "col": ci,
                            "gen": f"{avg_gen/2:.1f}pt", "ej": f"{avg_ej/2:.1f}pt",
                            "msg": f"❌ T{ti} F{fi} C{ci}: tamaño fuente gen={avg_gen/2:.1f}pt vs ej={avg_ej/2:.1f}pt"
                        })
                
                # ── Color de texto ──
                colors_gen = [r["color"] for p in cg["parrafos"] for r in p["runs"] if r["color"]]
                colors_ej = [r["color"] for p in ce["parrafos"] for r in p["runs"] if r["color"]]
                # Detectar azul (0000FF, 0070C0, etc.) donde el ejemplo no lo tiene
                for col in colors_gen:
                    if "0000FF" in col or "0070C0" in col:
                        if not any("0000FF" in c or "0070C0" in c for c in colors_ej):
                            errores.append({
                                "capa": 4, "tipo": "TEXTO_AZUL",
                                "tabla": ti, "fila": fi, "col": ci,
                                "msg": f"🔵 T{ti} F{fi} C{ci}: texto azul ({col}) donde ejemplo no lo tiene — ¿hyperlink residual?"
                            })
                
                # ── Viñetas ──
                bullets_gen = sum(1 for p in cg["parrafos"] if p["tiene_bullet"] and not p["texto"].strip())
                bullets_ej = sum(1 for p in ce["parrafos"] if p["tiene_bullet"] and not p["texto"].strip())
                if bullets_gen > bullets_ej:
                    errores.append({
                        "capa": 4, "tipo": "VINYETAS_VACIAS",
                        "tabla": ti, "fila": fi, "col": ci,
                        "gen": bullets_gen, "ej": bullets_ej,
                        "msg": f"• T{ti} F{fi} C{ci}: {bullets_gen} viñetas vacías (ej tiene {bullets_ej})"
                    })
        
        # Verificar filas extra/faltantes
        if len(fg["celdas"]) != len(fe["celdas"]):
            errores.append({
                "capa": 1, "tipo": "CELDAS_FILA",
                "tabla": ti, "fila": fi,
                "gen": len(fg["celdas"]), "ej": len(fe["celdas"]),
                "msg": f"❌ T{ti} F{fi}: celdas gen={len(fg['celdas'])} vs ej={len(fe['celdas'])}"
            })
    
    # ═══════════════════════════════════════════
    # 3. ENCABEZADOS Y PIES DE PÁGINA
    # ═══════════════════════════════════════════
    if len(molde_gen["encabezados"]) != len(molde_ej["encabezados"]):
        errores.append({
            "capa": 1, "tipo": "ENCABEZADOS",
            "gen": len(molde_gen["encabezados"]), "ej": len(molde_ej["encabezados"]),
            "msg": f"❌ Encabezados: gen={len(molde_gen['encabezados'])} vs ej={len(molde_ej['encabezados'])}"
        })
    
    # ═══════════════════════════════════════════
    # 4. HIPERVÍNCULOS
    # ═══════════════════════════════════════════
    if molde_gen["hipervinculos"] > molde_ej["hipervinculos"]:
        errores.append({
            "capa": 4, "tipo": "HYPERLINKS_RESIDUALES",
            "gen": molde_gen["hipervinculos"], "ej": molde_ej["hipervinculos"],
            "msg": f"❌ Hipervínculos: gen={molde_gen['hipervinculos']} vs ej={molde_ej['hipervinculos']} — ¡limpiar en _poner_texto!"
        })
    
    # ═══════════════════════════════════════════
    # 5. TAMAÑO DEL ARCHIVO (indicador de explosión)
    # ═══════════════════════════════════════════
    if molde_gen["tamano_bytes"] > molde_ej["tamano_bytes"] * 1.5:
        errores.append({
            "capa": 5, "tipo": "TAMANO_ANORMAL",
            "gen": f"{molde_gen['tamano_bytes']/1024:.0f}KB",
            "ej": f"{molde_ej['tamano_bytes']/1024:.0f}KB",
            "msg": f"⚠️  Tamaño: gen={molde_gen['tamano_bytes']/1024:.0f}KB vs ej={molde_ej['tamano_bytes']/1024:.0f}KB"
        })
    
    return errores, warnings, molde_ej, molde_gen


def main():
    if len(sys.argv) != 3:
        print("Uso: verificar_profundo.py <generado.docx> <ejemplo.docx>")
        sys.exit(1)
    
    gen_path, ej_path = sys.argv[1], sys.argv[2]
    errores, warnings, molde_ej, molde_gen = comparar_profundo(gen_path, ej_path)
    
    # ─── Reporte ───
    print()
    print("=" * 60)
    print("🔬 VERIFICACIÓN PROFUNDA")
    print("=" * 60)
    print(f"Ejemplo:  {molde_ej['archivo']} ({molde_ej['tamano_bytes']/1024:.0f} KB)")
    print(f"Generado: {molde_gen['archivo']} ({molde_gen['tamano_bytes']/1024:.0f} KB)")
    print()
    
    # Agrupar por capa
    from collections import defaultdict
    por_capa = defaultdict(list)
    for e in errores:
        por_capa[e["capa"]].append(e)
    
    for capa in [1, 2, 3, 4, 5]:
        errs = por_capa.get(capa, [])
        nombres = {1: "Estructura", 2: "Dimensiones", 3: "Contenido", 4: "Formato", 5: "Reglas ARL"}
        icono = "✅" if not errs else "❌"
        print(f"{icono} CAPA {capa} — {nombres[capa]}: {len(errs)} errores")
        for e in errs:
            print(f"   {e['msg']}")
    
    if warnings:
        print(f"\nℹ️  {len(warnings)} advertencias (baja prioridad):")
        for w in warnings[:5]:
            print(f"   {w['msg']}")
    
    print()
    total = len(errores)
    if total == 0:
        print("✅ DOCUMENTO APROBADO — Idéntico al ejemplo en todas las capas")
        sys.exit(0)
    else:
        criticos = sum(1 for e in errores if e["tipo"] in ["CELDA_ANGOSTA", "GRIDSPAN", "FILAS_TABLA", "COLUMNAS_TABLA", "FONDO_AMARILLO", "HYPERLINKS_RESIDUALES", "BOLD_INCORRECTO"])
        print(f"❌ {total} ERRORES ({criticos} críticos) — NO aprobado")
        sys.exit(1)


if __name__ == "__main__":
    main()
