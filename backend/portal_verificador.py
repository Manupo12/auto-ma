"""
Verificador cruzado de portales para el chat de Tomy.

Flujo:
  1. chat_handler detecta intencion de portal
  2. Llama a PortalVerificador.verificar(cc)
  3. Si hay JSON local fresco (<24h): compara sin navegar
  4. Si es viejo o no existe: navega y actualiza
  5. Retorna reporte de discrepancias listo para el LLM
"""
import asyncio, json, os, unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./storage"))
KNOWLEDGE_PATH = STORAGE_DIR / "portal_knowledge.json"
DATA_DIR = STORAGE_DIR / "data"


def _norm(s: str) -> str:
    if not s: return ""
    n = unicodedata.normalize("NFD", str(s).lower().strip())
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    return " ".join(n.split())


class PortalVerificador:
    def __init__(self):
        self._k = self._load_knowledge()

    def verificar(self, cc: str, forzar_extraccion: bool = False) -> dict:
        json_local = self._leer_json_local(cc)
        es_fresco = self._es_fresco(json_local)

        if forzar_extraccion or not es_fresco:
            _log(f"PORTAL: extrayendo portales para CC {cc}...")
            try:
                from backend.playwright_real.orquestador import extraer_paciente_completo
                datos_frescos = asyncio.run(extraer_paciente_completo(cc, guardar=True))
                json_local = datos_frescos
            except Exception as e:
                _log(f"PORTAL: extraccion fallo → {e}")
                if not json_local:
                    return {"error": f"No pude acceder a los portales: {e}", "cc": cc}

        return self._comparar_con_local(cc, json_local)

    def verificar_vs_docx(self, cc: str, ruta_docx: str) -> dict:
        from backend.chat_handler import _leer_docx
        texto_docx = _leer_docx(Path(ruta_docx))
        import re
        datos_docx = {}

        m = re.search(r"C\.?C\.?\s*[:\-]?\s*(\d{6,12})", texto_docx)
        if m: datos_docx["documento"] = m.group(1)
        m = re.search(r"[Ss]iniestro\s*[:\-]?\s*(\d{8,12})", texto_docx)
        if m: datos_docx["siniestro"] = m.group(1)
        m = re.search(r"\b([A-Z]\d{2,3})\b", texto_docx)
        if m: datos_docx["cie10_docx"] = m.group(1)

        resultado_portal = self.verificar(cc)
        resultado_portal["docx_comparacion"] = datos_docx
        resultado_portal["docx_nombre"] = Path(ruta_docx).name
        return resultado_portal

    def _comparar_con_local(self, cc: str, datos_portal: dict) -> dict:
        resultado = {
            "cc": cc,
            "campos": [],
            "discrepancias": [],
            "confianza": 1.0,
            "fuente_extraccion": datos_portal.get("_meta", {}).get("extraido_en", "desconocida"),
            "parcial": datos_portal.get("_meta", {}).get("parcial", False),
        }

        disc_portales = datos_portal.get("_meta", {}).get("discrepancias", [])
        for d in disc_portales:
            d["resolucion_conocida"] = self._buscar_resolucion_conocida(cc, d["campo"])
        resultado["discrepancias"] = disc_portales

        datos_medi = datos_portal.get("medifolios", {})
        datos_pos = datos_portal.get("positiva", {})

        # Siniestro: buscar en medifolios.siniestro_medi y positiva.siniestro_id/siniestros
        siniestro_medi = datos_medi.get("siniestro_medi", "")
        siniestro_pos = datos_pos.get("siniestro_id", "")
        if not siniestro_pos:
            siniestros_pos = datos_pos.get("siniestros", [])
            siniestro_pos = siniestros_pos[0].get("id", "") if siniestros_pos else ""

        # Nombre: buscar en medifolios.nombre1+apellido1 o medifolios.nombre, positiva.nombre_detectado
        nombre_medi = datos_medi.get("nombre1", "") or datos_medi.get("nombre", "")
        apellido_medi = datos_medi.get("apellido1", "")
        if nombre_medi and apellido_medi:
            nombre_medi = f"{nombre_medi} {apellido_medi}".strip()
        nombre_pos = datos_pos.get("nombre_detectado", "") or (datos_pos.get("datos_asegurado") or {}).get("nombre", "")

        # Diagnostico CIE-10
        diag_medi = datos_medi.get("diagnostico_cie10", "")
        diagnosticos_pos = datos_pos.get("diagnosticos", [])
        cie10_pos = datos_pos.get("cie10_candidatos", []) or datos_pos.get("cie10_encontrados", [])
        diag_pos = ""
        if diagnosticos_pos:
            diag_pos = diagnosticos_pos[0].get("codigo", "")
        elif cie10_pos:
            diag_pos = cie10_pos[0]

        # Empresa
        empresa_medi = datos_medi.get("empresa", "")
        empresa_pos = (datos_pos.get("datos_asegurado") or {}).get("empresa", "")

        campos_verificados = [
            ("nombre", nombre_medi, nombre_pos),
            ("siniestro", siniestro_medi, siniestro_pos),
            ("diagnostico CIE-10", diag_medi, diag_pos),
            ("empresa", empresa_medi, empresa_pos),
        ]

        n_ok = 0
        for nombre_campo, val_medi, val_pos in campos_verificados:
            coincide = not val_medi or not val_pos or _norm(str(val_medi)) == _norm(str(val_pos))
            if coincide: n_ok += 1
            resultado["campos"].append({
                "campo": nombre_campo,
                "medifolios": val_medi or "",
                "positiva": val_pos or "",
                "coincide": coincide,
            })

        total = len(campos_verificados)
        resultado["confianza"] = round(n_ok / total, 2) if total > 0 else 0.0
        self._registrar_verificacion(cc, resultado)
        return resultado

    def aprender_correccion(self, cc: str, campo: str, valor_correcto: str, fuente: str = "sandra"):
        correcciones = self._k.setdefault("correcciones_confirmadas", [])
        correcciones.append({
            "cc": cc, "campo": campo, "valor_correcto": valor_correcto,
            "fuente": fuente, "fecha": datetime.now().isoformat()[:10],
        })
        self._save_knowledge()

        json_path = DATA_DIR / f"{cc}-completo.json"
        if json_path.exists():
            datos = json.loads(json_path.read_text(encoding="utf-8"))
            campo_map = {
                "siniestro": ["positiva", "siniestro_principal", "id"],
                "diagnostico_cie10": ["positiva", "siniestros", 0, "diagnostico"],
                "nombre": ["medifolios", "nombre"],
            }
            ruta = campo_map.get(campo)
            if ruta:
                d = datos
                for k in ruta[:-1]:
                    d = d[k] if isinstance(k, str) else (d[k] if len(d) > k else d)
                if isinstance(ruta[-1], str):
                    d[ruta[-1]] = valor_correcto
                datos["_meta"]["ultima_correccion"] = datetime.now().isoformat()
                json_path.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")

        _log(f"APRENDIZAJE: CC {cc} campo '{campo}' = '{valor_correcto}' (fuente: {fuente})")

    def aprender_ruta_exitosa(self, portal: str, seccion: str, instruccion: str, pasos: list):
        rutas = self._k.setdefault("rutas_aprendidas", {}).setdefault(portal, [])
        for r in rutas:
            if r.get("seccion") == seccion:
                r["exitos"] = r.get("exitos", 0) + 1
                r["ultimo_uso"] = datetime.now().isoformat()[:10]
                self._save_knowledge()
                return
        rutas.append({
            "seccion": seccion, "instruccion_original": instruccion,
            "pasos": pasos, "exitos": 1,
            "primer_uso": datetime.now().isoformat()[:10],
            "ultimo_uso": datetime.now().isoformat()[:10],
        })
        self._save_knowledge()

    def reportar_portal_caido(self, portal: str, error: str):
        problemas = self._k.setdefault("portales_caidos", [])
        problemas.append({"portal": portal, "error": error[:200], "fecha": datetime.now().isoformat()})
        self._save_knowledge()
        try:
            from backend.notificador import enviar_telegram_manu
            enviar_telegram_manu(f"Portal {portal} caido: {error[:100]}")
        except Exception:
            pass

    def _buscar_resolucion_conocida(self, cc: str, campo: str) -> Optional[str]:
        for c in self._k.get("correcciones_confirmadas", []):
            if c.get("cc") == cc and c.get("campo") == campo:
                return f"Sandra confirmo anteriormente: usar '{c['valor_correcto']}' (fuente: {c['fuente']})"
        return None

    def _es_fresco(self, json_local: Optional[dict], max_horas: int = 24) -> bool:
        if not json_local: return False
        extraido = json_local.get("_meta", {}).get("extraido_en", "")
        if not extraido: return False
        try:
            dt = datetime.fromisoformat(extraido)
            return datetime.now() - dt < timedelta(hours=max_horas)
        except Exception:
            return False

    def _leer_json_local(self, cc: str) -> Optional[dict]:
        path = DATA_DIR / f"{cc}-completo.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    def _registrar_verificacion(self, cc: str, resultado: dict):
        historial = self._k.setdefault("historial_verificaciones", [])
        historial.append({
            "cc": cc, "fecha": datetime.now().isoformat()[:10],
            "confianza": resultado["confianza"],
            "n_discrepancias": len(resultado["discrepancias"]),
        })
        self._k["historial_verificaciones"] = historial[-200:]
        self._save_knowledge()

    def _load_knowledge(self) -> dict:
        if KNOWLEDGE_PATH.exists():
            try:
                return json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"version": "1.0", "creado": datetime.now().isoformat()[:10]}

    def _save_knowledge(self):
        KNOWLEDGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._k["ultima_actualizacion"] = datetime.now().isoformat()[:10]
        KNOWLEDGE_PATH.write_text(
            json.dumps(self._k, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _log(msg: str):
    import sys
    print(f"[PORTAL {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)
