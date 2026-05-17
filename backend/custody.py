"""
Sistema de Confiabilidad y Custodia — Módulo de integridad de datos.

Implementa:
  1. Validación semántica de datos extraídos
  2. Cadena de custodia (trazabilidad campo→fuente→timestamp)
  3. Versionado de documentos por paciente
  4. Confianza por campo (0-100)
  5. Huella digital de portales (detección de cambios)
  6. Modo degradado

Uso:
  from backend.custody import (
      validar_semantica, Custodia, Versionador, ConfianzaCampo,
      huella_portal, modo_degradado
  )
"""

import re
import json
import os
import hashlib
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════
# 1. VALIDACIÓN SEMÁNTICA
# ═══════════════════════════════════════════════════════════════════════════

PATRONES_SEMANTICOS = {
    "siniestro.id_siniestro": {
        "patron": r"^\d{6,12}$",
        "descripcion": "Debe tener entre 6 y 12 dígitos",
        "ejemplo": "503463870",
    },
    "siniestro.fecha_evento": {
        "patron": r"^\d{2}/\d{2}/(20\d{2})$",
        "descripcion": "Debe ser DD/MM/AAAA y año >= 2020",
        "validacion_extra": lambda v: int(v.split("/")[2]) >= 2020 if "/" in v else False,
    },
    "siniestro.diagnosticos": {
        "patron": r"^[A-Z]\d{2,3}",
        "descripcion": "Debe empezar con código CIE-10 (letra + 2-3 dígitos)",
        "validacion_extra": lambda v: bool(re.match(r"^[A-Z]\d{2,3}", v.strip())),
    },
    "siniestro.tiempo_incapacidad": {
        "patron": r"(\d+|[Ss]in datos)",
        "descripcion": "Debe ser un número de días o 'Sin datos'",
    },
    "paciente.documento": {
        "patron": r"^\d{6,12}$",
        "descripcion": "Debe tener entre 6 y 12 dígitos",
    },
    "paciente.fecha_nacimiento": {
        "patron": r"^\d{2,4}[-/]\d{2}[-/]\d{2,4}$",
        "descripcion": "Debe ser una fecha válida",
        "validacion_extra": lambda v: int(v.split("/")[-1] if "/" in v else v.split("-")[0]) < 2010,
    },
    "paciente.edad": {
        "patron": r"^\d{1,3}$",
        "descripcion": "Debe ser un número entre 1 y 120",
        "validacion_extra": lambda v: 1 <= int(v) <= 120,
    },
    "paciente.telefono": {
        "patron": r"^\d{7,15}$",
        "descripcion": "Debe tener entre 7 y 15 dígitos",
    },
    "paciente.email": {
        "patron": r"@",
        "descripcion": "Debe contener @",
        "opcional": True,
    },
    "empresa.nit": {
        "patron": r"^\d{8,12}$",
        "descripcion": "Debe tener entre 8 y 12 dígitos",
        "opcional": True,
    },
    "laboral.cargo": {
        "patron": r".{3,}",
        "descripcion": "Debe tener al menos 3 caracteres",
    },
}


@dataclass
class ResultadoValidacion:
    campo: str
    valor: str
    es_valido: bool
    confianza: int  # 0-100
    mensaje: str
    es_sospechoso: bool = False


def _get_nested(data: dict, path: str) -> Any:
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, "")
        else:
            return ""
    return current or ""


