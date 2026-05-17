"""Regenerar Cierre de Caso - v5 FINAL"""
import sys
sys.path.insert(0, "/root/fisioterapia/backend")

import doc_generator
original_convertir = doc_generator._convertir_a_pdf
doc_generator._convertir_a_pdf = lambda x: None

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
            "Control 30/04/2026:\n"
            "Paciente asiste a control, niega dolor, no limitación, asintomático. "
            "No trae Rx ordenada en consulta anterior."
        ),
        # DESCRIPCIÓN FURAT/FUREL — texto literal del FURAT (va entre ENFERMEDAD y EXAMEN)
        "descripcion_furat": (
            "DESCRIPCIÓN FURAT/FUREL: EL 2-3-2026 TUVO TRAUMA CONTUSO AL CAER UNA ROCA "
            "QUE FUE EXPULSADA POR UNA MAQUINA TRITURADORA DE ROCA, CAYENDO EN DORSO DE "
            "LA MANO DERECHA, PRESENTANDO HERIDA A NIVEL DE FALANGE DISTAL DEL 4° DEDO "
            "DE LA MANO DERECHA. MANEJADA CON DESBRIDAMIENTO DE HERIDA CON BORDES "
            "NECROTICOS Y EXPOSICION OSEA CON DAÑO PARCIAL DE MATRIZ UNGUEAL, "
            "REQUIRIENDO COLGAJO DE PIEL. RECIBIO MANEJO CON CEFALEXINA QUE TERMINO "
            "HACE 4 DIAS, PERO HOY NOTO PRESENCIA DE SECRECION PURULENTA POR HERIDA "
            "SUTURADA. 30/04/2026 PACIENTE QUIEN ASISTE A CONTROL NIEGA DOLOR, "
            "NO LIMITACION, ASINTOMATICO. NO TRAE RX ORDENADA EN CONSULTA ANTERIOR."
        ),
        "examen_fisico": (
            "Paciente ingresa por sus propios medios. Lateralidad: diestro.\n"
            "GONIOMETRIA RANGO DE MOVILIDAD PASIVO EN 4° DEDO DE MANO DERECHA:\n"
            "METACARPOFALANGICA FLEXION 90°, EXTENSION: 45°.\n"
            "INTERFALANGICA PROXIMAL FLEXION 110°, EXTENSION: 0°.\n"
            "INTERFALANGICA DISTAL FLEXION 90°, EXTENSION: 0°.\n"
            "Cicatriz a nivel del borde radial del tercio distal del 4° dedo mano "
            "derecha en buen estado, sin dolor. Neurológico: fuerza, sensibilidad y "
            "reflejos conservados."
        ),
        "analisis_recomendaciones": (
            "PACIENTE QUE TUVO TRAUMA CONTUSO AL CAER UNA ROCA EXPULSADA POR MAQUINA "
            "TRITURADORA EN DORSO DE MANO DERECHA CON HERIDA A NIVEL DE FALANGE DISTAL "
            "DE 4° DEDO DE MANO DERECHA, MANEJADA CON DESBRIDAMIENTO Y COLGAJO DE PIEL. "
            "PACIENTE ASINTOMATICO, SIN DOLOR, SIN LIMITACION FUNCIONAL. "
            "SE CONSIDERA MAXIMA REHABILITACION. ALTA POR FISIATRIA."
        ),
        "plan_manejo": "ALTA POR FISIATRIA.",
    },
    "rehabilitacion": {
        "forma_integracion": "Reintegro laboral sin modificaciones",
        "tiempo_vigencia": "3 meses",
        "actividades_funcional": "Medicina laboral, Fisiatría",
        "actividades_ocupacional": "Valoración ocupacional, Carta de recomendaciones, Cierre de caso",
        "obstaculos": "Ninguno frente al caso.",
        "observaciones": "Ninguna frente al caso",
        "concepto_integral": (
            "Afiliado de 35 años, quien ingresa al consultorio caminando por sus propios "
            "medios. A la valoración del desempeño ocupacional se encontró sin dificultad "
            "en procesos cognitivos, pensamiento lógico y coherente, orientado en tiempo, "
            "lugar y espacio.\n"
            "Accidente de trabajo el 02/03/2026. Diagnósticos: S611 HERIDA DEL CUARTO "
            "DEDO DE LA MANO DERECHA, S601 CONTUSIÓN DEL CUARTO DEDO DE LA MANO DERECHA, "
            "S626 FRACTURA DE LA FALANGE DISTAL DEL CUARTO DEDO DE LA MANO DERECHA.\n"
            "Cargo: Obrero de tratamiento roca. Funciones: desatasca las piedras de la "
            "máquina trituradora con gancho de hierro, empaca en bultos de 50 kg, llena "
            "bultos de piedra fina, los pasa a otro compañero para coser y transportar. "
            "Producción: 40 a 50 toneladas equivalente a 800-1000 bultos (materia prima "
            "de fertilizante).\n"
            "Componentes del desempeño:\n"
            "Sensorio-motor: Dificultad para manejo de herramientas, sostener y realizar "
            "agarres con la mano y el 4° dedo mano derecha. En actividades de la vida "
            "diaria evita usar el 4° dedo para no sentir dolor.\n"
            "Psicológico: Desmotivado por el dolor, teme ser excluido de sus labores.\n"
            "Social: Sin dificultad social. En lo familiar se ha visto afectado por "
            "disminución del salario durante la incapacidad.\n"
            "Fisiatría da de alta por no dolor y no limitación funcional — máxima "
            "rehabilitación alcanzada. Se concluye que el trabajador puede realizar "
            "las actividades del cargo teniendo en cuenta las recomendaciones laborales."
        ),
    },
}

print("🧪 Generando Cierre de Caso v5...")
docx_path = generar_cierre_caso(datos, output_name="cierre-1193143688-2026-05-01")
print(f"✅ DOCX: {docx_path}")

from pathlib import Path
size_kb = Path(docx_path).stat().st_size / 1024
print(f"   Tamaño: {size_kb:.0f} KB")

doc_generator._convertir_a_pdf = original_convertir
