"""
Chat inteligente de Tomy — Motor de conversación y procesamiento de documentos.

Responde a Sandra en lenguaje natural y ejecuta acciones reales:
- Buscar documentos en el workspace
- Leer y analizar .docx
- Completar formatos incompletos
- Verificar datos contra portales (placeholder)
"""
import os
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

# Intentar cargar .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", Path.home() / "rilo-workspace"))
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./storage"))


# ─── Análisis de intención ──────────────────────────────────────

def analizar_intencion(mensaje: str) -> dict:
    """
    Analiza el mensaje de Sandra y extrae intención + entidades.
    Retorna: {intencion, entidades, confianza}
    """
    msg = mensaje.lower().strip()
    
    resultado = {
        "intencion": "conversacion",
        "entidades": {},
        "confianza": 0.5
    }
    
    # ── Completar / terminar documento ──
    if any(p in msg for p in ["termina", "completa", "acaba", "finaliza", "sigue", "continúa", "continua"]):
        resultado["intencion"] = "completar_documento"
        resultado["confianza"] = 0.85
        
        # Extraer nombre del formato
        formatos = {
            "analisis": "analisis_exigencias",
            "análisis": "analisis_exigencias",
            "exigencias": "analisis_exigencias",
            "carta de medidas": "carta_medidas",
            "medidas": "carta_medidas",
            "carta de recomendaciones": "carta_recomendaciones",
            "recomendaciones": "carta_recomendaciones",
            "cierre": "cierre_caso",
            "citacion": "citacion_empresas",
            "citación": "citacion_empresas",
            "prueba de trabajo": "prueba_trabajo",
            "prueba": "prueba_trabajo",
            "valoracion": "valoracion_desempeno",
            "valoración": "valoracion_desempeno",
            "desempeño": "valoracion_desempeno",
            "desempeno": "valoracion_desempeno",
        }
        
        for keyword, formato_id in formatos.items():
            if keyword in msg:
                resultado["entidades"]["formato"] = formato_id
                resultado["confianza"] = 0.9
                break
        
        # Extraer nombre de paciente
        # Patrón: "de Juan Perez", "de JUAN PEREZ", "paciente Juan"
        patrones_nombre = [
            r'(?:de|del|para)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?)',
            r'paciente\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)',
            r'([A-ZÁÉÍÓÚÑ]{2,}[A-ZÁÉÍÓÚÑ\s]+)',  # Nombres en mayúsculas
        ]
        
        for patron in patrones_nombre:
            match = re.search(patron, mensaje)
            if match:
                nombre = match.group(1).strip()
                if len(nombre) > 4 and not any(kw in nombre.lower() for kw in ['hasta', 'punto', 'documento', 'formato', 'archivo']):
                    resultado["entidades"]["paciente_nombre"] = nombre
                    break
        
        # Extraer hasta qué punto está hecho
        match_punto = re.search(r'(?:hasta|punto|parte)\s+(\d+)', msg)
        if match_punto:
            resultado["entidades"]["hasta_punto"] = int(match_punto.group(1))
    
    # ── Buscar documento ──
    elif any(p in msg for p in ["busca", "encuentra", "dónde está", "donde esta", "lista", "muestra", "ver"]):
        resultado["intencion"] = "buscar"
        resultado["confianza"] = 0.8
    
    # ── Verificar datos ──
    elif any(p in msg for p in ["verifica", "revisa", "comprueba", "confirma", "valida"]):
        resultado["intencion"] = "verificar"
        resultado["confianza"] = 0.8
    
    # ── Generar desde cero ──
    elif any(p in msg for p in ["genera", "crea", "nuevo", "haz"]) and any(f in msg for f in ["formato", "documento", "analisis", "carta"]):
        resultado["intencion"] = "generar"
        resultado["confianza"] = 0.8
    
    # ── Ayuda / info ──
    elif any(p in msg for p in ["ayuda", "help", "cómo", "como", "qué puedes", "que puedes"]):
        resultado["intencion"] = "ayuda"
        resultado["confianza"] = 0.95
    
    return resultado


