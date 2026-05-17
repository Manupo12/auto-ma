"""
Prueba de generación — Cierre de Caso con datos reales
JUAN CARLOS DURAN NARVAEZ
"""
import sys
sys.path.insert(0, "/root/fisioterapia/backend")

from doc_generator import generar_cierre_caso

datos = {
    "paciente": {
        "nombre": "JUAN CARLOS DURAN NARVAEZ",
        "documento": "1193143688",
        "fecha_nacimiento": "08/03/1991",
        "edad": 35,
        "dominancia": "Izquierda",
        "estado_civil": "Casado",
        "nivel_educativo": "Bachillerato: vocacional 9°",
        "telefono": "3027218147",
        "direccion": "Calle 1 H No 24-14 Barrio Alfonso López",
        "eps_ips": "Famisanar",
        "afp": "Protección",
    },
    "empresa": {
        "nombre": "BOLIVARIANA DE MINERALES Y CIA LTDA",
        "nit": "860517272",
        "contacto": "Ingrid Johan Vargas Reyes",
        "cargo_contacto": "Jefe Talento Humano",
        "correo": "bolivarianamineralesgh@gmail.com",
        "telefono": "3143009418",
        "direccion": "KM 2 VIA NEIVA - PALERMO",
    },
    "laboral": {
        "cargo": "Obrero de tratamiento roca",
        "area": "Operativo",
        "fecha_ingreso_cargo": "16/12/2024",
        "antiguedad_cargo": "1 año y 4 meses aprox.",
        "antiguedad_empresa": "1 año y 4 meses aprox.",
        "vinculacion": "Término Fijo",
    },
    "siniestro": {
        "id_siniestro": "503463870",
        "tipo": "Accidente de trabajo",
        "fecha_evento": "02/03/2026",
        "segmento_lesionado": "4° dedo mano derecha",
        "diagnosticos": (
            "S611 HERIDA DEL CUARTO DEDO DE LA MANO DERECHA\n"
            "S601 CONTUSIÓN DEL CUARTO DEDO DE LA MANO DERECHA\n"
            "S626 FRACTURA DE LA FALANGE DISTAL DEL CUARTO DEDO DE LA MANO DERECHA"
        ),
        "tiempo_incapacidad": "Sin registro",
        "ultimo_dia_incapacidad": "",
        "incapacitado": False,
    },
    "consulta": {
        "fecha": "2026-05-01",
        "motivo_consulta": (
            "El 2/3/2026 tuvo trauma contuso al caer una roca expulsada por una máquina "
            "trituradora, cayendo en el dorso de la mano derecha. Presentó herida a nivel "
            "de falange distal del 4° dedo, manejada con desbridamiento por presencia de "
            "herida con bordes necróticos y exposición ósea con daño parcial de matriz "
            "ungueal, requiriendo colgajo de piel. Recibió manejo con cefalexina."
        ),
        "enfermedad_actual": (
            "Control 30/04/2026: Paciente asiste a control, niega dolor, no limitación, "
            "asintomático. No trae Rx ordenada en consulta anterior."
        ),
        "examen_fisico": (
            "Paciente ingresa por sus propios medios. Lateralidad: diestro.\n"
            "Gonimetría — Rango de movilidad pasivo en 4° dedo mano derecha:\n"
            "• Metacarpofalángica: flexión 90°, extensión 45°\n"
            "• Interfalángica proximal: flexión 110°, extensión 0°\n"
            "• Interfalángica distal: flexión 90°, extensión 0°\n"
            "Cicatriz a nivel del borde radial del tercio distal del 4° dedo mano "
            "derecha en buen estado, sin dolor. Neurológico: fuerza, sensibilidad y "
            "reflejos conservados."
        ),
    },
    "rehabilitacion": {
        "forma_integracion": "Reintegro laboral sin modificaciones",
        "tiempo_vigencia": "3 meses",
        "actividades_funcional": "Medicina laboral, Fisiatría",
        "actividades_ocupacional": "Valoración ocupacional, Carta de recomendaciones, Cierre de caso",
        "obstaculos": "Ninguno frente al caso.",
        "observaciones": "Ninguna frente al caso",
        "concepto_integral": (
            "Afiliado de 35 años, ingresa al consultorio caminando por sus propios medios. "
            "A la valoración del desempeño ocupacional se encontró sin dificultad en procesos "
            "cognitivos, pensamiento lógico y coherente, orientado en tiempo, lugar y espacio.\n"
            "Accidente de trabajo el 02/03/2026. Diagnósticos: S611, S601, S626 (herida, "
            "contusión y fractura de falange distal del 4° dedo mano derecha).\n"
            "Cargo: Obrero de tratamiento roca. Funciones: desatasca las piedras de la máquina "
            "trituradora con gancho de hierro, empaca en bultos de 50 kg, llena bultos de "
            "piedra fina, los pasa a otro compañero para coser y transportar. Producción: "
            "40 a 50 toneladas equivalente a 800-1000 bultos (materia prima de fertilizante).\n"
            "Componentes del desempeño:\n"
            "• Sensorio-motor: Dificultad para manejo de herramientas, sostener y realizar "
            "agarres con la mano y el 4° dedo mano derecha. En actividades de la vida diaria "
            "evita usar el 4° dedo para no sentir dolor.\n"
            "• Psicológico: Desmotivado por el dolor, teme ser excluido de sus labores.\n"
            "• Social: Sin dificultad social. En lo familiar se ha visto afectado por "
            "disminución del salario durante la incapacidad.\n"
            "Fisiatría da de alta por no dolor y no limitación funcional — máxima rehabilitación "
            "alcanzada. Se concluye que el trabajador puede realizar las actividades del cargo "
            "teniendo en cuenta las recomendaciones laborales."
        ),
    },
}

print("🧪 Generando Cierre de Caso para JUAN CARLOS DURAN NARVAEZ...")
print(f"   Datos: {len(datos['paciente'])} campos paciente, {len(datos['empresa'])} empresa")
print(f"   Diagnósticos: 3 códigos CIE-10")
print()

try:
    docx_path = generar_cierre_caso(datos, output_name="cierre-1193143688-2026-05-01")
    print(f"✅ DOCX: {docx_path}")
    
    from pathlib import Path
    pdf_path = Path("/root/fisioterapia/storage/pdfs") / (Path(docx_path).stem + ".pdf")
    if pdf_path.exists():
        print(f"✅ PDF:  {pdf_path}")
    else:
        print(f"⚠️  PDF no encontrado")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
