"""Prueba Carta de Recomendaciones - JUAN CARLOS DURAN NARVAEZ"""
import sys
sys.path.insert(0, "/root/fisioterapia/backend")

import doc_generator
# Desactivar conversion PDF para prueba rapida
original_convertir = doc_generator._convertir_a_pdf
doc_generator._convertir_a_pdf = lambda x: None

from doc_generator import generar_carta_recomendaciones

datos = {
    "paciente": {
        "nombre": "Juan Carlos Duran Narvaez",
        "documento": "193143688",
    },
    "empresa": {
        "nombre": "BOLIVARIANA DE MINERALES Y CIA LTDA",
        "contacto": "Ingrid Johan Vargas Reyes",
        "cargo_contacto": "jefe Talento Humano",
        "direccion": "KM 2 VIA NEIVA - PALERMO",
        "telefono": "3143009418",
    },
    "siniestro": {
        "tipo": "Accidente de trabajo",
        "fecha_evento": "02/03/2026",
        "segmento_lesionado": "Mano derecha y 4 dedo mano derecha",
        "incapacitado": True,
        "fecha_ultima_incapacidad": "Sin datos",
    },
    "laboral": {
        "cargo": "Obrero de tratamiento roca",
    },
    "consulta": {
        "fecha": "09 de abril de 2026",
        "concepto": (
            "Una vez realizada la Valoración de desempeño ocupacional al afiliado del asunto, "
            "y analizados los requerimientos del cargo de Obrero de tratamiento roca, "
            "seguimiento realizado el 02/03/2026, nos permitimos manifestar que el asegurado "
            "puede continuar desempeñando las tareas en el cargo mencionado, así como aquellas "
            "tareas que consideren asignar siempre y cuando estás le permitan garantizar el "
            "cumplimiento de las recomendaciones médico-ocupacionales que a continuación se "
            "mencionan. Estas se emiten con el objetivo que el afiliado finalice adecuadamente "
            "su proceso de rehabilitación, evitando así, alteraciones del estado de salud "
            "asociadas y favoreciendo el desempeño laboral. Lo anterior de conformidad con los "
            "artículos 2°, 4° y 8° de la Ley 776 de 2002."
        ),
    },
    "rehabilitacion": {
        "tiempo_vigencia": "3 meses",
        "forma_integracion": "Reintegro con modificaciones",
    },
    "recomendaciones": {
        "tareas": [
            "Desatasca las piedras de la máquina trituradora con un gancho de hierro para facilitar que la maquina triture o parta las piedras",
            "Empaca en bultos de piedra de 50 kilos",
            "Llena el bulto de piedra fina",
            "Cose los bultos de piedra",
            "Traslada los bultos de piedra",
        ],
        "trabajador": [
            "Puede desempeñarlas o con restricciones",
            "Realizar pausas activas por cada (1) hora de trabajo continuo durante cinco (5) a (10) minutos, realizando los ejercicios de movilidad articular y estiramientos con mayor énfasis en mano derecha.",
            "Evitar utilizar herramientas de impacto; no operar martillos neumáticos, picas, ganchos de hierro o cualquier herramienta que genere golpes secos. Ya que puede generar dolor y sobreesfuerzo de la articulación.",
            "Esta limitado la manipulación de maquinaria de trituración o herramientas eléctricas vibratorias ya que puede afectar la recuperación.",
            "Se recomienda que el trabajador se enfoque en el control y monitoreo de bandas transportadoras o inspección visual de calidad, donde no se requiera fuerza de carga.",
            "Es obligatorio la utilización de los EPP al realizar las actividades laborales.",
            "Al realizar el llenado del bulto evita sostenerlo con la mano derecha mientras cae la piedra utiliza un soporte que mantenga el bulto abierto para evitar realizar fuerza de tracción con los dedos.",
            "Al mover el bulto, nunca lo levantes metiendo los dedos en los pliegues. Usa la palma de la mano y mantén el dedo anular derecho extendido y fuera de la zona de presión.",
            "Al cargar material o sacos de piedra haga uso de ayudas mecánicas o carretillas.",
            "Si utiliza palas al llenar el bulto, se recomienda un mango grueso ya que reduce la tensión y el esfuerzo de las manos y los dedos.",
            "Al cargar sacos de piedra utiliza una adecuada postura manteniendo la espalda recta y dobla rodilla y no espalda. Esto evitará sobreesfuerzo de columna y miembros superiores.",
            "Al manipular los sacos para coserlo se recomienda el uso de dediles sobre el cuarto dedo para protegerlo de presiones y alternar la tarea con las 2 manos.",
            "Implemente el autocuidado en la realización de las diferentes tareas y en todas las actividades laborales, extralaborales y lúdicas (actividades del hogar, deportivas y de tiempo libre) siguiendo las recomendaciones dadas por los profesionales tratantes durante todo el proceso de rehabilitación.",
        ],
        "empresa_texto": (
            "- Participar del proceso de rehabilitación integral, para lo cual debe informar al funcionario por escrito las recomendaciones laborales que debe tener en cuenta, conforme a su capacidad laboral actual, con el fin de llevar a cabo el seguimiento y cumplimiento de las mismas.\n"
            "- Permitir la asistencia a los controles médicos programados para realizar el respectivo seguimiento del caso y coordinar horario de IPS con requerimientos productivos.\n"
            "- Las recomendaciones emitidas deben implementarse por tres (3) meses tanto en actividades laborales como extralaborales."
        ),
    },
}

print("\U0001f9ea Generando Carta de Recomendaciones...")
docx_path = generar_carta_recomendaciones(datos, output_name="recomendaciones-193143688-2026-04-09")
print(f"\u2705 DOCX: {docx_path}")
from pathlib import Path
print(f"   Tamaño: {Path(docx_path).stat().st_size/1024:.0f} KB")

doc_generator._convertir_a_pdf = original_convertir