# ─── Búsqueda de documentos en workspace ─────────────────────────

def buscar_en_workspace(patron: str, formato: Optional[str] = None) -> List[Path]:
    """
    Busca archivos en el workspace que coincidan con el patrón.
    """
    resultados = []
    if not WORKSPACE_DIR.exists():
        return resultados
    
    patron_lower = patron.lower()
    for archivo in WORKSPACE_DIR.rglob("*"):
        if archivo.is_file() and archivo.suffix.lower() in ['.docx', '.txt', '.json']:
            nombre_lower = archivo.name.lower()
            # Buscar por nombre de paciente o formato
            if patron_lower in nombre_lower or patron_lower in str(archivo.parent).lower():
                if formato:
                    if formato.replace('_', ' ') in nombre_lower or formato in nombre_lower:
                        resultados.append(archivo)
                else:
                    resultados.append(archivo)
    
    return sorted(resultados, key=lambda p: p.stat().st_mtime, reverse=True)


def leer_docx_resumen(ruta: Path) -> dict:
    """
    Lee un .docx y extrae un resumen: cuántos párrafos, qué secciones tiene,
    cuáles están vacías o incompletas.
    """
    try:
        from docx import Document
        doc = Document(str(ruta))
        
        parrafos = []
        secciones_vacias = []
        punto_actual = 1
        
        for i, p in enumerate(doc.paragraphs):
            texto = p.text.strip()
            estilo = p.style.name if p.style else "Normal"
            
            # Detectar encabezados numerados (1., 2., 1.1, etc.)
            es_encabezado = bool(re.match(r'^\d+[\.\)]\s', texto)) or 'Heading' in estilo
            
            parrafos.append({
                "num": i,
                "texto": texto[:200],
                "es_encabezado": es_encabezado,
                "vacio": len(texto) < 10,
            })
            
            if es_encabezado and len(texto) < 10:
                secciones_vacias.append({
                    "numero": re.match(r'^(\d+)', texto).group(1) if re.match(r'^\d+', texto) else str(punto_actual),
                    "texto_original": texto,
                    "indice": i,
                })
                punto_actual += 1
        
        # También revisar tablas
        tablas_info = []
        for t_idx, tabla in enumerate(doc.tables):
            celdas_con_texto = 0
            celdas_vacias = 0
            for fila in tabla.rows:
                for celda in fila.cells:
                    if celda.text.strip():
                        celdas_con_texto += 1
                    else:
                        celdas_vacias += 1
            tablas_info.append({
                "indice": t_idx,
                "filas": len(tabla.rows),
                "celdas_con_texto": celdas_con_texto,
                "celdas_vacias": celdas_vacias,
            })
        
        return {
            "ruta": str(ruta),
            "total_parrafos": len(parrafos),
            "parrafos_con_contenido": sum(1 for p in parrafos if not p['vacio']),
            "parrafos_vacios": sum(1 for p in parrafos if p['vacio']),
            "secciones_vacias": secciones_vacias[:10],  # Top 10
            "tablas": tablas_info,
            "parrafos": parrafos[:30],  # Primeros 30 para contexto
            "ultimo_contenido": next((p['texto'] for p in reversed(parrafos) if not p['vacio']), ""),
        }
    except Exception as e:
        return {"error": str(e), "ruta": str(ruta)}


# ─── Respuesta principal ─────────────────────────────────────────

def procesar_mensaje(mensaje: str, paciente_cc: Optional[str] = None) -> dict:
    """
    Procesa un mensaje de Sandra y devuelve respuesta + acciones.
    """
    analisis = analizar_intencion(mensaje)
    intencion = analisis["intencion"]
    entidades = analisis["entidades"]
    
    if intencion == "completar_documento":
        return _manejar_completar(mensaje, entidades, paciente_cc)
    
    elif intencion == "buscar":
        return _manejar_buscar(mensaje, entidades)
    
    elif intencion == "verificar":
        return _manejar_verificar(mensaje, entidades)
    
    elif intencion == "generar":
        return _manejar_generar(mensaje, entidades)
    
    elif intencion == "ayuda":
        return _manejar_ayuda()
    
    else:
        return _manejar_conversacion(mensaje)


