"""Prueba Carta de Medidas Preventivas - OLGA LUCIA PAREDES ORTIZ"""
import sys
sys.path.insert(0, "/root/fisioterapia/backend")

import doc_generator
original_convertir = doc_generator._convertir_a_pdf
doc_generator._convertir_a_pdf = lambda x: None

from doc_generator import generar_carta_medidas

datos = {
    "paciente": {
        "nombre": "OLGA LUCIA PAREDES ORTIZ",
        "documento": "40.776.172",
    },
    "empresa": {
        "nombre": "FISCALÍA GENERAL DE LA NACIÓN HUILA",
        "contacto": "Dra. Diana Cristina Sánchez Pama",
        "cargo_contacto": "Profesional de seguridad y salud en el trabajo",
        "direccion": "Carrera 21ª # 26-65 Sur",
        "telefono": "3223089360",
        "correo": "dianac.sanchez@fiscalia.gov.co",
    },
    "siniestro": {
        "id_siniestro": "423022266",
        "fecha_evento": "12/08/2022",
    },
    "consulta": {
        "fecha": "2026-03-26",
        "cuerpo_carta": (
            "Una vez realizada la visita al puesto de trabajo de la servidora en mención, "
            "quien presenta enfermedad laboral, siniestro 423022266, con fecha 12/08/2022, "
            "posterior al seguimiento en cuanto a la evolución del proceso y analizados los "
            "requerimientos del Cargo de Auxiliar I en la evaluación al puesto de trabajo "
            "realizada el día 26 de marzo de 2026, nos permitimos manifestar que puede "
            "continuar desempeñándose en dicho cargo, realizando el seguimiento y cumplimiento "
            "de las medidas que a continuación se mencionan por un periodo de 12 meses, con "
            "el fin de prevenir agravamiento de su estado de salud, evitar sintomatología y "
            "favorecer su rehabilitación integral, lo anterior de conformidad con los "
            "artículos 2°, 4° y 8° de la Ley 776 de 2002."
        ),
    },
    "recomendaciones": {
        "trabajador_texto": (
            "- Realizar pausas activas por cada (1) hora de trabajo continuo durante cinco (5), (7) minutos, realizando los ejercicios de movilidad articular y estiramientos en miembros superiores.\n"
            "- Al ejecutar actividades de registro de correspondencia y sobres en las plataformas haciendo uso del sistema - videoterminal, debe mantener la cabeza y el cuello en posición recta, los ojos alineados con el borde superior del monitor, espalda recta sobre el espaldar de la silla, brazos formando ángulo de 90° con respecto al escritorio, manos rectas y no dobladas, piernas y cadera doblados formando un ángulo de 90°, pies sobre el descansa pies y/o en el suelo. Así mismo tenga en cuenta digitar por un tiempo máximo de 1 hora con el fin de evitar sobrecargas a nivel muscular y articular de los segmentos afectados.\n"
            "- Se recomienda realizar las tareas de registro de correspondencia y sobres en las plataformas a un ritmo tolerable y de acuerdo con la capacidad funcional, procurando mantener el confort físico y prevenir molestias en la articulación de los codos y muñecas. Para ello, es beneficioso alternar estas actividades con otras como desplazamientos cortos dentro del área de trabajo, pausas activas, organización de documentos u otras labores que permitan variar la postura.\n"
            "- Al manipular el teclado, coloque los brazos formando un ángulo de 90°, ejerza poca fuerza al realizar actividades de digitar, no exceder más de una (1) hora continua, realizar pausa y retomar.\n"
            "- Tenga en cuenta que, para el uso de elementos de trabajo como grapadora y tijeras, se recomienda manipularlos en una superficie de trabajo estable y no en el aire, realizando la fuerza y el apoyo con las dos manos de manera gradual y firme. Si es posible, utilizar la mano derecha para estabilizar y la izquierda para presionar (o viceversa), repartiendo la carga de trabajo, así evitara generar sobreesfuerzo en sus miembros superiores.\n"
            "- Las actividades deben ejecutarse a tolerancia, respetando los límites de movilidad y fuerza.\n"
            "- Implemente el autocuidado en la realización de las diferentes tareas y en todas las actividades laborales, extralaborales y lúdicas (actividades del hogar, deportivas y de tiempo libre) siguiendo las recomendaciones."
        ),
        "tareas_texto": (
            "Al realizar tarea de radicación de documentos, uso del computador: recuerde tener en cuenta:\n"
            "- Al adoptar una postura sedente, ubicar la silla frente al escritorio, con la espalda apoyada cómodamente en el espaldar de esta, cadera y rodillas flexionadas formando un ángulo de 90°, pies apoyados firmemente sobre el piso y/o descansa pies.\n"
            "- Utilizar un teclado independiente del resto del equipo.\n"
            "- El borde superior debe estar a la altura de los ojos.\n"
            "- Al manipular el mouse y el teclado verifique que su antebrazo y mano estén alineados y apoyados en la superficie de la mesa.\n"
            "- Ajustar la altura de la silla para que coincida la altura del codo a 90 grados de flexión y con la altura de la superficie de trabajo, se debe observar que los miembros inferiores estén alineados (en ángulos de 90 grados en cadera, rodilla y cuello de pie).\n"
            "- Se recomienda alternar el uso del mouse constantemente, para utilizar las dos manos durante la jornada laboral.\n"
            "- Evite mantener los antebrazos y muñecas suspendidas en el aire sin ningún apoyo.\n"
            "- Ubicar los elementos de trabajo (lapicero, documentos, etc.) tanto en lado derecho como en el lado izquierdo con el fin de distribuir las labores y cargas que se generan con la manipulación de estos.\n"
            "- Al hacer uso del teclado, ubiqué las muñecas de forma neutra sin ningún tipo de apoyo debajo de las mismas, evité movimientos repetidos de flexo-extensión (arriba-abajo) y desviaciones radio-cubitales (adentro-afuera) por más de una (1) hora de trabajo continuo.\n"
            "- En el manejo del mouse y en la acción de digitar realice movimientos del hombro, brazo y mano en bloque, es decir todo el brazo, evite en lo posible ejecutar de forma repetitiva movimientos flexo-extensión (arriba-abajo) y desviaciones radio-cubitales (adentro-afuera) por más de una (1) hora de trabajo continuo de con el fin de evitar la fatiga muscular e incremento de sintomatología.\n"
            "- Al tomar la correspondencia o sobres, no la sujetes solo con los dedos. Usa la palma completa de la mano y mantén el objeto pegado a tu cuerpo.\n"
            "- Evitar alcanzar archivos por encima del nivel de tus hombros.\n"
            "- Al realizar la impresión realícela en posición a bípeda para evitar sobreesfuerzos de miembros superiores.\n"
            "- Realice el recorte y el uso de la cinta a un ritmo autoadministrado y después de 15 minutos realice una micro pausa, para permitir el descanso después de la actividad.\n"
            "- Al poner la cinta en las guías para pegarlas en el sobre presiónela con la palma de la mano extendida o con la base de la mano (zona tenar) y no con la punta de los dedos.\n"
            "- Siempre dobla el último centímetro de la cinta sobre sí mismo para crear una pestaña. Esto te permite sujetar la cinta en el próximo uso.\n"
            "- Para cortar la cinta utiliza unas tijeras, sujeta la cinta con la mano izquierda (o la menos afectada) y realiza el corte con la derecha, manteniendo el codo pegado al cuerpo.\n"
            "- Sujeta el rollo de cinta contra tu costado o contra la mesa usando el antebrazo izquierdo (no la mano). Con la mano derecha, hala la cinta hacia adelante manteniendo la muñeca bloqueada (recta). El movimiento debe nacer del hombro.\n"
            "- Al colocar la cinta, usa el lomo de un bolígrafo grueso o una regla plástica para alisar la cinta sobre el papel. Si necesitas presionar, hazlo con la base de la palma de la mano (zona hipotenar), manteniendo los dedos relajados.\n"
            "- Al realizar el corte con tijeras la muñeca debe estar siempre alineada con el antebrazo. Evita realizar los cortes con la muñeca girada o doblada.\n"
            "- Si la servidora tiene la capacidad, debe intentar realizar cortes simples con la mano izquierda para dar descanso a la derecha y viceversa."
        ),
        "empresa_texto": (
            "- Participar del proceso de rehabilitación integral, informando a la servidora por escrito de las medidas que debe tener en cuenta, con el fin de poder llevar a cabo el seguimiento del cumplimiento de estas.\n"
            "- Brindar acompañamiento y seguimiento a las medidas emitidas desde el área de seguridad y salud en el trabajo.\n"
            "- Promover la realización de pausas activas cada dos horas por cinco a diez minutos y alternancia de actividades para la recuperación muscular y articular del segmento comprometido."
        ),
    },
    "rehabilitacion": {
        "nombre_revisor": "YAMILE M SUAREZ VARGAS",
    },
}

print("🧪 Generando Carta de Medidas Preventivas...")
docx_path = generar_carta_medidas(datos, output_name="medidas-40776172-2026-03-26")
print(f"✅ DOCX: {docx_path}")

from pathlib import Path
print(f"   Tamaño: {Path(docx_path).stat().st_size/1024:.0f} KB")

doc_generator._convertir_a_pdf = original_convertir
