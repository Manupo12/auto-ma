"""
Paso 5: Síntesis maestra — LLM razonador con contexto cruzado.

Compone contexto a partir de:
  - Transcripción del audio (chunked si es necesario)
  - Datos verificados de portales (Medifolios + Positiva)
  - Notas crudas del workspace
  - Formatos antiguos subidos como referencia

Llama al LLM razonador (deepseek-v4-pro) en subprocess aislado vía
lote_worker --tipo sintetizar para evitar OOM.

Si el contexto excede 30K chars, hace resumen progresivo antes.
"""
import json
import os
import re
import sys
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List


def _log(msg: str):
    print(f"[SINTESIS {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _formatear_portales(datos: dict) -> str:
    if not datos or datos.get("_vacio"):
        return "[NO HAY DATOS VERIFICADOS DE PORTALES]"
    medi = datos.get("medifolios", {})
    pos = datos.get("positiva", {})
    discrepancias = datos.get("_meta", {}).get("discrepancias", [])
    bloques = ["📋 DATOS VERIFICADOS PORTALES:"]
    if medi:
        nombre = (
            " ".join(filter(None, [
                medi.get("nombre1",""), medi.get("nombre2",""),
                medi.get("apellido1",""), medi.get("apellido2","")
            ])).strip()
            or medi.get("nombre", "")
        )
        if nombre: bloques.append(f"  Paciente: {nombre}")
        if medi.get("fecha_nacimiento"): bloques.append(f"  Fecha nacimiento: {medi['fecha_nacimiento']}")
        if medi.get("telefono"): bloques.append(f"  Telefono: {medi['telefono']}")
        if medi.get("direccion"): bloques.append(f"  Direccion: {medi['direccion']}")
        if medi.get("email"):    bloques.append(f"  Email: {medi['email']}")
        if medi.get("eps_ips") or medi.get("slct_eps_paciente"):
            bloques.append(f"  EPS: {medi.get('eps_ips') or medi.get('slct_eps_paciente','')}")
        if medi.get("afp") or medi.get("slct_afp_paciente"):
            bloques.append(f"  AFP: {medi.get('afp') or medi.get('slct_afp_paciente','')}")
        if medi.get("empresa") or medi.get("slct_empresa_paciente"):
            bloques.append(f"  Empresa (Medi): {medi.get('empresa') or medi.get('slct_empresa_paciente','')}")
        if medi.get("siniestro_medi") and medi["siniestro_medi"] != "[VERIFICAR]":
            bloques.append(f"  Siniestro (Medi): {medi['siniestro_medi']}")
    if pos.get("datos_asegurado"):
        da = pos["datos_asegurado"]
        if da.get("empresa"): bloques.append(f"  Empresa (Pos): {da['empresa']}")
        if da.get("cargo_asegurado"): bloques.append(f"  Cargo (Pos): {da['cargo_asegurado']}")
        if da.get("nit"): bloques.append(f"  NIT: {da['nit']}")
    if pos.get("siniestros"):
        for s in pos["siniestros"][:2]:
            partes = [f"id={s.get('id','?')}", f"fecha={s.get('fecha','?')}"]
            if s.get("tipo"): partes.append(f"tipo={s['tipo']}")
            if s.get("diagnostico"): partes.append(f"dx={s['diagnostico'][:50]}")
            if s.get("segmento"): partes.append(f"segmento={s['segmento']}")
            bloques.append(f"  Siniestro (Pos): {' | '.join(partes)}")
    # Siniestro en autorizaciones cuando Positiva no devuelve siniestros directos
    if not pos.get("siniestros") and pos.get("autorizaciones"):
        for aut in pos["autorizaciones"][:3]:
            posible_sin = aut.get("descripcion", "").strip()
            posible_fecha = aut.get("estado", "").strip()
            if posible_sin and re.match(r'^\d{8,12}$', posible_sin):
                bloques.append(f"  Siniestro (Pos-aut): {posible_sin}")
                if re.match(r'\d{2}/\d{2}/\d{4}', posible_fecha):
                    bloques.append(f"  Fecha evento (Pos-aut): {posible_fecha}")
                break
    rhi = pos.get("rhi", {})
    if rhi.get("fechas_encontradas"):
        bloques.append(f"  Fecha (RHI): {rhi['fechas_encontradas'][0]}")
    rehab = pos.get("rehabilitacion", {})
    if rehab.get("fechas_rehab"):
        bloques.append(f"  Fecha evento (Rehab): {rehab['fechas_rehab'][0]}")
    if discrepancias:
        bloques.append("\n⚠️ DISCREPANCIAS DETECTADAS:")
        for d in discrepancias:
            bloques.append(f"  - {d.get('campo','?')}: Medi={d.get('medifolios','?')} vs Pos={d.get('positiva','?')}")
    return "\n".join(bloques)


def _extraer_datos_notas(notas: list) -> dict:
    """Extrae campos estructurados de archivos CR_, CC_, VOI_ de Sandra."""
    datos = {}
    for nota in notas:
        contenido = nota.get("contenido", "")
        
        # Parse line-by-line first (precise extraction for tabular data)
        for line in contenido.split('\n'):
            line_lower = line.lower()
            if '|' in line:
                partes = [p.strip() for p in line.split('|')]
                label = partes[0].lower()
                
                # Contacto en empresa
                if "contacto en empresa" in label or "contacto/cargo" in label or "nombre contacto" in label:
                    contacto_val = partes[1] if len(partes) > 1 else ""
                    if contacto_val:
                        if "/" in contacto_val:
                            c_name, c_cargo = contacto_val.split("/", 1)
                            c_name = c_name.strip()
                            c_cargo = c_cargo.strip()
                        else:
                            c_name = contacto_val
                            c_cargo = ""
                        if c_name and c_name.lower() not in ("no", "si", "na", "n/a", "contacto en empresa/cargo"):
                            datos["empresa_contacto"] = c_name
                        if c_cargo:
                            datos["empresa_cargo_contacto"] = c_cargo
                            
                # Dirección de empresa
                elif "dirección de empresa" in label:
                    if len(partes) > 1 and partes[1] and partes[1].lower() not in ("no", "si", "na", "n/a"):
                        datos["empresa_direccion"] = partes[1]
                        
                # Teléfono de empresa
                elif "teléfono" in label and "empresa" in label:
                    if len(partes) > 1 and partes[1] and partes[1].lower() not in ("no", "si", "na", "n/a"):
                        datos["empresa_telefono"] = partes[1]
                        
                # Correo de empresa
                elif "correo" in label and len(partes) > 1:
                    correo_val = partes[1]
                    if "@" in correo_val:
                        datos["empresa_correo"] = correo_val

                # Fecha ingreso a la empresa / antigüedad
                elif "fecha ingreso a la empresa" in label:
                    if len(partes) >= 3:
                        date_val = partes[1]
                        time_val = partes[2]
                        if re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', date_val):
                            datos["fecha_ingreso_empresa"] = date_val
                        if time_val and time_val.lower() not in ("no", "si", "na", "n/a"):
                            datos["antiguedad_empresa"] = time_val
                    elif len(partes) >= 2:
                        date_val = partes[1]
                        if re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', date_val):
                            datos["fecha_ingreso_empresa"] = date_val

                # Fecha ingreso cargo
                elif "fecha ingreso cargo" in label:
                    if len(partes) >= 3:
                        date_val = partes[1]
                        time_val = partes[2]
                        if re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', date_val) and not datos.get("fecha_ingreso_empresa"):
                            datos["fecha_ingreso_empresa"] = date_val
                        if time_val and time_val.lower() not in ("no", "si", "na", "n/a") and not datos.get("antiguedad_empresa"):
                            datos["antiguedad_empresa"] = time_val

                # Fecha de nacimiento
                elif "fecha de nacimiento" in label:
                    if len(partes) >= 2:
                        date_val = partes[1]
                        if re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', date_val):
                            datos["fecha_nacimiento"] = date_val

        # Regex-based extractions (fallback & general matching)
        tipo_match = re.search(r'TIPO\s*(?:DE\s*)?SINIESTRO\s*[\|:\s]+([^\n\|]{5,40})', contenido, re.IGNORECASE)
        if tipo_match and not datos.get("tipo_siniestro"):
            datos["tipo_siniestro"] = tipo_match.group(1).strip()
            
        fecha_match = re.search(r'FECHA\s*DEL\s*EVENTO\s*[\|:\s]+(\d{1,2}/\d{1,2}/\d{4})', contenido, re.IGNORECASE)
        if fecha_match and not datos.get("fecha_evento"):
            datos["fecha_evento"] = fecha_match.group(1).strip()
            
        # Buscar todos los matches de CARGO y elegir el más confiable
        # Primero intentar "CARGO:" en ALL-CAPS (tabla clínica del CR) — es el cargo del paciente
        cargo_match_oficial = re.search(r'\bCARGO\s*[|:]\s*\n?\s*([A-Za-záéíóúñÁÉÍÓÚÑ \t]{5,60})', contenido)
        if cargo_match_oficial and not datos.get("cargo"):
            cargo = cargo_match_oficial.group(1).strip().split('\n')[0].strip()
            if len(cargo) > 4 and cargo.upper() not in ("CARGO", "FUNCIONES"):
                datos["cargo"] = cargo
        if not datos.get("cargo"):
            # Fallback: tomar TODOS los matches y elegir el que NO contenga palabras de contacto
            cargo_matches = list(re.finditer(r'CARGO\s*[\|:\s]+([A-Za-záéíóúñÁÉÍÓÚÑ \t]{5,60})', contenido, re.IGNORECASE))
            palabras_contacto = {"jefe", "director", "coordinador", "gerente", "supervisor", "profesional", "analista", "asesor"}
            for m in cargo_matches:
                cargo = m.group(1).strip().split('\n')[0].strip()
                primeras_palabras = set(cargo.lower().split()[:2])
                if len(cargo) > 4 and not primeras_palabras.intersection(palabras_contacto):
                    datos["cargo"] = cargo
                    break
                    
        seg_match = re.search(r'SEGMENTO\s*LESIONADO\s*[\|:\s]+([A-Za-záéíóúñÁÉÍÓÚÑ, \t]{5,80})', contenido, re.IGNORECASE)
        if seg_match and not datos.get("segmento"):
            datos["segmento"] = seg_match.group(1).strip()
            
        cie10 = re.findall(r'([A-Z]\d{2,3}(?:\.\d)?)\s+([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ\s,]{5,60})', contenido)
        if cie10 and not datos.get("diagnosticos"):
            datos["diagnosticos"] = [{"codigo": m[0], "descripcion": m[1].strip()} for m in cie10[:3]]
            
        eps_match = re.search(r'EPS\s*[-\s]*IPS\s*[\|:\* \t]+\s*([A-Za-záéíóúñÁÉÍÓÚÑ \t]{3,40})', contenido, re.IGNORECASE)
        if eps_match and not datos.get("eps"):
            eps = eps_match.group(1).strip()
            if eps and eps.upper() not in ("EPS", "IPS", "ENTIDAD"):
                datos["eps"] = eps
                
        sin_match = re.search(r'(?:NO\.?\s*SINIESTRO|siniestro)\s*[\|:\s]+(\d{8,12})', contenido, re.IGNORECASE)
        if sin_match and not datos.get("siniestro"):
            datos["siniestro"] = sin_match.group(1).strip()

        # AFP
        afp_match = re.search(r'AFP\s*[-:*| \t]+([A-Za-záéíóúñÁÉÍÓÚÑ \t]{3,30})', contenido, re.IGNORECASE)
        if afp_match and not datos.get("afp"):
            afp = afp_match.group(1).strip().split('\n')[0].strip()
            if afp and afp.upper() not in ("AFP", "PENSIONES", "FONDO"):
                datos["afp"] = afp

        # NIT de la empresa
        nit_match = re.search(r'NIT\s*(?:de\s*la\s*empresa)?\s*[-:*| \t]+([0-9]{5,12})', contenido, re.IGNORECASE)
        if nit_match and not datos.get("nit_empresa"):
            datos["nit_empresa"] = nit_match.group(1).strip()

        # Fecha de valoración (del CR_): "seguimiento realizado el DD/MM/YYYY"
        fv_match = re.search(r'seguimiento\s+realizado\s+el\s+(\d{1,2}/\d{1,2}/\d{4})', contenido, re.IGNORECASE)
        if not fv_match:
            fv_match = re.search(r'valoraci[oó]n.*?(\d{1,2}/\d{1,2}/\d{4})', contenido[:500], re.IGNORECASE)
        if fv_match and not datos.get("fecha_valoracion"):
            datos["fecha_valoracion"] = fv_match.group(1).strip()

        # Fecha ingreso a la empresa (del CC_)
        fi_match = re.search(r'FECHA\s*(?:DE\s*)?INGRESO[^\n]*?EMPRESA[^\n]*?(\d{1,2}/\d{1,2}/\d{4})', contenido, re.IGNORECASE)
        if not fi_match:
            fi_match = re.search(r'FECHA\s*(?:DE\s*)?INGRESO[^\n]*?(\d{1,2}/\d{1,2}/\d{4})', contenido, re.IGNORECASE)
        if fi_match and not datos.get("fecha_ingreso_empresa"):
            datos["fecha_ingreso_empresa"] = fi_match.group(1).strip()

        # Antigüedad en la empresa (del CC_)
        ant_match = re.search(r'ANTIG[ÜU]EDAD\s*(?:EN\s*LA\s*EMPRESA)?\s*[-:*| \t]+([0-9a-záéíóúñ \t]{3,40})', contenido, re.IGNORECASE)
        if ant_match and not datos.get("antiguedad_empresa"):
            ant = ant_match.group(1).strip().split('\n')[0].strip()
            if ant:
                datos["antiguedad_empresa"] = ant

        # Forma de integración (del CR_)
        fi2_match = re.search(r'FORMA\s*DE\s*INTEGRACI[OÓ]N\s*[-:*| \t]+([^\n]{5,60})', contenido, re.IGNORECASE)
        if fi2_match and not datos.get("forma_integracion"):
            datos["forma_integracion"] = fi2_match.group(1).strip()

        # Vinculación laboral (del CC_)
        vinc_match = re.search(r'FORMA\s*DE\s*VINCULACI[OÓ]N\s*[-:*| \t]+([^\n]{5,60})', contenido, re.IGNORECASE)
        if vinc_match and not datos.get("forma_vinculacion"):
            datos["forma_vinculacion"] = vinc_match.group(1).strip()

        # Empresa: contacto, teléfono, correo, dirección (del CR_)
        contacto_match_cr = re.search(r'Señora?\s*:\s*([A-Za-záéíóúñÁÉÍÓÚÑ \t]{3,50})', contenido, re.IGNORECASE)
        if contacto_match_cr and not datos.get("empresa_contacto"):
            datos["empresa_contacto"] = contacto_match_cr.group(1).strip()
            
        contacto_cargo_cr = re.search(r'Cargo\s*:\s*([A-Za-záéíóúñÁÉÍÓÚÑ \t]{3,50})', contenido, re.IGNORECASE)
        if contacto_cargo_cr and not datos.get("empresa_cargo_contacto"):
            cargo_val = contacto_cargo_cr.group(1).strip()
            if any(k in cargo_val.lower() for k in ("jefe", "director", "coordinador", "gerente", "supervisor", "talento", "recursos")):
                datos["empresa_cargo_contacto"] = cargo_val

        contacto_match = re.search(r'(?:NOMBRE\s+CONTACTO|CONTACTO)\s*[-:*| \t]+([A-Za-záéíóúñÁÉÍÓÚÑ \t]{5,60})', contenido, re.IGNORECASE)
        if contacto_match and not datos.get("empresa_contacto"):
            c_val = contacto_match.group(1).strip()
            if "reserva" not in c_val.lower() and "apto" not in c_val.lower():
                datos["empresa_contacto"] = c_val

        tel_cr_match = re.search(r'Tel[eé]fono\s*:\s*([0-9\s\-\+]{7,15})', contenido, re.IGNORECASE)
        if tel_cr_match and not datos.get("empresa_telefono"):
            datos["empresa_telefono"] = tel_cr_match.group(1).strip()

        tel_match = re.search(r'TEL[EÉ]FONO\s*(?:EMPRESA)?\s*[-:*| \t]+([0-9 \t\-\+]{7,15})', contenido, re.IGNORECASE)
        if tel_match and not datos.get("empresa_telefono"):
            datos["empresa_telefono"] = tel_match.group(1).strip()

        correo_match = re.search(r'CORREO\s*(?:ELECTR[OÓ]NICO)?\s*(?:EMPRESA)?\s*[-:*| \t]+([^\s@]+@[^\s|]{3,40})', contenido, re.IGNORECASE)
        if correo_match and not datos.get("empresa_correo"):
            datos["empresa_correo"] = correo_match.group(1).strip()

        dir_cr_match = re.search(r'Direcci[oó]n\s*:\s*([^\n]{10,80})', contenido, re.IGNORECASE)
        if dir_cr_match and not datos.get("empresa_direccion"):
            dir_val = dir_cr_match.group(1).strip()
            if "reserva" not in dir_val.lower() and "apto" not in dir_val.lower():
                datos["empresa_direccion"] = dir_val

        dir_match = re.search(r'DIRECCI[OÓ]N\s*(?:EMPRESA)?\s*[-:*| \t]+([^\n]{10,80})', contenido, re.IGNORECASE)
        if dir_match and not datos.get("empresa_direccion"):
            # Avoid residencia
            for m in re.finditer(r'DIRECCI[OÓ]N[^\n|:]*?[|:]\s*([^\n|]{10,80})', contenido, re.IGNORECASE):
                linea_completa = m.group(0).lower()
                if "residencia" not in linea_completa and "trabajador" not in linea_completa:
                    datos["empresa_direccion"] = m.group(1).strip()
                    break

        # Historia ocupacional (del CC_): buscar filas de tabla empresa|cargo|tiempo|motivo
        # Patrón: línea con al menos 2 campos separados por | (tabla extraída de docx)
        if not datos.get("historia_ocupacional_raw"):
            hist_lines = []
            for linea in contenido.split('\n'):
                linea_s = linea.strip()
                # Línea con al menos 2 pipes → probable fila de tabla de historia
                if linea_s.count('|') >= 2:
                    partes_hist = [p.strip() for p in linea_s.split('|') if p.strip()]
                    if len(partes_hist) >= 3 and not any(h in linea_s.lower() for h in ('empresa', 'cargo', 'tiempo', 'motivo')):
                        hist_lines.append(partes_hist)
                # También buscar líneas con "ALCALDIA", "COOTRANS", nombres de empresa conocidos
                elif re.search(r'(ALCALD|CAMARA|ELECTRO|COOTRANS|EJERCITO|BOLIVAR)', linea_s.upper()):
                    # Extraer empresa, cargo, duración en un mismo texto
                    hist_lines.append([linea_s])
            if hist_lines:
                datos["historia_ocupacional_raw"] = hist_lines[:6]

        # Núcleo familiar / composición familiar (del CC_)
        nucleo_match = re.search(r'N[UÚ]CLEO\s*FAMILIAR\s*[-:*| \t]+([^\n]{5,100})', contenido, re.IGNORECASE)
        if nucleo_match and not datos.get("nucleo_familiar"):
            datos["nucleo_familiar"] = nucleo_match.group(1).strip()

        sostenedor_match = re.search(r'SOSTENEDOR\s*(?:ECON[OÓ]MICO)?\s*[-:*| \t]+([^\n]{3,50})', contenido, re.IGNORECASE)
        if sostenedor_match and not datos.get("sostenedor"):
            datos["sostenedor"] = sostenedor_match.group(1).strip()

        # Extraer bloque "CONCEPTO INTEGRAL FINAL" del CC_
        # Este bloque es el texto que va directamente a Sección 9 del VOI
        concepto_match = re.search(
            r'(?:CONCEPTO\s+INTEGRAL\s+FINAL|7\.\s*\n?\s*CONCEPTO)\s*\n(.*?)(?:\n\d+\.\s*\n|\Z)',
            contenido, re.DOTALL | re.IGNORECASE
        )
        if concepto_match and not datos.get("concepto_integral_final"):
            bloque = concepto_match.group(1).strip()
            if len(bloque) > 100:
                datos["concepto_integral_final"] = bloque

        # Extraer TODOS los bloques de notas médicas (puede haber múltiples consultas)
        # Tomar la MÁS RECIENTE (última en aparecer en el documento = Sandra la escribe arriba)
        # Nota: en el CC_ los bloques van: fecha_más_reciente primero OR fecha_más_antigua primero
        # → para ser robusto, recolectar TODOS y ordenar por fecha
        if not datos.get("tratamiento_atel_raw"):
            trat_all = list(re.finditer(
                r'(\d{1,2}/\d{1,2}/\d{4})\s*\n\s*(FISIATRIA|MEDICINA LABORAL|DT\.[^\n]{0,80}|ELECTROMIOGRAFI[A-Z]?[^\n]{0,60})[^\n]*\n(.*?)(?=\n\d{1,2}/\d{1,2}/\d{4}\s*\n\s*(?:FISIATRIA|MEDICINA LABORAL|DT\.|ELECTRO)|\n\d+\.\s*\n\s*(?:OBSTÁCULOS|CONCEPTO|LOGROS)|\Z)',
                contenido, re.DOTALL | re.IGNORECASE
            ))
            if trat_all:
                # Parsear fechas para ordenar
                from datetime import datetime as dt_
                bloques_con_fecha = []
                for m in trat_all:
                    try:
                        partes_f = m.group(1).strip().split('/')
                        if len(partes_f) == 3:
                            fecha_obj = dt_(int(partes_f[2]), int(partes_f[1]), int(partes_f[0]))
                        else:
                            fecha_obj = dt_(2000,1,1)
                    except Exception:
                        fecha_obj = dt_(2000,1,1)
                    cuerpo = m.group(3).strip()[:5000]
                    bloque_texto = f"{m.group(1).strip()}\n{m.group(2).strip()}\n\n{cuerpo}"
                    bloques_con_fecha.append((fecha_obj, bloque_texto, m.group(1).strip()))

                # Ordenar de más reciente a más antiguo
                bloques_con_fecha.sort(key=lambda x: x[0], reverse=True)
                # La nota más reciente = fecha_valoracion
                if not datos.get("fecha_valoracion"):
                    datos["fecha_valoracion"] = bloques_con_fecha[0][2]
                # Concatenar todos los bloques (más reciente primero)
                datos["tratamiento_atel_raw"] = "\n\n---\n\n".join(b[1] for b in bloques_con_fecha[:3])

        # Nivel educativo: detectar cuál tiene la X marcada
        # Formato CC_ (pipe-separated): "Nivel educativo | ... | Profesional | X"
        # La opción INMEDIATAMENTE ANTES del "X" es la seleccionada
        if not datos.get("nivel_educativo"):
            for linea in contenido.split('\n'):
                linea_low = linea.lower()
                if 'nivel educativo' in linea_low and '|' in linea:
                    partes_ned = [p.strip() for p in linea.split('|')]
                    opciones_ned = {
                        "profesional": "Profesional",
                        "especialización/ postgrado/ maestría": "Especialización",
                        "técnico/ tecnológico": "Técnico/ Tecnológico",
                        "bachillerato: modalidad": "Bachillerato",
                        "básica primaria": "Básica primaria",
                        "formación empírica": "Formación empírica",
                        "analfabeta": "Analfabeta",
                    }
                    for i, parte in enumerate(partes_ned):
                        if parte == 'X' and i > 0:
                            opcion_previa = partes_ned[i-1].strip().lower()
                            for key, val in opciones_ned.items():
                                if key in opcion_previa:
                                    datos["nivel_educativo"] = val
                                    break
                        if datos.get("nivel_educativo"):
                            break
                    if datos.get("nivel_educativo"):
                        break

            # Fallback: busca en múltiples líneas (CC_ con newlines reales en el texto)
            if not datos.get("nivel_educativo"):
                for opcion, valor in [
                    (r'Profesional', "Profesional"),
                    (r'Especialización', "Especialización"),
                    (r'Técnico', "Técnico/ Tecnológico"),
                    (r'Bachillerato', "Bachillerato"),
                ]:
                    # Busca el patrón "OPCION <separator> X" donde separator es | o \n
                    if re.search(rf'{opcion}\s*(?:\||\n)\s*X(?:\s*(?:\||\n|$))', contenido, re.IGNORECASE):
                        datos["nivel_educativo"] = valor
                        break

        # Formación: campo "Otros" que sigue a "Analfabeta" en CC_
        if not datos.get("formacion_oficios"):
            form_match = re.search(
                r'(?:Analfabeta|Formación informal oficios)[^\n]*\n([^\n]{10,150})',
                contenido, re.IGNORECASE
            )
            if form_match:
                candidato = form_match.group(1).strip()
                # Evitar capturar "Otros" o texto de etiqueta
                if not re.match(r'^(?:Otros|Teléfonos|Diagnóstico|EPS)', candidato, re.IGNORECASE):
                    datos["formacion_oficios"] = candidato

        # Composición familiar desde Concepto Integral
        if not datos.get("composicion_familiar_raw"):
            fam_match = re.search(
                r'[Vv]ive con\s+(.{20,200}?)(?:\.\s+[Ll]abora|\.\s+[Cc]omponentes|\n\n)',
                contenido, re.DOTALL
            )
            if fam_match:
                datos["composicion_familiar_raw"] = fam_match.group(0).strip()

        # Ingresos del hogar desde Concepto Integral
        if not datos.get("ingreso_hogar"):
            ingreso_match = re.search(r'(\d[\d\.]+\.?\d{3})\s*pesos', contenido, re.IGNORECASE)
            if ingreso_match:
                datos["ingreso_hogar"] = ingreso_match.group(1) + " pesos"

        # Rol laboral: texto de componentes de desempeño desde Concepto Integral
        if not datos.get("rol_laboral_raw"):
            rl_match = re.search(
                r'[Cc]omponentes de desempeño:\s*(.*?)(?:\.\s+[Aa]filiada?\s+refiere|\Z)',
                contenido, re.DOTALL
            )
            if rl_match:
                datos["rol_laboral_raw"] = rl_match.group(1).strip()[:800]

        # ─── DOMINANCIA (lateralidad) ───────────────────────────────────────────
        # En la CC_, la fila de dominancia tiene formato: "Dominancia | Derecha | X | Izquierda | Ambidiestra"
        # La opción INMEDIATAMENTE ANTES del "X" es la seleccionada
        if not datos.get("dominancia"):
            for linea in contenido.split('\n'):
                if 'dominancia' in linea.lower() and '|' in linea:
                    partes_dom = [p.strip() for p in linea.split('|')]
                    opciones_dom = ("Derecha", "Izquierda", "Ambidiestra")
                    for i, parte in enumerate(partes_dom):
                        if parte == 'X' and i > 0:
                            # El elemento anterior al X es la opción seleccionada
                            opcion_previa = partes_dom[i-1]
                            if opcion_previa in opciones_dom:
                                datos["dominancia"] = opcion_previa
                                break
                    if datos.get("dominancia"):
                        break

        # Fallback: detectar DIESTRA/ZURDA en texto de notas médicas
        if not datos.get("dominancia"):
            if re.search(r'\bDIESTRA\b', contenido, re.IGNORECASE):
                datos["dominancia"] = "Derecha"
            elif re.search(r'\bZURDA\b', contenido, re.IGNORECASE):
                datos["dominancia"] = "Izquierda"
    return datos


def _formatear_notas(notas: list) -> str:
    if not notas:
        return "[NO HAY NOTAS CRUDAS]"
    bloques = [f"📝 NOTAS CRUDAS ({len(notas)} archivos):"]
    for n in notas[:5]:
        tipo = n.get("tipo", "")
        nombre = n.get("nombre", "")
        contenido = n.get("contenido", "")
        if tipo == "voi_referencia":
            # Ya incluido completo en bloque ⭐⭐⭐ arriba — no duplicar
            bloques.append(f"\n--- {nombre} [VOI REFERENCIA: ver bloque ⭐⭐⭐ arriba] ---")
            continue
        if tipo == "cc_paciente":
            # AUTORITATIVOS ya tiene los campos clave del CC_ — enviar solo 3000 chars extra
            bloques.append(f"\n--- {nombre} (CC_, primeros 3000 chars) ---\n{contenido[:3000]}")
        else:
            bloques.append(f"\n--- {nombre} ---\n{contenido[:2000]}")
    return "\n".join(bloques)


def _formatear_formatos_subidos(formatos: list) -> str:
    if not formatos:
        return ""
    bloques = [f"📄 FORMATOS DE REFERENCIA SUBIDOS POR SANDRA ({len(formatos)}):"]
    for f in formatos:
        bloques.append(f"\n--- {f['nombre']} ---\n{f['contenido']}")
    return "\n".join(bloques)


def _resumir_si_largo(texto: str, max_chars: int = 30000) -> str:
    if len(texto) <= max_chars:
        return texto
    inicio_chars = max_chars * 4 // 10
    fin_chars = max_chars * 4 // 10
    return (
        texto[:inicio_chars]
        + f"\n\n[...RESUMIDO: {len(texto) - inicio_chars - fin_chars} chars omitidos del medio...]\n\n"
        + texto[-fin_chars:]
    )


def _componer_contexto(transcripcion, datos_portales, notas_crudas, formatos_subidos, paciente_cc) -> str:
    # Verificar si hay un VOI completado por Sandra en el workspace para este paciente
    # Si lo hay, es la fuente MÁS CONFIABLE — usar todos sus campos como AUTORITATIVOS
    voi_referencia_texto = ""
    for nota in (notas_crudas or []):
        if nota.get("tipo") == "voi_referencia":
            voi_referencia_texto = nota.get("contenido", "")
            break

    transcripcion_texto = transcripcion.get("texto", "")
    if len(transcripcion_texto) > 20000:
        transcripcion_texto = _resumir_si_largo(transcripcion_texto, 20000)
    bloques = [
        f"═══ PACIENTE CC: {paciente_cc} ═══\n",
        "🎙️ TRANSCRIPCIÓN DEL AUDIO:",
        transcripcion_texto,
        "",
    ]

    if voi_referencia_texto:
        bloques.append(
            "⭐⭐⭐ VOI DE REFERENCIA DE SANDRA (MÁXIMA PRIORIDAD):\n"
            "Este es el documento que Sandra completó manualmente para ESTE paciente.\n"
            "TODOS los campos de este VOI son correctos. Úsalos exactamente.\n"
            "Si hay conflicto entre este VOI y cualquier otra fuente, SIEMPRE prevalece este VOI.\n\n"
            f"{voi_referencia_texto[:8000]}\n"
        )
        bloques.append("")
    # Pre-extraer datos estructurados de los archivos de Sandra (F-5)
    datos_de_notas = _extraer_datos_notas(notas_crudas)
    if datos_de_notas:
        bloques_notas = ["📋 DATOS EXTRAÍDOS DE ARCHIVOS DE SANDRA (AUTORITATIVOS):"]
        if datos_de_notas.get("tipo_siniestro"):
            bloques_notas.append(f"  Tipo siniestro: {datos_de_notas['tipo_siniestro']}")
        if datos_de_notas.get("fecha_evento"):
            bloques_notas.append(f"  Fecha del evento: {datos_de_notas['fecha_evento']}")
        if datos_de_notas.get("cargo"):
            bloques_notas.append(f"  Cargo actual: {datos_de_notas['cargo']}")
        if datos_de_notas.get("segmento"):
            bloques_notas.append(f"  Segmento lesionado: {datos_de_notas['segmento']}")
        if datos_de_notas.get("diagnosticos"):
            for dx in datos_de_notas["diagnosticos"][:2]:
                bloques_notas.append(f"  Diagnostico: {dx['codigo']} - {dx['descripcion']}")
        if datos_de_notas.get("eps"):
            bloques_notas.append(f"  EPS: {datos_de_notas['eps']}")
        if datos_de_notas.get("siniestro"):
            bloques_notas.append(f"  Siniestro (notas): {datos_de_notas['siniestro']}")
        if datos_de_notas.get("afp"):
            bloques_notas.append(f"  AFP: {datos_de_notas['afp']}")
        if datos_de_notas.get("nit_empresa"):
            bloques_notas.append(f"  NIT empresa: {datos_de_notas['nit_empresa']}")
        if datos_de_notas.get("fecha_valoracion"):
            bloques_notas.append(f"  Fecha valoración (CR): {datos_de_notas['fecha_valoracion']}")
        if datos_de_notas.get("fecha_ingreso_empresa"):
            bloques_notas.append(f"  Fecha ingreso empresa: {datos_de_notas['fecha_ingreso_empresa']}")
        if datos_de_notas.get("antiguedad_empresa"):
            bloques_notas.append(f"  Antigüedad empresa: {datos_de_notas['antiguedad_empresa']}")
        if datos_de_notas.get("forma_integracion"):
            bloques_notas.append(f"  Forma de integración: {datos_de_notas['forma_integracion']}")
        if datos_de_notas.get("forma_vinculacion"):
            bloques_notas.append(f"  Forma de vinculación: {datos_de_notas['forma_vinculacion']}")
        if datos_de_notas.get("empresa_contacto"):
            bloques_notas.append(f"  Contacto empresa: {datos_de_notas['empresa_contacto']}")
        if datos_de_notas.get("empresa_telefono"):
            bloques_notas.append(f"  Teléfono empresa: {datos_de_notas['empresa_telefono']}")
        if datos_de_notas.get("empresa_correo"):
            bloques_notas.append(f"  Correo empresa: {datos_de_notas['empresa_correo']}")
        if datos_de_notas.get("empresa_direccion"):
            bloques_notas.append(f"  Dirección empresa: {datos_de_notas['empresa_direccion']}")
        if datos_de_notas.get("historia_ocupacional_raw"):
            bloques_notas.append(f"  Historia ocupacional (CC_): {datos_de_notas['historia_ocupacional_raw']}")
        nuc = datos_de_notas.get("nucleo_familiar", "")
        fam_raw = datos_de_notas.get("composicion_familiar_raw", "")
        sos = datos_de_notas.get("sostenedor", "")
        ing = datos_de_notas.get("ingreso_hogar", "")
        if nuc or fam_raw or sos or ing:
            lineas_fam = ["  ⭐ COMPOSICIÓN FAMILIAR (CC_) — OBLIGATORIO COPIAR EXACTO SIN MODIFICAR:"]
            if nuc:
                lineas_fam.append(f"    composicion_familiar.nucleo = '{nuc}'")
            if fam_raw:
                lineas_fam.append(f"    composicion_familiar.convivencia = '{fam_raw}'")
            if sos:
                lineas_fam.append(f"    composicion_familiar.sostenedor = '{sos}'")
            if ing:
                lineas_fam.append(f"    composicion_familiar.ingreso_promedio = '{ing}'")
            lineas_fam.append("    REGLA: NO cambiar género (esposo ≠ esposa). NO cambiar cifras. COPIAR EXACTO.")
            bloques_notas.append("\n".join(lineas_fam))

        if datos_de_notas.get("concepto_integral_final"):
            bloques_notas.append(
                f"  ⭐ CONCEPTO INTEGRAL FINAL (CC_) — COPIAR DIRECTAMENTE a consulta.concepto:\n"
                f"  {datos_de_notas['concepto_integral_final'][:2000]}"
            )
        if datos_de_notas.get("tratamiento_atel_raw"):
            bloques_notas.append(
                f"  ⭐ NOTAS MÉDICAS (CC_) — COPIAR DIRECTAMENTE a tratamiento_atel:\n"
                f"  {datos_de_notas['tratamiento_atel_raw'][:8000]}"
            )
        if datos_de_notas.get("nivel_educativo"):
            bloques_notas.append(f"  Nivel educativo (CC_ checkbox): {datos_de_notas['nivel_educativo']}")
        if datos_de_notas.get("formacion_oficios"):
            bloques_notas.append(f"  Formación/oficios (CC_): {datos_de_notas['formacion_oficios']}")
        if datos_de_notas.get("rol_laboral_raw"):
            bloques_notas.append(f"  Rol laboral/componentes (CC_): {datos_de_notas['rol_laboral_raw'][:500]}")
        if datos_de_notas.get("dominancia"):
            bloques_notas.append(f"  Dominancia (CC_ checkbox): {datos_de_notas['dominancia']}")
        bloques.append("\n".join(bloques_notas) + "\n")
    bloques.append(_formatear_portales(datos_portales))
    bloques.append("")
    bloques.append(_formatear_notas(notas_crudas))
    bloques.append("")
    bloques.append(_formatear_formatos_subidos(formatos_subidos))
    return "\n".join(bloques)


PROMPT_USUARIO_SINTESIS = """Eres Tomy, asistente clínico EXPERTO de Sandra (RILO SAS, ARL Positiva Colombia).

Tu tarea AHORA: a partir del contexto cruzado abajo (audio + portales + notas + formatos), produce un JSON estructurado con TODOS los datos clínicos necesarios para generar los 7 formatos oficiales.

Devuelve SOLO un bloque JSON válido entre ```json ... ```. Estructura esperada:

```json
{
  "paciente": {"documento": "...", "nombre": "...", "fecha_nacimiento": "YYYY-MM-DD o DD/MM/YYYY tal como aparece en el portal", "edad": "...", "telefono": "...", "direccion": "...", "email": "...", "eps_ips": "...", "afp": "...", "ocupacion": "...", "dominancia": "Diestro|Zurdo|Ambidiestro", "estado_civil": "...", "nivel_educativo": "...", "formacion_oficios": "formación específica, títulos obtenidos, del campo Formación/oficios (CC_)"},
  "empresa": {"nombre": "...", "nit": "...", "cargo": "...", "contacto": "...", "cargo_contacto": "...", "direccion": "...", "telefono": "...", "correo": "..."},
  "laboral": {
    "cargo": "...",
    "tareas": "descripción detallada de tareas del cargo actual",
    "herramientas": "herramientas y equipos utilizados en el cargo",
    "horario": "horario de trabajo",
    "epp": "elementos de protección personal usados",
    "antiguedad_cargo": "tiempo en el cargo actual",
    "antiguedad_empresa": "tiempo total trabajando en la empresa",
    "fecha_ingreso_empresa": "DD/MM/YYYY de ingreso a la empresa actual",
    "requerimientos_motrices": "exigencias físicas y motrices del cargo",
    "vinculacion": "SI|NO",
    "forma_vinculacion": "Contrato a término indefinido|Contrato a término fijo|En carrera administrativa|...",
    "modalidad": "Presencial|Virtual|Híbrido",
    "ocurrencia_atel": "SI|NO",
    "lugar_atel": "Puesto de trabajo|Área de trabajo|Otro"
  },
  "historia_ocupacional": [
    {"empresa": "empresa actual primero", "cargo": "cargo en esa empresa", "duracion": "tiempo trabajado", "motivo_retiro": "Actualmente|Voluntario|Despido|..."},
    {"empresa": "empresa anterior", "cargo": "cargo anterior", "duracion": "...", "motivo_retiro": "..."}
  ],
  "siniestro": {"id_siniestro": "...", "fecha_evento": "DD/MM/YYYY", "tipo_evento": "Accidente de Trabajo|Enfermedad Laboral", "diagnostico_cie10": "código CIE-10 - descripción", "descripcion": "...", "segmento_lesionado": "...", "incapacitado": true, "tiempo_incapacidad": "..."},
  "consulta": {"fecha": "DD de mes de YYYY", "metodologia": "...", "concepto": "concepto final del VOI (párrafo largo)"},
  "tratamiento_atel": "<<CC_NOTAS>>",
  "estado_caso": "NUEVO|SEGUIMIENTO|CIERRE|PRUEBA_TRABAJO",
  "proceso_productivo": "...",
  "apreciacion_trabajador": "...",
  "materiales": [{"nombre":"...","estado":"..."}],
  "peligros": [{"nombre":"...","descripcion":"...","recomendacion":"..."}],
  "tareas_criticas": [{"tarea":"...","observacion":"...","desempeno":"..."}],
  "concepto_desempeno": "...",
  "recomendaciones": {"trabajador":"...","empresa":"..."},
  "logros": "...",
  "obstaculos": "...",
  "composicion_familiar": {"nucleo": "...", "integrantes": "...", "sostenedor": "...", "ingreso_promedio": "...", "responsabilidad": "...", "convivencia": "..."},
  "rol_laboral": {"tareas_operaciones": "...", "sensorio_motor": "...", "cognitivo": "...", "psicologicos": "...", "social": "...", "tiempo_ejecucion": "...", "forma_integracion": "..."},
  "areas_ocupacionales": {
    "cuidado_personal": {
      "Lavarse": "no dificultad|dificultad leve|dificultad moderada|dificultad severa|dificultad completa o dict con {nivel, observacion}",
      "Cuidado de partes del cuerpo": "no dificultad|dificultad leve|dificultad moderada|dificultad severa|dificultad completa o dict con {nivel, observacion}",
      "Higiene personal": "...",
      "Vestirse": "...",
      "Quitarse la ropa": "...",
      "Ponerse calzado": "...",
      "Comer": "...",
      "Beber": "...",
      "Cuidado de la propia salud": "...",
      "Control de la dieta y forma física": "..."
    },
    "comunicacion": {
      "Con recepción de mensajes verbales": "no dificultad|dificultad leve|dificultad moderada|dificultad severa|dificultad completa o dict con {nivel, observacion}",
      "Con recepción de mensajes no verbales": "...",
      "Con recepción de mensajes en lenguaje de signos": "...",
      "Con recepción de mensajes escritos": "...",
      "Habla": "...",
      "Producción de mensajes no verbales": "...",
      "Mensajes escritos": "...",
      "Conversación": "...",
      "Discusión": "...",
      "Utilización de dispositivos y técnicas de comunicación": "..."
    },
    "movilidad": {
      "Cambiar las posturas corporales básicas": "no dificultad|dificultad leve|dificultad moderada|dificultad severa|dificultad completa o dict con {nivel, observacion}",
      "Mantener la posición del cuerpo": "...",
      "Levantar y llevar objetos": "...",
      "Uso fino de la mano": "...",
      "Uso de la mano y el brazo": "...",
      "Andar y desplazarse por el entorno": "...",
      "Desplazarse por distintos lugares": "...",
      "Desplazarse utilizando algún tipo de equipo": "...",
      "Utilizar transporte como pasajero": "...",
      "Conducir": "..."
    },
    "aprendizaje": {
      "Mirar": "no dificultad|dificultad leve|dificultad moderada|dificultad severa|dificultad completa o dict con {nivel, observacion}",
      "Escuchar": "...",
      "Aprender a leer escribir y calcular": "...",
      "Aprender a calcular": "...",
      "Pensar": "...",
      "Leer": "..."
    },
    "vida_domestica": {
      "Adquisición de un lugar para vivir": "no dificultad|dificultad leve|dificultad moderada|dificultad severa|dificultad completa o dict con {nivel, observacion}",
      "Adquisición de bienes y servicios": "...",
      "Preparar comidas": "...",
      "Hacer los quehaceres de la casa": "...",
      "Limpiar / Hacer oficio": "...",
      "Cuidado de los objetos del hogar": "...",
      "Ayudar a los demás": "..."
    }
  },
  "orientacion_ocupacional": "...",
  "_meta": {
    "campos_faltantes": ["lista de campos críticos sin info"],
    "discrepancias": ["resoluciones tomadas"],
    "confianza_global": 0.0-1.0
  }
}
```

REGLAS ESTRICTAS:
- REGLA MÁXIMA: Si en el contexto aparece "⭐⭐⭐ VOI DE REFERENCIA DE SANDRA", extrae TODOS los campos directamente de ese documento. Es el VOI que Sandra completó a mano. No necesitas inferir ni generar — solo leer y trasladar.
- Datos de IDENTIDAD (nombre, CC, fecha_nacimiento, telefono, direccion): COPIAR EXACTAMENTE del bloque
  📋 DATOS VERIFICADOS PORTALES. Si el audio dice algo diferente, IGNORAR el audio para estos campos.
- Nombre del paciente: usar el nombre EXACTO del portal, no el del audio. Nunca cambies apellidos.
- Si el portal tiene "PUENTES" como apellido, el JSON debe decir "PUENTES", nunca "FUENTES" ni variantes.

REGLAS:
- Si un dato está en portales Y en audio Y coinciden → úsalo.
- Si discrepan → prevalece portal (es fuente oficial). Marca en _meta.discrepancias.
- Si solo está en audio (subjetivo) → úsalo y marca confianza_global menor.
- Si falta dato crítico → escribe "[FALTA: descripción específica]" y agrégalo a campos_faltantes.
- NUNCA inventes datos clínicos. Si no sabes, di [FALTA].
- Español colombiano clínico.

REGLAS ADICIONALES:
- "proceso_productivo", "tareas_criticas", "apreciacion_trabajador": SOLO del cargo actual (empresa.nombre + empresa.cargo).
- Si el audio menciona trabajos anteriores, ponlos en "apreciacion_trabajador" como historial laboral previo, NO en tareas_criticas.
- Si hay contradiccion entre proceso_productivo y empresa.cargo, prevalece empresa.cargo (oficial en el sistema de riesgos).
- Si una tarea no corresponde al cargo actual, omitirla o marcarla como historial previo.
- Dominancia (lateralidad): extraer del audio con cuidado. Si no esta claro, poner "[VERIFICAR: derecha o izquierda]".

REGLAS PARA NOTAS DE ARCHIVO (📝 NOTAS CRUDAS):
- Los archivos CR_, VOI_, CC_ que aparecen en 📝 NOTAS CRUDAS son documentos OFICIALES generados por Sandra.
- Para los siguientes campos, si aparecen en las notas de archivo, SON AUTORITATIVOS (igual de confiables que el portal):
  * empresa.cargo → buscar "Nombre del cargo:", "CARGO:", "cargo asegurado"
  * siniestro.tipo_evento → buscar "TIPO DE SINIESTRO", "Enfermedad Laboral", "Accidente de Trabajo"
  * siniestro.fecha_evento → buscar "FECHA DEL EVENTO", "Fecha del evento"
  * siniestro.id_siniestro → buscar "Siniestro:", "NO. SINIESTRO" con digitos
  * siniestro.diagnostico_cie10 → buscar diagnosticos CIE-10 en notas clinicas
  * empresa.nombre → buscar el nombre de la empresa en el encabezado del CR
  * paciente.eps_ips → buscar "EPS - IPS*" en las notas
  * paciente.afp → buscar "AFP:" en notas
  * empresa.nit → buscar "NIT de la Empresa:" en notas (número de 9-10 dígitos)
  * consulta.fecha → buscar "Fecha valoración (CR):" en DATOS AUTORITATIVOS — OBLIGATORIO completarlo
  * laboral.fecha_ingreso_empresa → buscar "Fecha ingreso empresa:" en DATOS AUTORITATIVOS
  * laboral.antiguedad_empresa → buscar "Antigüedad empresa:" en DATOS AUTORITATIVOS  
  * laboral.forma_vinculacion → buscar "Forma de vinculación:" en DATOS AUTORITATIVOS
  * rol_laboral.forma_integracion → buscar "Forma de integración:" en DATOS AUTORITATIVOS
  * empresa.contacto → buscar "Contacto empresa:" en DATOS AUTORITATIVOS
  * empresa.telefono → buscar "Teléfono empresa:" en DATOS AUTORITATIVOS
  * empresa.correo → buscar "Correo empresa:" en DATOS AUTORITATIVOS
  * empresa.direccion → buscar "Dirección empresa:" en DATOS AUTORITATIVOS
  * paciente.dominancia → buscar "Dominancia (CC_ checkbox):" en DATOS AUTORITATIVOS.
    Valores posibles: "Derecha", "Izquierda", "Ambidiestra". NO dejar en blanco si está disponible.
- Si el audio dice cargo X y el CR dice cargo Y, PREVALECE el CR (documento oficial).
- Si el audio menciona trabajos anteriores (historial laboral), NO usarlos para llenar empresa.nombre ni empresa.cargo. Solo para apreciacion_trabajador como historial previo.

REGLAS PARA historia_ocupacional:
- El PRIMER elemento es el trabajo MÁS ANTIGUO. El ÚLTIMO elemento es el empleo ACTUAL.
- Orden cronológico ASCENDENTE: de más antiguo a más reciente.
- "motivo_retiro" del empleo actual (último elemento): siempre "Actualmente".
- El campo laboral.cargo debe ser IGUAL a empresa.cargo.
- laboral.tareas, laboral.herramientas, laboral.horario: extraer del audio si el paciente describe su trabajo.
  Si no los menciona explícitamente, escribir "[FALTA: no mencionado en audio]".

REGLAS PARA fecha y género:
- consulta.fecha: SI aparece "Fecha valoración (CR): DD/MM/YYYY" en DATOS AUTORITATIVOS, úsalo EXACTAMENTE.
  Este es el campo más importante para el documento — NO lo dejes vacío ni uses fecha de Juan Carlos.
  Formato esperado: "DD de mes de YYYY" (ej: "19 de mayo de 2026").
- laboral.fecha_ingreso_empresa: copiar exactamente del campo "Fecha ingreso empresa" si aparece.
- laboral.antiguedad_empresa: copiar exactamente del campo "Antigüedad empresa" si aparece.
- historia_ocupacional: si aparece "Historia ocupacional (CC_):" en DATOS AUTORITATIVOS, usar esos datos
  como base (son del documento oficial de Sandra). Complementar con el audio si hay más información.
- GÉNERO del paciente: deducir del nombre. Si el nombre es femenino (Maribel, Rosa, Laura, María, etc.),
  usar género femenino en TODO el JSON:
  * concepto_desempeno: "La afiliada..." no "El afiliado..."
  * apreciacion_trabajador: usar "ella", "su desempeño", etc.
  * composicion_familiar: si hay esposo → "Esposo: nombre"; si hay esposa → "Esposa: nombre"
- Si los datos de historia_ocupacional en CC_ tienen 4 entradas, incluir las 4 en historia_ocupacional[].
  El VOI las mostrará en "Otros Oficios" si superan 2.

REGLAS COMPLEMENTARIAS CC_:
- consulta.concepto: Si hay "⭐ CONCEPTO INTEGRAL FINAL (CC_)" en AUTORITATIVOS, pon EXACTAMENTE el marcador "<<CC_CONCEPTO>>" en el campo "consulta.concepto". Python lo reemplazará con el texto real. NO copies el texto. Si NO hay concepto del CC_, genera un concepto clínico en máx 200 palabras.
- tratamiento_atel: Si hay "⭐ NOTAS MÉDICAS (CC_)" en AUTORITATIVOS, pon EXACTAMENTE el marcador "<<CC_NOTAS>>" en el campo "tratamiento_atel". Python lo reemplazará. NO copies el texto. Si no hay notas, poner "".
- paciente.nivel_educativo: usar el valor de "Nivel educativo (CC_ checkbox)" si está disponible.
- paciente.formacion_oficios: usar "Formación/oficios (CC_)" si está disponible.
- composicion_familiar: OBLIGATORIO. Si aparece "⭐ COMPOSICIÓN FAMILIAR (CC_)" en DATOS AUTORITATIVOS:
  * nucleo: copiar EXACTO 'composicion_familiar.nucleo'. "esposo" es masculino, NO cambiar a "esposa".
  * convivencia: copiar EXACTO 'composicion_familiar.convivencia' (texto "Vive con...").
  * sostenedor: copiar EXACTO 'composicion_familiar.sostenedor'. NO cambiar género.
  * ingreso_promedio: copiar EXACTO 'composicion_familiar.ingreso_promedio'. "6.00.000 pesos" ≠ "2.500.000 pesos". NO inventar cifra.
  NUNCA inventar composición familiar. Si no hay datos del CC_, dejar vacío y agregar a campos_faltantes.
- rol_laboral.sensorio_motor: usar "Rol laboral/componentes (CC_)" si está disponible.

REGLAS PRECISAS PARA areas_ocupacionales (Sección 8 VOI):
- NIVELES: "no dificultad"=lo hace sin problema | "dificultad leve"=lo hace con alguna molestia | "dificultad moderada"=dolor/limitación notable al hacerlo | "dificultad severa"=no puede sin ayuda | "dificultad completa"=totalmente dependiente
- IMPORTANTE: NO asumas "no dificultad" por defecto. Si el paciente menciona dolor/limitación/evitación → marca al menos "dificultad leve".
- Para CADA item de las 5 categorías, indica el nivel basado en lo que el paciente REPORTÓ. Si no hay info específica para un item, pon "n/a".
- Revisar las NOTAS MÉDICAS (CC_) y la transcripción buscando síntomas y limitaciones reportados.
- Mapear a áreas usando estas reglas:
  * "dolor al bañarse / refregarse / lavarse" → cuidado_personal["Lavarse"] = {"nivel": "dificultad moderada", "observacion": "Dificultad para refregarse"}
  * "dolor al cocinar / preparar alimentos / cocinar" → vida_domestica["Preparar comidas"] = {"nivel": "dificultad moderada", "observacion": "Al cocinar, preparar alimentos"}
  * "dolor al usar cubiertos / cortar alimentos / alimentarse" → cuidado_personal["Alimentarse"] = {"nivel": "dificultad leve", "observacion": "Al utilizar los cubiertos, al cortar los alimentos"}
  * "dolor al escribir / usar teclado / computador" → comunicacion["Escribir"] = {"nivel": "dificultad moderada", "observacion": "Al escribir, usar computador / teclado"}
  * "dolor al cargar / llevar objetos / levantar peso" → movilidad["Cargar objetos"] = {"nivel": "dificultad moderada", "observacion": "Al levantar peso o cargar objetos"}
  * "dolor al hacer oficio / aseo del hogar / barrer / trapear" → vida_domestica["Limpiar / Hacer oficio"] = {"nivel": "dificultad moderada", "observacion": "Al realizar labores domésticas o de aseo"}
- Cada valor puede ser string "nivel" O dict {"nivel": "...", "observacion": "..."}. Usar dict cuando hay observación específica.
- NO dejar areas_ocupacionales completamente vacío si las notas médicas reportan síntomas funcionales.
- NUNCA pongas TODOS los items en "no dificultad". Si el paciente menciona dolor en codos/manos/muñecas, al menos "dificultad leve" aplica a items de mano/brazo.
- orientacion_ocupacional: OBLIGATORIO completar. Si paciente FEMENINA: "La afiliada puede realizar las actividades laborales, teniendo en cuenta las recomendaciones médico-ocupacionales." Si masculino: "El afiliado puede realizar...". NUNCA dejar vacío.
"""


def sintetizar(transcripcion: Dict, datos_portales: Dict, notas_crudas: List, formatos_subidos: List, paciente_cc: str) -> Dict:
    """Llama a lote_worker --tipo sintetizar con el contexto cruzado."""
    import time as _time
    contexto = _componer_contexto(transcripcion, datos_portales, notas_crudas, formatos_subidos, paciente_cc)
    _log(f"Contexto compuesto: {len(contexto)} chars")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
        tmp.write(contexto)
        contexto_file = tmp.name

    modelo = os.getenv("LLM_MODEL_SINTESIS", "deepseek-v4-pro")
    MAX_INTENTOS = 3
    ultimo_error = None
    resultado = {}
    respuesta_texto = ""

    for intento in range(MAX_INTENTOS):
        if intento > 0:
            delay = 30 * intento
            _log(f"Reintento {intento+1}/{MAX_INTENTOS} en {delay}s...")
            _time.sleep(delay)
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "backend.lote_worker",
                 "--tipo", "sintetizar",
                 "--modelo", modelo,
                 "--mensaje", PROMPT_USUARIO_SINTESIS,
                 "--contexto-file", contexto_file,
                 "--cc", paciente_cc],
                capture_output=True, text=True,
                timeout=900,
                cwd=str(Path(__file__).parent.parent.parent),
            )
        except subprocess.TimeoutExpired:
            ultimo_error = "Timeout del subprocess de síntesis (>900s)"
            _log(f"INTENTO {intento+1}: {ultimo_error}")
            continue

        if proc.returncode != 0:
            ultimo_error = proc.stderr[:500] or f"lote_worker exit {proc.returncode}"
            _log(f"INTENTO {intento+1}: lote_worker falló: {ultimo_error[:200]}")
            continue

        try:
            resultado = json.loads(proc.stdout)
        except json.JSONDecodeError:
            ultimo_error = f"stdout no es JSON: {proc.stdout[:200]}"
            _log(f"INTENTO {intento+1}: {ultimo_error}")
            continue

        if not resultado.get("ok"):
            ultimo_error = resultado.get("error", "lote_worker ok=False sin mensaje")
            _log(f"INTENTO {intento+1}: {ultimo_error}")
            continue

        respuesta_texto = resultado.get("respuesta", "")
        if not respuesta_texto:
            ultimo_error = "respuesta_texto vacía"
            _log(f"INTENTO {intento+1}: {ultimo_error}")
            continue

        # Llegamos aquí: hay respuesta, intentar extraer JSON
        break
    else:
        # Todos los intentos fallaron
        try:
            os.unlink(contexto_file)
        except Exception:
            pass
        return {"ok": False, "error": f"Síntesis falló tras {MAX_INTENTOS} intentos: {ultimo_error}"}

    try:
        os.unlink(contexto_file)
    except Exception as e:
        _log(f"No se pudo eliminar temp: {e}")

    _log(f"Síntesis OK en intento {intento+1}: {resultado.get('tokens', {})} tokens en {resultado.get('tiempo_s')}s")

    import re
    datos_clinicos = None
    # Intento 1: bloque ```json ... ``` (principal)
    match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', respuesta_texto, re.IGNORECASE)
    if match:
        try:
            datos_clinicos = json.loads(match.group(1))
        except json.JSONDecodeError as e:
            _log(f"JSON en bloque backtick invalido: {e}")

    # Intento 2: JSON raw (sin backticks) — buscar el bloque { ... } más grande
    if datos_clinicos is None:
        primer_llave = respuesta_texto.find('{')
        ultimo_cierre = respuesta_texto.rfind('}')
        if primer_llave != -1 and ultimo_cierre > primer_llave:
            candidato = respuesta_texto[primer_llave:ultimo_cierre+1]
            try:
                datos_clinicos = json.loads(candidato)
                _log(f"JSON extraido sin backtick wrapper ({len(candidato)} chars)")
            except json.JSONDecodeError:
                _log("Fallback JSON también inválido")

    # Intento 3: JSON truncado — intentar completar con llave de cierre
    if datos_clinicos is None:
        try:
            primer_llave = respuesta_texto.find('{')
            if primer_llave != -1:
                candidato_trunc = respuesta_texto[primer_llave:]
                # Contar llaves abiertas y cerradas para saber cuántas } faltan
                abiertas = candidato_trunc.count('{')
                cerradas = candidato_trunc.count('}')
                faltantes = abiertas - cerradas
                if 0 < faltantes <= 20:
                    # Truncar en el último campo completo (buscar última coma o valor completo)
                    # Buscar la última posición con un string cerrado correctamente
                    ultimo_ok = max(
                        candidato_trunc.rfind('",'),
                        candidato_trunc.rfind('",\n'),
                        candidato_trunc.rfind('],'),
                    )
                    if ultimo_ok > primer_llave:
                        reparado = candidato_trunc[:ultimo_ok + 1] + "}" * faltantes
                        datos_clinicos = json.loads(reparado)
                        _log(f"JSON reparado (faltaban {faltantes} llaves de cierre)")
                        datos_clinicos.setdefault("_meta", {})["json_reparado"] = True
        except Exception:
            pass

    if datos_clinicos is None or not isinstance(datos_clinicos, dict) or not datos_clinicos:
        cruda_preview = respuesta_texto[:300].replace('\n', ' ')
        return {
            "ok": False,
            "error": f"LLM no devolvio JSON clinico valido. Preview: {cruda_preview}",
            "respuesta_cruda": respuesta_texto[:1000],
            "tokens": resultado.get("tokens", {}),
        }

    # ─── INYECCIÓN POST-SÍNTESIS: reemplazar marcadores con texto verbatim del CC_ ───
    # El LLM usa <<CC_NOTAS>> y <<CC_CONCEPTO>> como marcadores para no agotar max_tokens.
    # Python extrae los textos reales del CC_ e inyecta aquí.
    try:
        datos_de_notas_inj = _extraer_datos_notas(notas_crudas) if notas_crudas else {}
        if datos_de_notas_inj.get("tratamiento_atel_raw"):
            trat_actual = str(datos_clinicos.get("tratamiento_atel") or "")
            if not trat_actual or "<<CC_NOTAS>>" in trat_actual or trat_actual in ("[SIN NOTAS EN CC_]", "[FALTA]", ""):
                datos_clinicos["tratamiento_atel"] = datos_de_notas_inj["tratamiento_atel_raw"]
                _log("Inyectado tratamiento_atel desde CC_ (marcador reemplazado)")
        if datos_de_notas_inj.get("concepto_integral_final"):
            consulta = datos_clinicos.setdefault("consulta", {})
            concepto_actual = str(consulta.get("concepto") or "")
            if not concepto_actual or "<<CC_CONCEPTO>>" in concepto_actual:
                consulta["concepto"] = datos_de_notas_inj["concepto_integral_final"]
                _log("Inyectado consulta.concepto desde CC_ (marcador reemplazado)")
    except Exception as e_inj:
        _log(f"WARN: inyección post-síntesis falló (no crítico): {e_inj}")

    # ─── POST-PROCESAMIENTO: verificar que tratamiento_atel tenga MULTIPLES fechas ───
    try:
        trat = str(datos_clinicos.get("tratamiento_atel") or "")
        if trat:
            import re as _re_trat
            fechas_trat = _re_trat.findall(r'\b(\d{2}/\d{2}/\d{4})\b', trat)
            if len(fechas_trat) <= 1:
                # Buscar en notas crudas si hay mas consultas
                if notas_crudas:
                    for nc in notas_crudas:
                        nc_text = str(nc) if isinstance(nc, str) else json.dumps(nc)
                        fechas_nc = _re_trat.findall(r'\b(\d{2}/\d{2}/\d{4})\b', nc_text)
                        especialidades_nc = _re_trat.findall(r'(FISIATRIA|MEDICINA LABORAL|ELECTROMIOGRAF)', nc_text, _re_trat.IGNORECASE)
                        if len(fechas_nc) > 1 and len(especialidades_nc) > 0:
                            # Hay mas datos en notas crudas, concatenar
                            datos_clinicos["tratamiento_atel_notas_extra"] = True
                            _log(f"ADVERTENCIA: tratamiento_atel tiene solo {len(fechas_trat)} fecha(s), "
                                 f"pero notas crudas tienen {len(fechas_nc)} fechas con {len(especialidades_nc)} especialidades")
                            break
    except Exception as e_trat:
        _log(f"WARN: post-procesamiento tratamiento_atel falló: {e_trat}")

    def _limpiar_concepto(concepto: str) -> str:
        """Elimina texto de footer/registro que el LLM a veces incluye en el concepto."""
        if not concepto:
            return concepto
        marcadores = [
            "8. | observacion",
            "8. | observación",
            "9. | registro",
            "insertar firma",
            "equipo de rehabilitacion",
            "equipo de rehabilitación",
            "rehabilitacion integral laboral",
            "rehabilitación integral laboral",
            "rilo sas",
            "medico laboral",
            "médico laboral",
            "fisiatra especialista",
            "terapeuta especialista",
            "elaboro",
            "elaboró",
            "revision por proveedor",
            "revisión por proveedor"
        ]
        concepto_lower = concepto.lower()
        min_idx = len(concepto)
        for marcador in marcadores:
            idx = concepto_lower.find(marcador)
            if idx != -1 and idx < min_idx:
                min_idx = idx
        if min_idx < len(concepto):
            concepto = concepto[:min_idx].strip()
        return concepto.strip()

    # Sanitizar el concepto clínico
    if "consulta" in datos_clinicos and "concepto" in datos_clinicos["consulta"]:
        datos_clinicos["consulta"]["concepto"] = _limpiar_concepto(datos_clinicos["consulta"]["concepto"])

    paciente = datos_clinicos.get("paciente", {}) or {}
    siniestro = datos_clinicos.get("siniestro", {}) or {}
    doc = (paciente.get("documento") or "").strip()
    sin = (siniestro.get("id_siniestro") or "").strip()
    if not doc:
        return {
            "ok": False,
            "error": "Falta documento (CC) del paciente en datos_clinicos",
            "datos_clinicos": datos_clinicos,
            "respuesta_cruda": respuesta_texto[:500],
            "tokens": resultado.get("tokens", {}),
        }
    if not sin:
        datos_clinicos.setdefault("siniestro", {})["id_siniestro"] = "[VERIFICAR EN PORTAL]"
        _log("Advertencia: siniestro no encontrado - marcado como pendiente de verificacion")

    if datos_portales:
        medi_portales = datos_portales.get("medifolios", {})
        apellido_portal = medi_portales.get("apellido1", "").strip().upper()
        nombre_llm = (datos_clinicos.get("paciente", {}).get("nombre") or "").upper()

        if apellido_portal and apellido_portal not in nombre_llm:
            _log(f"ADVERTENCIA: apellido portal '{apellido_portal}' no encontrado en nombre LLM '{nombre_llm}'")
            nombre_portal = (
                " ".join(filter(None, [
                    medi_portales.get("nombre1",""), medi_portales.get("nombre2",""),
                    medi_portales.get("apellido1",""), medi_portales.get("apellido2","")
                ])).strip()
            )
            if nombre_portal:
                datos_clinicos["paciente"]["nombre"] = nombre_portal
                datos_clinicos.setdefault("_meta", {}).setdefault("correcciones_portal", []).append(
                    f"nombre: LLM={nombre_llm} -> portal={nombre_portal}"
                )

    # ─── GUARDAR datos_clinicos como archivo canónico del paciente ───
    # Esto permite que /api/pacientes/{cc} encuentre datos ricos incluso cuando
    # los portales fallaron (que es el caso normal para pacientes Medifolios ausentes)
    try:
        storage = Path(os.getenv("STORAGE_DIR", "./storage"))
        data_dir = storage / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        save_path = data_dir / f"{doc}-sintetizado.json"
        datos_a_guardar = dict(datos_clinicos)
        datos_a_guardar["_meta"] = {
            "fuente": "sintetizado_llm",
            "guardado_en": datetime.now().isoformat(),
            "paciente_cc": doc,
        }
        if datos_portales:
            datos_a_guardar["_portales"] = {
                "medifolios": datos_portales.get("medifolios", {}),
                "positiva": datos_portales.get("positiva", {}),
            }
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(datos_a_guardar, f, ensure_ascii=False, indent=2)
        _log(f"datos_clinicos guardados → {save_path.name}")
    except Exception as e:
        _log(f"WARN: no se pudo guardar datos_clinicos: {e}")

    return {
        "ok": True,
        "respuesta_completa": respuesta_texto,
        "datos_clinicos": datos_clinicos,
        "tokens": resultado.get("tokens", {}),
        "tiempo_s": resultado.get("tiempo_s"),
    }


def ejecutar(transcripcion: Dict, datos_portales: Dict, notas_crudas: List, formatos_subidos: List, paciente_cc: str) -> dict:
    return sintetizar(transcripcion, datos_portales, notas_crudas, formatos_subidos, paciente_cc)
