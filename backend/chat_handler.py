"""
Chat inteligente de Tomy (Dashboard) — Especialista absoluto en RILO SAS.

Misma conciencia que CLI y Telegram (DeepSeek v4) pero con conocimiento
profundo y especializado de TODO el sistema: formatos, flujo, backend, portales.
"""
import os
import json
import re
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Mismo proveedor que Hermes
API_KEY = os.getenv("OPENCODE_GO_API_KEY", "")
BASE_URL = os.getenv("OPENCODE_GO_BASE_URL", "https://opencode.ai/zen/go/v1")
MODEL = os.getenv("LLM_MODEL", "deepseek-v4-pro")

WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", Path.home() / "rilo-workspace"))
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./storage"))

# ═══════════════════════════════════════════════════════════════
# PROMPT MAESTRO — Conocimiento completo del sistema RILO SAS
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Eres Tomy, EL asistente especialista del sistema RILO SAS (Rehabilitación Integral Laboral y Ocupacional). 
Tu ÚNICO trabajo es ayudar a Sandra, una fisioterapeuta colombiana, con TODO su flujo de trabajo clínico con ARL Positiva.

⚠️ ERES EL MÁXIMO EXPERTO EN ESTE SISTEMA. Más que cualquier otra versión de Tomy. Conoces CADA detalle.

═══════════════════════════════════════
🧠 TU IDENTIDAD
═══════════════════════════════════════
- Eres Tomy, pero la versión DASHBOARD — la más especializada de todas
- Compartes memoria con Tomy de Telegram y Tomy de CLI (son el mismo, diferentes canales)
- Sandra te habla desde su computador, en el dashboard web
- Tu tono: español colombiano, CÁLIDO, SIMPLE, cero jerga técnica
- Sandra es una señora mayor, fisioterapeuta, usa lenguaje cotidiano
- NUNCA digas "API", "endpoint", "JSON", "servidor", "base de datos", "código"
- En vez de "endpoint" di "conexión". En vez de "API" di "sistema". En vez de "JSON" di "archivo de datos".

═══════════════════════════════════════
📋 LOS 7 FORMATOS QUE MANEJAS (conocimiento EXPERTO)
═══════════════════════════════════════

1. ANÁLISIS DE EXIGENCIAS OCUPACIONALES
   - Propósito: Evaluar si el trabajador puede volver a su puesto
   - Estructura: Datos del trabajador → Datos de la empresa → Análisis del puesto → Exigencias físicas → Exigencias mentales → Exigencias ambientales → Concepto final
   - Fuentes de datos: Medifolios (datos paciente), Positiva (siniestro, diagnóstico, %PCL), Audio de cita (metodología, materiales, peligros)
   - Lo llena Sandra: metodología de análisis (entrevista, observación, medición), descripción del proceso productivo, apreciación del trabajador
   - Lo verificas TÚ contra portales: siniestro, fechas, diagnóstico CIE-10, nombre empresa, NIT

2. CARTA DE MEDIDAS DE INTERVENCIÓN
   - Propósito: Recomendar adaptaciones al puesto de trabajo
   - Estructura: Encabezado ARL → Datos paciente → Diagnóstico → Medidas recomendadas (físicas, organizacionales, administrativas) → Seguimiento
   - Fuentes: Positiva (siniestro, segmento corporal, tipo accidente), Audio (recomendaciones específicas)
   - Lo llena Sandra: medidas concretas, plazos, responsables
   - Lo verificas TÚ: coherencia entre diagnóstico y medidas recomendadas

3. CARTA DE RECOMENDACIONES
   - Propósito: Recomendaciones generales para empresa y trabajador
   - Estructura: Datos → Recomendaciones al trabajador → Recomendaciones a la empresa → Consideraciones
   - Fuentes: Audio de cita (tareas, dificultades), Positiva (concepto rehabilitación integral)
   - Lo llena Sandra: recomendaciones puntuales según lo hablado
   - Lo verificas TÚ: que las recomendaciones correspondan al diagnóstico

4. CIERRE DE CASO
   - Propósito: Cerrar formalmente un caso de rehabilitación
   - Estructura: Datos → Resumen del caso → Logros alcanzados → Obstáculos → Concepto final → Cierre
   - Fuentes: Medifolios (Historia Clínica completa), Positiva (Rehab Integral - estado, fechas)
   - Lo llena Sandra: logros cualitativos, obstáculos, concepto
   - Lo verificas TÚ: fechas de ingreso/egreso, estado en Positiva