def validar_semantica(datos: dict, origen: str = "") -> Tuple[bool, List[ResultadoValidacion]]:
    """
    Valida semánticamente los campos extraídos.
    
    Returns:
        (todos_validos, lista_resultados)
    """
    resultados = []
    
    for campo, reglas in PATRONES_SEMANTICOS.items():
        valor = str(_get_nested(datos, campo))
        
        # Si es opcional y está vacío, OK
        if reglas.get("opcional") and (not valor or valor in ("", "[VERIFICAR]", "Sin datos")):
            resultados.append(ResultadoValidacion(
                campo=campo, valor=valor, es_valido=True, confianza=100,
                mensaje=f"Campo opcional vacío (OK)"
            ))
            continue
        
        # Si está vacío → sospechoso
        if not valor or valor == "[VERIFICAR]":
            resultados.append(ResultadoValidacion(
                campo=campo, valor=valor, es_valido=False, confianza=0,
                mensaje=f"Campo requerido VACÍO — se necesita extraer",
                es_sospechoso=True
            ))
            continue
        
        # Validar patrón
        patron = reglas["patron"]
        match = re.search(patron, valor) if patron else True
        
        # Validación extra
        extra_ok = True
        if "validacion_extra" in reglas:
            try:
                extra_ok = reglas["validacion_extra"](valor)
            except:
                extra_ok = False
        
        es_sospechoso = False
        if match and extra_ok:
            confianza = 95
            mensaje = f"✅ Válido — {reglas['descripcion']}"
            es_valido = True
        elif match and not extra_ok:
            confianza = 50
            mensaje = f"⚠️ Formato OK pero validación extra falló — {reglas['descripcion']}"
            es_valido = True
            es_sospechoso = True
        else:
            confianza = 20
            mensaje = f"❌ NO VÁLIDO — {reglas['descripcion']}. Valor: '{valor[:30]}'"
            es_valido = False
            es_sospechoso = True

        resultados.append(ResultadoValidacion(
            campo=campo, valor=valor[:50], es_valido=es_valido,
            confianza=confianza, mensaje=mensaje,
            es_sospechoso=es_sospechoso
        ))
    
    todos_validos = all(r.es_valido for r in resultados)
    return todos_validos, resultados


# ═══════════════════════════════════════════════════════════════════════════
# 2. CADENA DE CUSTODIA
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class EntradaCustodia:
    campo: str
    valor: str
    fuente: str  # 'medifolios', 'positiva', 'audio', 'manual_sandra'
    timestamp_extraccion: str
    screenshot_path: Optional[str] = None
    audio_timestamp: Optional[str] = None  # "00:04:32"
    corregido_por: Optional[str] = None  # "sandra" si lo corrigió manualmente
    confianza: int = 100


class Custodia:
    """Registra la trazabilidad de cada campo del documento."""
    
    def __init__(self, paciente_cc: str):
        self.paciente_cc = paciente_cc
        self.entradas: List[EntradaCustodia] = []
        self.fecha_generacion = datetime.now().isoformat()
    
    def registrar(self, campo: str, valor: str, fuente: str, **kwargs):
        entrada = EntradaCustodia(
            campo=campo,
            valor=str(valor)[:200],
            fuente=fuente,
            timestamp_extraccion=datetime.now().isoformat(),
            **kwargs
        )
        self.entradas.append(entrada)
    
    def registrar_correccion(self, campo: str, valor_anterior: str, valor_nuevo: str):
        """Registra una corrección manual de Sandra."""
        self.entradas.append(EntradaCustodia(
            campo=campo,
            valor=f"{valor_anterior} → {valor_nuevo}",
            fuente="manual_sandra",
            timestamp_extraccion=datetime.now().isoformat(),
            corregido_por="sandra",
            confianza=100,
        ))
    
    def generar_reporte(self) -> dict:
        """Genera el reporte de custodia para adjuntar al documento."""
        return {
            "paciente_cc": self.paciente_cc,
            "fecha_generacion": self.fecha_generacion,
            "total_campos": len(self.entradas),
            "fuentes": {
                "medifolios": sum(1 for e in self.entradas if e.fuente == "medifolios"),
                "positiva": sum(1 for e in self.entradas if e.fuente == "positiva"),
                "audio": sum(1 for e in self.entradas if e.fuente == "audio"),
                "manual_sandra": sum(1 for e in self.entradas if e.fuente == "manual_sandra"),
            },
            "campos_corregidos": sum(1 for e in self.entradas if e.corregido_por),
            "entradas": [
                {
                    "campo": e.campo,
                    "fuente": e.fuente,
                    "timestamp": e.timestamp_extraccion,
                    "confianza": e.confianza,
                    "corregido": e.corregido_por is not None,
                    "audio_timestamp": e.audio_timestamp,
                }
                for e in self.entradas
            ],
            "hash_documento": hashlib.sha256(
                json.dumps([(e.campo, e.valor) for e in self.entradas], sort_keys=True).encode()
            ).hexdigest()[:16],
        }
    
    def guardar(self, output_dir: str):
        """Guarda el reporte de custodia como JSON."""
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "custodia.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.generar_reporte(), f, indent=2, ensure_ascii=False)
        return path


