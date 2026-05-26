"""
Paso del workflow: verificar datos sintetizados contra los portales.

Automatico — se ejecuta siempre despues de la sintesis.
- Extrae datos de Medifolios + Positiva
- Cruza TODOS los campos sensibles con los datos sintetizados
- Enriquece campos faltantes con lo que encuentra en portales
- Marca verificaciones: confirmado, pendiente_portal, discrepancia
"""
import os, sys, json, asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict


def _log(msg: str):
    print(f"[VERIFICAR {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)
CAMPOS_SENSIBLES = [
    ("paciente.nombre", ["paciente.nombre", "nombre", "nombre1", "nombre_detectado"]),
    ("paciente.documento", ["paciente.documento", "cc", "numero_id", "documento"]),
    ("siniestro.id_siniestro", ["siniestro.id_siniestro", "siniestro_id", "siniestro_medi", "id"]),
    ("siniestro.fecha_evento", ["siniestro.fecha_evento", "fecha_siniestro", "fecha"]),
    ("siniestro.diagnostico_cie10", ["siniestro.diagnostico_cie10", "diagnostico_cie10", "diagnostico", "cie10_encontrados"]),
    ("siniestro.descripcion", ["siniestro.descripcion", "descripcion"]),
    ("empresa.nombre", ["empresa.nombre", "empresa"]),
    ("empresa.cargo", ["empresa.cargo", "cargo", "paciente.ocupacion"]),
    ("paciente.direccion", ["paciente.direccion", "direccion"]),
    ("paciente.telefono", ["paciente.telefono", "telefono"]),
    ("paciente.eps_ips", ["paciente.eps_ips", "eps"]),
    ("paciente.afp", ["paciente.afp", "afp"]),
    ("siniestro.tipo_evento", ["siniestro.tipo_evento", "tipo"]),
    ("siniestro.segmento", ["siniestro.segmento", "segmento_corporal", "segmento"]),
]


def _get_valor_sintesis(datos: dict, rutas: list) -> str:
    """Busca valor en dict anidado por rutas alternativas."""
    for ruta in rutas:
        partes = ruta.split(".")
        val = datos
        for p in partes:
            if isinstance(val, dict):
                val = val.get(p, "")
            else:
                val = ""
                break
        if val and str(val).strip():
            return str(val).strip()
    return ""


def _extraer_de_portales(cc: str, datos_portales_cache: dict = None) -> dict:
    """Usa datos del portal YA extraidos por resolver_paciente (paso 2)."""
    import json as _json

    if datos_portales_cache and not datos_portales_cache.get("_vacio"):
        _log(f"Usando datos del portal del paso 2 (resolver_paciente)")
        return datos_portales_cache

    cache_path = Path(os.getenv("STORAGE_DIR", "./storage")) / "data" / f"{cc}-completo.json"
    if cache_path.exists():
        try:
            cached = _json.loads(cache_path.read_text(encoding="utf-8"))
            medi = cached.get("medifolios", {})
            pos = cached.get("positiva", {})
            if medi.get("nombre1") or pos.get("siniestro_id") or (pos.get("siniestros") and pos["siniestros"][0].get("id")):
                _log(f"Cache JSON del portal encontrado: {cache_path.name}")
                return cached
        except Exception:
            pass

    _log("Extrayendo de portales con Playwright (ultimo recurso)...")
    try:
        from backend.playwright_real.orquestador import extraer_paciente_completo
        resultado = asyncio.run(extraer_paciente_completo(cc, guardar=True))
        _log(f"Playwright: {'parcial' if resultado.get('_meta',{}).get('parcial') else 'completo'}")
        return resultado
    except Exception as e:
        _log(f"Playwright error: {e}")

    return {
        "_meta": {"parcial": True, "error": "Sin datos de portales", "extraido_en": datetime.now().isoformat()},
        "medifolios": {}, "positiva": {}
    }


def _set_nested(d: dict, path: str, value):
    """Set a nested dict value by dot-notation path (e.g. 'paciente.nombre')."""
    partes = path.split(".")
    for p in partes[:-1]:
        if p not in d or not isinstance(d[p], dict):
            d[p] = {}
        d = d[p]
    d[partes[-1]] = value


def _normalizar(texto: str) -> str:
    """Normaliza para comparacion: minusculas, sin tildes, sin espacios extra."""
    if not texto:
        return ""
    import unicodedata
    t = unicodedata.normalize("NFD", str(texto).lower().strip())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return " ".join(t.split())


def ejecutar(datos_clinicos: dict, paciente_cc: str, datos_portales_cache: dict = None) -> dict:
    """
    Punto de entrada. Verifica los datos sintetizados contra portales.
    
    Args:
        datos_clinicos: dict con datos sintetizados por la IA
        paciente_cc: cedula del paciente
        datos_portales_cache: datos del portal cacheados del paso 2
    
    Returns:
        dict con datos_enriquecidos, verificaciones, campos_faltantes
    """
    _log(f"Verificando CC {paciente_cc} contra portales...")

    portales = _extraer_de_portales(paciente_cc, datos_portales_cache)
    parcial = portales.get("_meta", {}).get("parcial", True)
    medi = portales.get("medifolios", {})
    pos = portales.get("positiva", {})

    verificaciones = []
    campos_completados = {}
    datos_enriquecidos = dict(datos_clinicos) if datos_clinicos else {}

    for nombre_campo, rutas_sintesis in CAMPOS_SENSIBLES:
        val_sintesis = _get_valor_sintesis(datos_clinicos, rutas_sintesis)

        val_portal = ""
        fuente_portal = ""
        for fuente, datos_fuente in [("medifolios", medi), ("positiva", pos)]:
            for ruta in rutas_sintesis:
                val = _get_valor_sintesis(datos_fuente, [ruta])
                if val:
                    val_portal = val
                    fuente_portal = fuente
                    break
            if val_portal:
                break

        estado = "no_verificado"
        if not val_sintesis and not val_portal:
            if parcial:
                estado = "no_verificado"
            else:
                estado = "faltante"
        elif not val_sintesis and val_portal:
            estado = "completado_portal"
            campos_completados[nombre_campo] = val_portal
        elif val_sintesis and not val_portal:
            estado = "pendiente_portal"
        elif _normalizar(val_sintesis) == _normalizar(val_portal):
            estado = "confirmado"
        else:
            estado = "discrepancia"

        verificaciones.append({
            "campo": nombre_campo,
            "sintesis": val_sintesis,
            "portal": val_portal,
            "fuente_portal": fuente_portal,
            "estado": estado,
        })

    for v in verificaciones:
        if v["estado"] == "discrepancia" and v["campo"].startswith("paciente."):
            _set_nested(datos_enriquecidos, v["campo"], v["portal"])
            v["estado"] = "corregido_por_portal"
            v["nota"] = f"Auto-corregido: LLM={v['sintesis']} -> Portal={v['portal']}"
            _log(f"Auto-correccion identidad: {v['campo']} '{v['sintesis']}' -> '{v['portal']}'")

    resumen = {
        "confirmados": sum(1 for v in verificaciones if v["estado"] == "confirmado"),
        "completados_portal": sum(1 for v in verificaciones if v["estado"] == "completado_portal"),
        "pendientes_portal": sum(1 for v in verificaciones if v["estado"] == "pendiente_portal"),
        "discrepancias": sum(1 for v in verificaciones if v["estado"] == "discrepancia"),
        "faltantes": sum(1 for v in verificaciones if v["estado"] == "faltante"),
        "no_verificados": sum(1 for v in verificaciones if v["estado"] == "no_verificado"),
        "total": len(verificaciones),
    }

    ok = resumen["discrepancias"] == 0 and resumen["faltantes"] <= 3

    _log(
        f"Verificacion: {resumen['confirmados']} conf, "
        f"{resumen['completados_portal']} completados, "
        f"{resumen['pendientes_portal']} pendientes, "
        f"{resumen['discrepancias']} discrepancias, "
        f"{resumen['faltantes']} faltantes"
    )

    return {
        "ok": ok,
        "verificaciones": verificaciones,
        "resumen": resumen,
        "campos_completados": campos_completados,
        "datos_enriquecidos": datos_enriquecidos,
        "parcial": parcial,
    }