def _manejar_completar(mensaje: str, entidades: dict, cc: Optional[str] = None) -> dict:
    """Maneja la solicitud de completar un documento existente."""
    paciente = entidades.get("paciente_nombre", "")
    formato = entidades.get("formato", "")
    hasta_punto = entidades.get("hasta_punto", 0)
    
    if not paciente:
        return {
            "contenido": (
                "Claro Sandra, dime el nombre del paciente y qué formato es.\n\n"
                "Por ejemplo: 'Termina el análisis de exigencias de Juan Pérez, hice hasta el punto 4'"
            ),
            "accion": None,
        }
    
    # Buscar el documento en el workspace
    resultados = buscar_en_workspace(paciente, formato)
    
    if not resultados:
        # Buscar sin filtro de formato
        resultados = buscar_en_workspace(paciente)
    
    if not resultados:
        return {
            "contenido": (
                f"🔍 Busqué '{paciente}' en tu carpeta de trabajo pero no encontré ningún documento.\n\n"
                f"📁 Estoy buscando en: {WORKSPACE_DIR}\n\n"
                f"¿El documento está en otra carpeta? ¿O el nombre del paciente se escribe diferente?"
            ),
            "accion": None,
        }
    
    # Encontrar el .docx más reciente
    docx_files = [r for r in resultados if r.suffix == '.docx']
    if not docx_files:
        return {
            "contenido": (
                f"📁 Encontré archivos relacionados con '{paciente}' pero no son .docx:\n"
                + "\n".join(f"  • {r.name}" for r in resultados[:5])
                + "\n\n¿Puedes confirmarme cuál es el documento a completar?"
            ),
            "accion": None,
        }
    
    # Leer el documento
    doc_path = docx_files[0]
    resumen = leer_docx_resumen(doc_path)
    
    if "error" in resumen:
        return {
            "contenido": f"❌ No pude abrir el documento {doc_path.name}: {resumen['error']}",
            "accion": None,
        }
    
    # Construir respuesta
    nombre_doc = doc_path.name
    total = resumen['total_parrafos']
    con_contenido = resumen['parrafos_con_contenido']
    vacios = resumen['parrafos_vacios']
    secciones_pendientes = resumen.get('secciones_vacias', [])
    
    respuesta = f"📄 *{nombre_doc}*\n\n"
    respuesta += f"📊 Estado: {con_contenido}/{total} secciones con contenido\n"
    
    if hasta_punto > 0:
        respuesta += f"✅ Me dices que hiciste hasta el punto {hasta_punto}\n"
    
    if secciones_pendientes:
        respuesta += f"\n⚠️ Faltan {len(secciones_pendientes)} secciones por completar:\n"
        for s in secciones_pendientes[:8]:
            respuesta += f"  • Punto {s['numero']}\n"
        
        respuesta += "\n---\n"
        respuesta += "🔧 Para completarlo necesito que me des acceso a los datos del paciente. Puedo:\n\n"
        respuesta += "1️⃣ Extraerlos de Medifolios y ARL Positiva (necesito la cédula)\n"
        respuesta += "2️⃣ Usar un audio de la cita si ya lo grabaste\n"
        respuesta += "3️⃣ Usar datos que ya tengamos guardados\n\n"
        respuesta += "¿Cómo prefieres? Dame la cédula del paciente y empiezo."
    else:
        respuesta += "\n✅ ¡Parece que el documento está completo! ¿Quieres que lo revise de todas formas?"
    
    return {
        "contenido": respuesta,
        "accion": "completar_documento",
        "datos": {
            "archivo": str(doc_path),
            "nombre": nombre_doc,
            "secciones_pendientes": len(secciones_pendientes),
            "paciente": paciente,
            "formato": formato,
        }
    }