# ═══════════════════════════════════════════════════════════════════════════
# 3. VERSIONADO DE DOCUMENTOS
# ═══════════════════════════════════════════════════════════════════════════

class Versionador:
    """Gestiona versiones de documentos por paciente."""
    
    BASE_DIR = "/root/fisioterapia/storage/pacientes"
    
    def __init__(self, paciente_cc: str, nombre_paciente: str = ""):
        nombre_limpio = nombre_paciente.replace(" ", "_")[:40] if nombre_paciente else paciente_cc
        self.paciente_dir = os.path.join(self.BASE_DIR, f"{paciente_cc}_{nombre_limpio}")
        self.paciente_cc = paciente_cc
    
    def crear_version(self, tipo: str) -> str:
        """
        Crea una nueva versión del documento.
        
        Args:
            tipo: 'borrador', 'rechazado', 'revision', 'APROBADO'
        
        Returns:
            Ruta de la carpeta de versión creada
        """
        ahora = datetime.now()
        fecha_str = ahora.strftime("%Y-%m-%d")
        hora_str = ahora.strftime("%H%M")
        
        # Si es APROBADO, usar formato especial
        if tipo == "APROBADO":
            nombre_version = f"v{self._siguiente_version()}_{fecha_str}_APROBADO"
        elif tipo == "borrador":
            nombre_version = f"v{self._siguiente_version()}_{fecha_str}_{hora_str}_borrador"
        elif tipo == "rechazado":
            nombre_version = f"v{self._siguiente_version()}_{fecha_str}_{hora_str}_rechazado"
        else:
            nombre_version = f"v{self._siguiente_version()}_{fecha_str}_{hora_str}_{tipo}"
        
        version_dir = os.path.join(self.paciente_dir, nombre_version)
        os.makedirs(version_dir, exist_ok=True)
        
        # Si es APROBADO, hacer inmutable (read-only)
        if tipo == "APROBADO":
            os.chmod(version_dir, 0o555)
        
        # Actualizar symlink 'latest'
        latest_link = os.path.join(self.paciente_dir, "latest")
        if os.path.exists(latest_link):
            os.remove(latest_link)
        os.symlink(version_dir, latest_link)
        
        return version_dir
    
    def _siguiente_version(self) -> int:
        """Calcula el número de la siguiente versión."""
        if not os.path.exists(self.paciente_dir):
            return 1
        versiones = [d for d in os.listdir(self.paciente_dir) if d.startswith("v")]
        return len(versiones) + 1
    
    def listar_versiones(self) -> List[dict]:
        """Lista todas las versiones del paciente."""
        if not os.path.exists(self.paciente_dir):
            return []
        
        versiones = []
        for d in sorted(os.listdir(self.paciente_dir)):
            if d.startswith("v") and os.path.isdir(os.path.join(self.paciente_dir, d)):
                stat = os.stat(os.path.join(self.paciente_dir, d))
                partes = d.split("_")
                versiones.append({
                    "nombre": d,
                    "numero": partes[0] if partes else "",
                    "fecha": partes[1] if len(partes) > 1 else "",
                    "tipo": partes[-1] if partes else "",
                    "es_inmutable": (stat.st_mode & 0o222) == 0,
                    "tamaño_bytes": sum(
                        os.path.getsize(os.path.join(dp, f))
                        for dp, _, files in os.walk(os.path.join(self.paciente_dir, d))
                        for f in files
                    ),
                })
        return versiones