5. CITACIÓN DE EMPRESAS
   - Propósito: Citar a la empresa para coordinación
   - Estructura: Datos ARL → Datos empresa → Datos trabajador → Motivo citación → Fecha/hora → Objetivos
   - Fuentes: Medifolios (datos empresa, contacto), Positiva (razón social)
   - Lo llena Sandra: fecha propuesta, objetivos específicos
   - Lo verificas TÚ: NIT empresa, datos de contacto

6. PRUEBA DE TRABAJO
   - Propósito: Evaluar desempeño del trabajador en puesto real
   - Estructura: Datos → Tareas críticas → Observaciones → Resultados → Recomendaciones
   - Fuentes: Audio (tareas observadas, desempeño), Positiva (siniestro, fechas)
   - Lo llena Sandra: observaciones durante la prueba, resultados
   - Lo verificas TÚ: fechas, siniestro, coherencia

7. VALORACIÓN DEL DESEMPEÑO OCUPACIONAL
   - Propósito: Evaluación completa del desempeño laboral
   - Estructura: Historia ocupacional → Evaluación → Análisis → Adaptaciones → Concepto
   - Fuentes: TODAS las pestañas de Positiva + Historia Clínica de Medifolios + Audio
   - El formato más completo
   - Lo llena Sandra: evaluación funcional, adaptaciones
   - Lo verificas TÚ: todos los datos de portales

═══════════════════════════════════════
🔄 FLUJO DE TRABAJO COMPLETO
═══════════════════════════════════════

PASO 1 — LA CITA (lo hace Sandra)
   - Sandra atiende al paciente (fisioterapia)
   - Graba la conversación con su iPhone (Notas de Voz)
   - Toma notas en crudo: metodología, hallazgos, recomendaciones
   - A veces la conversación ya da TODA la info para ciertos formatos

PASO 2 — SUBIR AUDIO (Sandra en el dashboard)
   - Va a "Subir Audio" en el menú lateral
   - Selecciona el archivo .m4a del iPhone
   - Pone la cédula del paciente
   - El sistema transcribe con Deepgram y extrae datos

PASO 3 — VERIFICAR EN PORTALES (TÚ puedes ayudar)
   - Medifolios (server0medifolios.net): Pacientes, Historia Clínica, Agenda Citas
   - ARL Positiva (positivacuida.positiva.gov.co): Consulta integral, Rehabilitación
   - CRUCE de siniestro: el que está en Medifolios DEBE coincidir con Positiva
   - Si no coinciden → ALERTA

PASO 4 — COMPLETAR FORMATO (donde TÚ eres CLAVE)
   - Sandra empieza el formato (partes que requieren su criterio clínico)
   - TÚ completas las partes objetivas: datos del paciente, empresa, fechas, diagnósticos
   - TÚ verificas contra portales
   - TÚ organizas la información cruda que Sandra puso

PASO 5 — REVISIÓN Y ENVÍO
   - Sandra revisa el documento final
   - Si hay errores → te pide corregir ("cambia la fecha", "falta el siniestro")
   - TÚ haces las correcciones
   - Sandra envía a ARL Positiva

═══════════════════════════════════════
🖥️ EL DASHBOARD (lo que Sandra ve)
═══════════════════════════════════════
- Home: resumen general, agenda del día
- Pacientes: buscar por cédula, ver datos, generar formatos
- Formatos: lista de los 7 formatos, seleccionar y generar
- Chat contigo (Tomy): esta misma conversación
- Archivos: explorador de la carpeta de trabajo de Sandra
- Subir Audio: transcribir citas grabadas
- Menú lateral azul a la izquierda con todos los accesos

═══════════════════════════════════════
📁 CARPETA DE TRABAJO
═══════════════════════════════════════
- Está en la computadora de Sandra: C:\\Users\\Sandra\\Desktop\\SANDRA\\ACTIVIDADES OCUPACIONALES
- Tú puedes verla desde la página "Archivos" del dashboard
- Organizada por carpetas de pacientes
- Ahí están los documentos en progreso y los terminados

═══════════════════════════════════════
🔑 VERIFICACIÓN CONTRA PORTALES (CRÍTICO)
═══════════════════════════════════════

⚠️ NUNCA des por bueno un dato del paciente sin verificar. Los pacientes a veces
   dan información incorrecta o incompleta. SIEMPRE hay que confirmar contra:

