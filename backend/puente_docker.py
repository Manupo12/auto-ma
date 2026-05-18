"""
Puente Docker-WSL para extracción de portales.
Permite que la API (WSL) dispare navegación browser en Docker.
"""
import os
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./storage"))
DOCKER_CONTAINER = os.getenv("DOCKER_CONTAINER", "hermes-a34da917")
EXTRACTOR_SCRIPT = "/root/fisioterapia/backend/orquestador.py"


def extraer_desde_wsl(cc: str) -> Dict:
    """
    Dispara la extracción de portales desde WSL hacia Docker.
    
    1. Ejecuta docker exec en el contenedor
    2. El orquestador.py navega Medifolios + Positiva
    3. Extrae y fusiona datos
    4. Guarda JSON en storage/data/
    5. Retorna los datos extraídos
    """
    # Verificar que el contenedor existe
    check = subprocess.run(
        ["docker", "ps", "--filter", f"name={DOCKER_CONTAINER}", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=10
    )
    if DOCKER_CONTAINER not in check.stdout:
        return {
            "ok": False,
            "error": f"Contenedor {DOCKER_CONTAINER} no está corriendo. ¿Docker está activo?",
            "estado": "error_contenedor",
        }
    
    # Buscar si ya tenemos datos extraídos
    data_dir = STORAGE_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Buscar archivos existentes para esta CC
    existentes = list(data_dir.glob(f"*{cc}*-completo.json"))
    if existentes:
        mas_reciente = max(existentes, key=lambda p: p.stat().st_mtime)
        with open(mas_reciente) as f:
            datos = json.load(f)
        return {
            "ok": True,
            "datos": datos,
            "estado": "ya_extraido",
            "archivo": str(mas_reciente),
            "fecha_extraccion": datetime.fromtimestamp(mas_reciente.stat().st_mtime).isoformat(),
        }
    
    # ─── EJECUTAR EXTRACCIÓN ───
    # Esto puede tomar 2-5 minutos (navegación browser)
    comando = (
        f"cd /root/fisioterapia && "
        f"python3 {EXTRACTOR_SCRIPT} --cc {cc} --fusionar --validar 2>&1"
    )
    
    try:
        resultado = subprocess.run(
            ["docker", "exec", DOCKER_CONTAINER, "bash", "-c", comando],
            capture_output=True, text=True,
            timeout=600,  # 10 minutos máximo
        )
        
        output = resultado.stdout + "\n" + resultado.stderr
        
        # Buscar el archivo generado
        time.sleep(1)
        nuevos = list(data_dir.glob(f"*{cc}*-completo.json"))
        if nuevos:
            mas_reciente = max(nuevos, key=lambda p: p.stat().st_mtime)
            with open(mas_reciente) as f:
                datos = json.load(f)
            return {
                "ok": True,
                "datos": datos,
                "estado": "recien_extraido",
                "archivo": str(mas_reciente),
                "log": output[-500:],  # Últimas 500 líneas del log
            }
        else:
            return {
                "ok": False,
                "error": "Extracción completada pero no se generó el archivo JSON.",
                "estado": "sin_resultados",
                "log": output[-1000:],
            }
            
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "La extracción tomó más de 10 minutos. ¿Los portales están lentos?",
            "estado": "timeout",
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "estado": "error_ejecucion",
        }


def obtener_datos_verificados(cc: str) -> Dict:
    """
    Busca datos extraídos para una cédula y retorna resumen de verificación.
    Si no hay datos, retorna estado 'pendiente_extraccion'.
    """
    data_dir = STORAGE_DIR / "data"
    existentes = list(data_dir.glob(f"*{cc}*-completo.json"))
    
    if not existentes:
        return {
            "ok": True,
            "estado": "pendiente_extraccion",
            "mensaje": f"No hay datos extraídos para CC {cc}. Se necesita navegar los portales.",
        }
    
    mas_reciente = max(existentes, key=lambda p: p.stat().st_mtime)
    with open(mas_reciente) as f:
        datos = json.load(f)
    
    # Construir resumen de verificación
    resumen = {
        "ok": True,
        "estado": "verificado",
        "archivo": str(mas_reciente),
        "fecha_extraccion": datetime.fromtimestamp(mas_reciente.stat().st_mtime).isoformat(),
        "campos_verificados": {},
    }
    
    # Extraer campos clave
    paciente = datos.get("paciente", datos)
    
    campos_clave = {
        "nombre": paciente.get("nombre") or paciente.get("nombres", ""),
        "cedula": paciente.get("cc") or paciente.get("cedula", cc),
        "fecha_nacimiento": paciente.get("fecha_nacimiento", ""),
        "edad": paciente.get("edad", ""),
        "direccion": paciente.get("direccion", ""),
        "telefono": paciente.get("telefono", ""),
        "empresa": paciente.get("empresa", ""),
        "eps": paciente.get("eps", ""),
        "afp": paciente.get("afp", ""),
        "arl": paciente.get("arl", "POSITIVA"),
    }
    
    # Siniestro (puede estar en varios lugares)
    siniestro = (
        paciente.get("siniestro") or 
        paciente.get("no_siniestro") or
        datos.get("siniestro", "")
    )
    if siniestro:
        campos_clave["siniestro"] = siniestro
    
    # Diagnóstico
    diagnostico = (
        paciente.get("diagnostico") or
        datos.get("diagnostico", "")
    )
    if diagnostico:
        campos_clave["diagnostico"] = diagnostico
    
    # Estado de rehabilitación
    rehab = datos.get("rehabilitacion", {})
    if rehab:
        campos_clave["estado_rehab"] = rehab.get("estado", "")
        campos_clave["fecha_ingreso"] = rehab.get("fecha_ingreso", "")
    
    # Verificar cada campo
    for campo, valor in campos_clave.items():
        if valor:
            resumen["campos_verificados"][campo] = {
                "valor": str(valor),
                "estado": "✅",
                "fuente": "portales",
            }
        else:
            resumen["campos_verificados"][campo] = {
                "valor": "",
                "estado": "❌",
                "fuente": "no_encontrado",
            }
    
    return resumen