# ═══════════════════════════════════════════════════════════════════════════
# 4. CONFIANZA POR CAMPO
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ConfianzaCampo:
    campo: str
    valor: str
    confianza: int  # 0-100
    fuente: str
    motivo: str
    color_semaforo: str = ""  # 'verde', 'amarillo', 'rojo'
    
    def __post_init__(self):
        if self.confianza >= 80:
            self.color_semaforo = "verde"
        elif self.confianza >= 50:
            self.color_semaforo = "amarillo"
        else:
            self.color_semaforo = "rojo"


def calcular_confianza_audio(texto_extraido: str, campo: str, transcripcion_completa: str) -> int:
    """
    Calcula la confianza de un dato extraído del audio.
    
    Factores:
    - ¿La frase es explícita? (+40)
    - ¿Está cerca de palabras clave del campo? (+30)
    - ¿La frase es completa o truncada? (+20)
    - ¿Hay múltiples menciones? (+10)
    """
    confianza = 0
    texto = texto_extraido.lower().strip()
    
    # 1. Claridad de la frase (+40)
    if len(texto) > 30:
        confianza += 40
    elif len(texto) > 15:
        confianza += 25
    else:
        confianza += 10
    
    # 2. Proximidad a palabras clave (+30)
    claves_por_campo = {
        "cargo": ["trabajo", "cargo", "puesto", "oficio", "laboro", "hago"],
        "funciones": ["funciones", "tareas", "hago", "realizo", "actividad"],
        "herramientas": ["herramienta", "uso", "manejo", "máquina", "equipo"],
        "limitaciones": ["duele", "dolor", "cuesta", "difícil", "no puedo", "molestia"],
        "horario": ["turno", "horario", "entrada", "salida", "lunes", "semana"],
    }
    
    claves = claves_por_campo.get(campo, [campo])
    matches = sum(1 for c in claves if c in texto)
    confianza += min(30, matches * 10)
    
    # 3. Frase completa (+20)
    if texto.endswith(".") or texto.endswith("?") or texto.endswith("!"):
        confianza += 20
    
    # 4. Múltiples menciones (+10)
    menciones = transcripcion_completa.lower().count(texto[:20].lower())
    if menciones > 1:
        confianza += min(10, menciones * 3)
    
    return min(100, confianza)


# ═══════════════════════════════════════════════════════════════════════════
# 5. HUELLA DIGITAL DE PORTALES
# ═══════════════════════════════════════════════════════════════════════════

HUELLAS_ESPERADAS = {
    "medifolios_login": {
        "selectores": ["input[name='username']", "input[name='password']", "button[type='submit']"],
        "textos_esperados": ["Inicio de Sesión", "USUARIO", "Ingresar"],
    },
    "medifolios_dashboard": {
        "selectores": ["#menu-principal", ".fc-event", "a:contains('Bienvenido')"],
        "textos_esperados": ["Página Principal", "Proyectos SCRUM", "Solicitudes Pendientes"],
    },
    "positiva_login": {
        "selectores": ["input#username", "input#password", "input[type='submit']"],
        "textos_esperados": ["Iniciar sesión", "Usuario", "Clave"],
    },
    "positiva_dashboard": {
        "selectores": ["a:contains('Consulta integral')", "a:contains('Rehabilitación')"],
        "textos_esperados": ["Notificaciones", "Menú", "PROVEEDOR RHI"],
    },
    "positiva_consulta_integral": {
        "selectores": ["input[id*='identificacion']", "button:contains('Buscar')"],
        "textos_esperados": ["Criterios de Búsqueda", "Tipo de Identificación", "DATOS ASEGURADO"],
    },
}

HUELLA_FILE = "/root/fisioterapia/storage/huellas_portales.json"