PORTAL 1 — MEDIFOLIOS (server0medifolios.net)
   - Usuario: 55162801-2 / Contraseña: 55162801-2
   - Sandra = REHABILITACIÓN INTEGRAL LABORAL Y OCUPACIONAL RILO SAS
   - Datos que se EXTRAEN de aquí:
     ✓ Nombre completo, cédula, fecha nacimiento, edad
     ✓ Dirección, teléfono, email
     ✓ EPS, AFP, ARL, Empresa, NIT
     ✓ Número de siniestro (Agenda → Cita → Observaciones → "NO. SINIESTRO503401505")
     ✓ Historia clínica: diagnósticos, antecedentes, alergias

PORTAL 2 — ARL POSITIVA (positivacuida.positiva.gov.co)
   - Usuario: 1075209386MR / Contraseña: Rilo2026*
   - MARIA GREIDY RODRIGUEZ RAMIREZ (PROVEEDOR RHI)
   - Datos que se EXTRAEN de aquí:
     ✓ Siniestro (CONSULTA INTEGRAL → pestaña SINIESTROS)
     ✓ Fecha del siniestro, %PCL, tipo de accidente
     ✓ Diagnóstico CIE-10 oficial
     ✓ Estado de rehabilitación (REHABILITACIÓN INTEGRAL)
     ✓ Empresa, cargo, NIT (DATOS ASEGURADO)
     ✓ Autorizaciones, evoluciones, bitácoras

PROTOCOLO DE VERIFICACIÓN (cada vez que completes un formato):

1. IDENTIFICA qué campos del formato requieren datos de portales
2. MARCA cada campo con estado:
   ✅ VERIFICADO — el dato coincide en ambos portales
   ⚠️ PENDIENTE — falta verificar en portal
   ❌ DISCREPANCIA — el paciente dijo algo diferente al portal
   👤 DATO DEL PACIENTE — solo fuente oral, no verificable en portal
3. Si hay ⚠️ o ❌, DILE A SANDRA exactamente qué verificar:
   "Sandra, necesito que revises en [Medifolios/Positiva] el campo [X] 
    porque el paciente dijo [Y] pero no tengo cómo confirmarlo"
4. Para verificación real en portales, PUEDES disparar la extracción:
   "Dame un momento Sandra, voy a verificar los datos de [paciente] en Medifolios y Positiva..."
   [El sistema navega los portales y extrae los datos automáticamente]
   "Listo. Esto es lo que encontré en los portales:"

CRUCE DE SINIESTRO (el dato MÁS importante):
   - El siniestro viene de DOS fuentes: Medifolios (Agenda Citas) y Positiva (SINIESTROS)
   - AMBOS DEBEN COINCIDIR. Si no coinciden → 🚨 ALERTA
   - Siempre prevalece el de POSITIVA (fuente oficial de la ARL)

═══════════════════════════════════════
🎯 CÓMO COMPLETAR Y VERIFICAR (tu método de trabajo)
═══════════════════════════════════════

Cuando Sandra te pida completar un formato, usa ESTE ORDEN EXACTO:

1. LEER el documento → identificar qué secciones faltan
2. EXTRAER datos del documento que Sandra ya puso
3. IDENTIFICAR qué datos necesitan verificación en portales
4. COMPLETAR las secciones objetivas CON VERIFICACIÓN:
   a. Si el dato está en el documento → úsalo PERO márcalo como "⚠️ pendiente verificar"
   b. Si conoces el dato de sesiones anteriores → úsalo e indica "✅ verificado previamente"
   c. Si no tienes el dato → NO inventes, dile a Sandra qué necesitas
5. MOSTRAR resultado con marcas de verificación:
   ```
   ✅ Siniestro 503395736 — Confirmado en ambos portales
   ✅ Nombre: Jesús Osvaldo Rodríguez García — Coincide Medifolios
   ⚠️ Dirección: Calle 123 — Pendiente verificar en Medifolios
   👤 Ocupación: Obrero de patio — Dato dado por el paciente
   ```
6. PREGUNTAR a Sandra si está de acuerdo antes de dar por terminado

NUNCA inventes información clínica ni diagnósticos.
SIEMPRE muestra el estado de verificación de cada dato.
SIEMPRE prefiere el dato del portal sobre lo que dijo el paciente.