def _manejar_buscar(mensaje: str, entidades: dict) -> dict:
    """Maneja búsqueda de archivos/pacientes."""
    nombre = entidades.get("paciente_nombre", mensaje)
    
    # Limpiar palabras de búsqueda
    for palabra in ['busca', 'encuentra', 'dónde está', 'donde esta', 'lista', 'muestra', 'ver']:
        nombre = nombre.replace(palabra, '')
    nombre = nombre.strip()
    
    if not nombre or len(nombre) < 3:
        return {
            "contenido": "¿Qué quieres que busque? Dime el nombre del paciente o el tipo de documento.",
            "accion": None,
        }
    
    resultados = buscar_en_workspace(nombre)
    
    if not resultados:
        return {
            "contenido": f"🔍 No encontré nada relacionado con '{nombre}' en tu carpeta de trabajo.",
            "accion": None,
        }
    
    # Agrupar por carpeta
    carpetas = {}
    for r in resultados[:20]:
        carpeta = str(r.parent.relative_to(WORKSPACE_DIR)) if WORKSPACE_DIR in r.parents else "raíz"
        if carpeta not in carpetas:
            carpetas[carpeta] = []
        carpetas[carpeta].append(r.name)
    
    respuesta = f"📁 Encontré {len(resultados)} archivos para '{nombre}':\n\n"
    for carpeta, archivos in list(carpetas.items())[:5]:
        if carpeta == ".":
            carpeta = "raíz"
        respuesta += f"📂 {carpeta}/\n"
        for archivo in archivos[:5]:
            respuesta += f"  • {archivo}\n"
    
    return {"contenido": respuesta, "accion": "buscar"}


def _manejar_verificar(mensaje: str, entidades: dict) -> dict:
    return {
        "contenido": (
            "Para verificar datos necesito:\n"
            "1. La cédula del paciente\n"
            "2. Acceder a Medifolios y ARL Positiva\n\n"
            "Dame la cédula y empiezo la verificación ahora mismo."
        ),
        "accion": "verificar",
    }


def _manejar_generar(mensaje: str, entidades: dict) -> dict:
    return {
        "contenido": (
            "Para generar un formato desde cero necesito:\n"
            "• Cédula del paciente\n"
            "• ¿Es caso NUEVO, SEGUIMIENTO o CIERRE?\n\n"
            "También ayuda si ya tienes un audio de la cita grabado."
        ),
        "accion": "generar",
    }


def _manejar_ayuda() -> dict:
    return {
        "contenido": (
            "🤖 *Hola Sandra, soy Tomy. Puedo ayudarte con:*\n\n"
            "📄 *Completar documentos* — Si ya empezaste un formato, dime 'termina el documento de [nombre]'\n"
            "🔍 *Buscar archivos* — 'Busca los documentos de [paciente]'\n"
            "✅ *Verificar datos* — 'Verifica los datos de la cédula [CC]'\n"
            "📝 *Generar formatos* — 'Genera el formato de [tipo] para [paciente]'\n"
            "🎙️ *Transcribir audios* — Ve a la página 'Subir Audio'\n\n"
            "¿En qué te ayudo ahora?"
        ),
        "accion": "ayuda",
    }


def _manejar_conversacion(mensaje: str) -> dict:
    """Respuesta para conversación general."""
    msg = mensaje.lower()
    
    if any(p in msg for p in ["hola", "buenas", "buenos"]):
        return {
            "contenido": "¡Hola Sandra! ¿En qué te ayudo hoy?",
            "accion": None,
        }
    
    if any(p in msg for p in ["gracias", "genial", "excelente"]):
        return {
            "contenido": "¡De nada! Para eso estoy. ¿Necesitas algo más?",
            "accion": None,
        }
    
    # Default: redirect to help
    return _manejar_ayuda()