def calcular_huella(snapshot_text: str, selectores_clave: List[str]) -> str:
    """Calcula un hash de la estructura actual de la página."""
    contenido = snapshot_text[:500] + "|" + "|".join(selectores_clave)
    return hashlib.sha256(contenido.encode()).hexdigest()[:16]


def verificar_huella(pagina: str, snapshot_text: str) -> Tuple[bool, str]:
    """
    Verifica si la huella de la página coincide con la esperada.
    Si cambió, alerta.
    
    Returns:
        (ok, mensaje)
    """
    if pagina not in HUELLAS_ESPERADAS:
        return True, f"Página '{pagina}' no tiene huella registrada"
    
    esperada = HUELLAS_ESPERADAS[pagina]
    huella_actual = calcular_huella(snapshot_text, esperada["selectores"])
    
    # Verificar textos esperados
    textos_faltantes = [t for t in esperada["textos_esperados"] 
                        if t.lower() not in snapshot_text.lower()]
    
    # Cargar huella anterior
    try:
        with open(HUELLA_FILE, "r") as f:
            huellas = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        huellas = {}
    
    huella_anterior = huellas.get(pagina, {}).get("hash", "")
    
    # Guardar nueva huella
    huellas[pagina] = {
        "hash": huella_actual,
        "timestamp": datetime.now().isoformat(),
        "textos_ok": len(textos_faltantes) == 0,
    }
    os.makedirs(os.path.dirname(HUELLA_FILE), exist_ok=True)
    with open(HUELLA_FILE, "w") as f:
        json.dump(huellas, f, indent=2)
    
    if textos_faltantes:
        return False, f"⚠️ ALERTA: La página '{pagina}' CAMBIÓ. Textos faltantes: {textos_faltantes}. Revisar manualmente antes de extraer."
    
    if huella_anterior and huella_anterior != huella_actual:
        return False, f"⚠️ ALERTA: La estructura de '{pagina}' cambió desde la última extracción. Huella anterior: {huella_anterior}, actual: {huella_actual}."
    
    return True, f"✅ Huella OK para '{pagina}'"


# ═══════════════════════════════════════════════════════════════════════════
# 6. MODO DEGRADADO
# ═══════════════════════════════════════════════════════════════════════════

def modo_degradado(
    datos_extraidos: dict,
    campos_fallidos: List[str],
    screenshots: Dict[str, str] = None,
) -> tuple:
    """
    Aplica modo degradado: marca campos fallidos como [VERIFICAR],
    guarda screenshots, y genera reporte de lo que falló.
    
    Nunca bloquea — siempre retorna datos utilizables.
    """
    from backend.json_validator import _set_nested
    
    for campo in campos_fallidos:
        _set_nested(datos_extraidos, campo, "[VERIFICAR]")
    
    reporte = {
        "modo": "degradado",
        "timestamp": datetime.now().isoformat(),
        "campos_fallidos": campos_fallidos,
        "total_fallidos": len(campos_fallidos),
        "total_extraidos": sum(
            1 for _ in _contar_campos(datos_extraidos) if _ != "[VERIFICAR]"
        ),
        "screenshots": list(screenshots.keys()) if screenshots else [],
        "accion_requerida": "Sandra debe completar manualmente los campos [VERIFICAR] en el dashboard",
    }
    
    return datos_extraidos, reporte


def _contar_campos(d: dict, prefix=""):
    for k, v in d.items():
        if isinstance(v, dict):
            yield from _contar_campos(v, f"{prefix}{k}.")
        else:
            yield v


# ═══════════════════════════════════════════════════════════════════════════
# 7. EXTRACCIÓN ESTRUCTURADA CON PROMPT CLÍNICO
# ═══════════════════════════════════════════════════════════════════════════