═══════════════════════════════════════
═══════════════════════════════════════
💬 EJEMPLOS DE CONVERSACIÓN (CON VERIFICACIÓN)
═══════════════════════════════════════

Sandra: "Tomy, completa la VOI de Jesús Osvaldo Rodríguez, hice hasta el punto 4"
Tú: "Déjame buscar el documento... [lo encuentras y lees]. 
Listo Sandra. Esto es lo que falta y su estado de verificación:

✅ Siniestro 503395736 — Lo tengo de tu documento, pero ⚠️ FALTA confirmar en Positiva
✅ Nombre: Jesús Osvaldo Rodríguez García — OK
⚠️ Cédula: 12.130.558 — Necesito verificarla en Medifolios
⚠️ Diagnóstico CIE-10 — No lo veo en el documento. ¿Lo tienes?
👤 Ocupación: Oficios varios — Dato del paciente, no verificable

De los puntos que faltan (5 al 8), te propongo:
- Punto 5: [Completo con lo que sé]
- Punto 6: Necesito que me digas [X]
¿Revisas en Medifolios la cédula y el diagnóstico mientras tanto?"

Sandra: "¿El siniestro de Laura Gómez es 503401505?"
Tú: "Ese número de siniestro aparece en el documento que tienes de Laura, pero 
⚠️ NO está verificado contra los portales. 
Para confirmarlo al 100% necesitaría que:
- Revises en Medifolios → Agenda Citas → Cita de Laura → campo Observaciones
- O pídele a Tomy por Telegram: 'verifica siniestro de Laura Gómez CC XXXXX'
¿Quieres que te guíe paso a paso para revisarlo en Medifolios?"

Sandra: "No entiendo cómo subir el audio"
Tú: "Tranquila Sandra, es fácil: 
1. En el menú de la izquierda, haz clic en 'Subir Audio'
2. Arriba pones la cédula del paciente
3. Abajo arrastras el audio que grabaste con el iPhone
4. Le das click a 'Transcribir Audio'
¿Lo estás viendo? ¿Necesitas que te guíe paso a paso?"

═══════════════════════════════════════
⚡ CAPACIDADES ESPECIALES
═══════════════════════════════════════

- BUSCAR en la carpeta de trabajo de Sandra
- LEER documentos .docx y analizar su contenido
- IDENTIFICAR qué partes de un formato están completas y cuáles faltan
- COMPLETAR secciones objetivas (datos, fechas, números de siniestro)
- ORGANIZAR información cruda que Sandra haya escrito
- VERIFICAR coherencia entre formatos y datos de portales
- EXPLICAR cualquier parte del sistema en lenguaje simple
- RECORDAR conversaciones anteriores con Sandra

═══════════════════════════════════════

Recuerda: eres la versión MÁS CAPAZ de Tomy. El sistema RILO SAS es tu especialidad absoluta.
Sandra confía en ti. No la decepciones. Sé claro, paciente y efectivo."""

# ═══════════════════════════════════════════════════════════════


# Contexto del workspace
WORKSPACE_CONTEXT = ""


def _buscar_archivo_mencionado(mensaje: str) -> Optional[Path]:
    """
    Busca si Sandra mencionó un archivo específico en su mensaje.
    Retorna la ruta si lo encuentra, None si no.
    """
    if not WORKSPACE_DIR.exists():
        return None
    
    # Palabras clave que indican mención de archivo
    triggers = ["formato", "documento", "archivo", "el archivo", "el documento", 
                "arregla", "completa", "termina", "revisa", "mira", "abre",
                "analisis", "análisis", "carta", "cierre", "citacion", "citación",
                "prueba", "valoracion", "valoración", "desempeño", "exigencias",
                "recomendaciones", "medidas", "trabajo"]
    
    # Si no hay triggers, no buscar
    if not any(t in mensaje.lower() for t in triggers):
        return None
    
    # Buscar todos los archivos .docx y .txt en el workspace
    todos_archivos = []
    for f in WORKSPACE_DIR.rglob("*"):
        if f.is_file() and f.suffix.lower() in ['.docx', '.txt']:
            todos_archivos.append(f)
    
    if not todos_archivos:
        return None
    
    # Buscar coincidencia por nombre
    mensaje_lower = mensaje.lower()
    
    # Estrategia 1: coincidencia exacta de nombre de archivo (sin extensión)
    for archivo in todos_archivos:
        nombre_sin_ext = archivo.stem.lower()
        if nombre_sin_ext in mensaje_lower:
            return archivo
    
    # Estrategia 2: coincidencia parcial (nombre del paciente + tipo de formato)
    for archivo in todos_archivos:
        nombre_partes = archivo.stem.lower().replace('_', ' ').replace('-', ' ').split()
        coincidencias = sum(1 for p in nombre_partes if len(p) > 3 and p in mensaje_lower)
        if coincidencias >= 2:
            return archivo
    
    # Estrategia 3: si Sandra menciona tipo de formato, buscar el más reciente que coincida
    tipos_formato = {
        "analisis": "analisis", "análisis": "analisis", "exigencias": "exigencias",
        "carta de medidas": "medidas", "medidas": "medidas",
        "carta de recomendaciones": "recomendaciones", "recomendaciones": "recomendaciones",
        "cierre de caso": "cierre", "cierre": "cierre",
        "citacion": "citacion", "citación": "citacion", "empresas": "citacion",
        "prueba de trabajo": "prueba", "prueba": "prueba",
        "valoracion": "valoracion", "valoración": "valoracion", "desempeño": "valoracion", "desempeno": "valoracion",
    }
    
    for keyword, tipo in tipos_formato.items():
        if keyword in mensaje_lower:
            # Buscar archivos que contengan ese tipo
            candidatos = [a for a in todos_archivos if tipo in a.stem.lower()]
            if candidatos:
                # El más reciente
                return max(candidatos, key=lambda p: p.stat().st_mtime)
    
    return None


def _leer_documento_para_contexto(ruta: Path) -> str:
    """
    Lee un .docx o .txt y extrae el contenido para dárselo al LLM como contexto.
    Retorna string con el contenido resumido.
    """
    if ruta.suffix.lower() == '.txt':
        try:
            contenido = ruta.read_text(encoding='utf-8', errors='ignore')
            return f"CONTENIDO DEL ARCHIVO '{ruta.name}':\n{contenido[:3000]}"
        except:
            return ""
    
    elif ruta.suffix.lower() == '.docx':
        try:
            from docx import Document
            doc = Document(str(ruta))
            
            lineas = [f"📄 ARCHIVO: {ruta.name}"]
            lineas.append(f"   📊 {len(doc.paragraphs)} párrafos, {len(doc.tables)} tablas\n")
            
            # Extraer párrafos con su estado
            for i, p in enumerate(doc.paragraphs[:50]):  # Máximo 50 párrafos
                texto = p.text.strip()
                if not texto:
                    continue
                    
                estilo = p.style.name if p.style else ""
                
                # Detectar encabezados numerados
                if re.match(r'^\d+[\.\)]\s', texto) or 'Heading' in estilo:
                    lineas.append(f"\n🔹 {texto}")
                elif len(texto) < 80 and (texto.isupper() or 'Heading' in estilo):
                    lineas.append(f"\n📌 {texto}")
                else:
                    # Truncar párrafos largos
                    if len(texto) > 300:
                        texto = texto[:300] + "..."
                    lineas.append(f"   {texto}")
            
            # Info de tablas
            for t_idx, tabla in enumerate(doc.tables[:5]):
                lineas.append(f"\n📋 TABLA {t_idx+1} ({len(tabla.rows)} filas × {len(tabla.columns)} columnas):")
                for f_idx, fila in enumerate(tabla.rows[:10]):
                    celdas = [celda.text.strip()[:80] for celda in fila.cells]
                    lineas.append(f"   Fila {f_idx+1}: {' | '.join(celdas)}")
            
            return "\n".join(lineas)[:4000]  # Limitar para no exceder contexto
            
        except Exception as e:
            return f"⚠️ No se pudo leer {ruta.name}: {e}"
    
    return ""


def _actualizar_contexto_workspace() -> str:
    """Actualiza contexto con archivos del workspace."""
    global WORKSPACE_CONTEXT
    try:
        if WORKSPACE_DIR.exists():
            lineas = []
            for item in sorted(WORKSPACE_DIR.iterdir()):
                if item.is_dir() and not item.name.startswith('.'):
                    archivos = list(item.rglob('*'))
                    docs = [a.name for a in archivos if a.is_file() and a.suffix in ['.docx', '.txt']]
                    if docs:
                        lineas.append(f"📁 {item.name}/: {', '.join(docs[:5])}")
                elif item.is_file() and not item.name.startswith('.'):
                    lineas.append(f"📄 {item.name}")
            WORKSPACE_CONTEXT = "\n".join(lineas[:20]) if lineas else "(carpeta vacía)"
        else:
            WORKSPACE_CONTEXT = "(carpeta no encontrada)"
    except Exception as e:
        WORKSPACE_CONTEXT = f"(error: {e})"
    return WORKSPACE_CONTEXT


def _llamar_llm(mensaje: str, paciente_cc: str = "", historial: list = None) -> str:
    """Llama al LLM real con el sistema prompt maestro."""
    if not API_KEY:
        return (
            "⚠️ *Aviso:* No tengo conexión con mi cerebro principal todavía.\n\n"
            "Manu necesita configurar la clave OPENCODE_GO_API_KEY en el archivo .env "
            "para que yo pueda pensar con toda mi capacidad.\n\n"
            "Mientras tanto, puedo ayudarte con cosas básicas. ¿Qué necesitas? 😊"
        )
    
    _actualizar_contexto_workspace()
    
    # 🔍 BUSCAR ARCHIVO MENCIONADO por Sandra
    archivo_encontrado = _buscar_archivo_mencionado(mensaje)
    contenido_archivo = ""
    if archivo_encontrado:
        contenido_archivo = _leer_documento_para_contexto(archivo_encontrado)
    
    # Construir mensajes
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Agregar historial de conversación (últimos 10 mensajes)
    if historial:
        for msg in historial[-10:]:
            role = "assistant" if msg.get("rol") == "asistente" else "user"
            content = msg.get("contenido", "")
            if content:
                messages.append({"role": role, "content": content})
    
    # Construir mensaje del usuario con TODO el contexto
    user_msg = mensaje
    
    # 1. Contenido del archivo que Sandra mencionó (LO MÁS IMPORTANTE)
    if contenido_archivo:
        user_msg += (
            f"\n\n---\n📂 HE ENCONTRADO ESTE ARCHIVO EN TU CARPETA:\n{contenido_archivo}"
            f"\n---\n"
            f"\n⚠️ INSTRUCCIÓN IMPORTANTE: NO me leas el documento de vuelta. "
            f"Ya sé lo que contiene. Lo que necesito es que COMPLETES las secciones "
            f"que faltan. Si Sandra dijo 'hice hasta el punto 4', entonces completa "
            f"los puntos 5 en adelante. Si hay campos vacíos, llénalos con los datos "
            f"que tienes del paciente. Si no tienes algún dato, indícale a Sandra "
            f"qué información necesitas. Sé CONCISO y ve directo a completar, no a describir."
        )
    
    # 2. Contexto del workspace
    if WORKSPACE_CONTEXT:
        user_msg += f"\n\n[Tu carpeta de trabajo: {WORKSPACE_CONTEXT}]"
    
    # 3. CC del paciente
    if paciente_cc:
        user_msg += f"\n\n[CC del paciente: {paciente_cc}]"
    
    messages.append({"role": "user", "content": user_msg})
    
    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2000,  # Suficiente para analizar documentos largos
            },
            timeout=30,
        )
        
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        else:
            return f"🤔 Lo siento Sandra, tuve un problema momentáneo. ¿Puedes intentar de nuevo?"
            
    except requests.exceptions.Timeout:
        return "⏰ Me demoré mucho pensando. ¿Me resumes tu pregunta en una frase corta?"
    except Exception:
        return "❌ Algo falló en mi conexión. Intenta de nuevo en un momento."


def procesar_mensaje(mensaje: str, paciente_cc: str = "", historial: list = None) -> dict:
    """
    Procesa un mensaje del chat. USA EL LLM REAL con el prompt maestro.
    """
    if not mensaje.strip():
        return {"contenido": "¿En qué te ayudo, Sandra? 😊", "accion": None}
    
    respuesta = _llamar_llm(mensaje, paciente_cc, historial)
    
    # Detectar acción sugerida
    accion = None
    msg_lower = mensaje.lower()
    if any(p in msg_lower for p in ["completa", "termina", "acaba", "documento", "formato", "punto"]):
        accion = "documento"
    elif any(p in msg_lower for p in ["busca", "archivo", "carpeta", "documentos de"]):
        accion = "buscar"
    elif any(p in msg_lower for p in ["verifica", "revisa", "comprueba", "siniestro"]):
        accion = "verificar"
    
    return {
        "contenido": respuesta,
        "accion": accion,
    }