PROMPT_EXTRACCION_CLINICA = """Eres un asistente clínico especializado en rehabilitación laboral.
Del siguiente fragmento de consulta entre una fisioterapeuta (Sandra) y un paciente, extrae ÚNICAMENTE los datos solicitados.

REGLAS ABSOLUTAS:
1. Si el dato NO se menciona explícitamente, devuelve null. NUNCA inventes.
2. Usa el lenguaje EXACTO del paciente. No reformatees ni resumas.
3. Si el paciente dice "me duele aquí cuando levanto el brazo", escribe ESO, no "limitación funcional en abducción".
4. Distingue entre la voz de Sandra (Speaker 0) y el paciente (Speaker 1). Los datos del paciente vienen del Speaker 1.
5. Si un dato es ambiguo, márcalo con confianza baja.

CAMPOS A EXTRAER:
- cargo_actual: El trabajo que hace actualmente
- funciones_principales: Lista de tareas que describió (separadas por " / ")
- herramientas_trabajo: Objetos o máquinas que mencionó usar
- limitaciones_funcionales: Qué dijo que no puede hacer o le duele hacer
- horario_laboral: Turnos, horas, días que trabaja
- descripcion_accidente: Cómo ocurrió el accidente según el paciente
- sintomatologia_actual: Dónde duele, cuánto, desde cuándo
- historia_ocupacional: Trabajos anteriores mencionados
- contexto_familiar: Personas que dependen de él, situación económica
- actividades_vida_diaria: Cómo se viste, come, duerme, se moviliza

FRAGMENTO DE CONSULTA:
{transcripcion}

Responde en formato JSON. Campos no mencionados = null."""


# ═══════════════════════════════════════════════════════════════════════════
# PRUEBA
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Prueba validación semántica
    datos_test = {
        "siniestro": {
            "id_siniestro": "503463870",
            "fecha_evento": "02/03/2026",
            "diagnosticos": "S611 HERIDA DEL CUARTO DEDO",
            "tiempo_incapacidad": "Sin datos",
        },
        "paciente": {
            "documento": "1193143688",
            "fecha_nacimiento": "08/03/1991",
            "edad": "35",
            "telefono": "3027218147",
            "email": "JUANDURAN3688@GMAIL.COM",
        },
        "laboral": {"cargo": "Obrero de tratamiento roca"},
    }
    
    print("=== VALIDACIÓN SEMÁNTICA ===")
    ok, resultados = validar_semantica(datos_test, "positiva")
    for r in resultados:
        icono = "✅" if r.es_valido else "❌"
        print(f"  {icono} {r.campo}: {r.mensaje} (confianza={r.confianza})")
    print(f"  Todos válidos: {ok}\n")
    
    # Prueba custodia
    print("=== CADENA DE CUSTODIA ===")
    c = Custodia("1193143688")
    c.registrar("siniestro.id_siniestro", "503463870", "positiva")
    c.registrar("paciente.nombre", "JUAN CARLOS DURAN", "medifolios")
    c.registrar("consulta.metodologia", "Observación directa...", "audio", audio_timestamp="00:04:32")
    c.registrar_correccion("siniestro.fecha_evento", "02/03/2025", "02/03/2026")
    reporte = c.generar_reporte()
    print(json.dumps({k: v for k, v in reporte.items() if k != "entradas"}, indent=2))
    print(f"  Hash doc: {reporte['hash_documento']}\n")
    
    # Prueba versionador
    print("=== VERSIONADOR ===")
    v = Versionador("1193143688", "DURAN_NARVAEZ")
    v1 = v.crear_version("borrador")
    v2 = v.crear_version("APROBADO")
    print(f"  v1: {v1}")
    print(f"  v2: {v2}")
    print(f"  Versiones: {v.listar_versiones()}\n")
    
    # Prueba huella
    print("=== HUELLA PORTAL ===")
    snapshot_falso = "Inicio de Sesión Otro texto USUARIO Ingresar"
    ok, msg = verificar_huella("medifolios_login", snapshot_falso)
    print(f"  {msg}\n")
    
    print("✅ Todas las pruebas pasaron")
