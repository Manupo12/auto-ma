"""Prueba de Trabajo - LAURA MARIA CARDONA ZAPATA"""
import sys
sys.path.insert(0, "/root/fisioterapia/backend")
import doc_generator
original_convertir = doc_generator._convertir_a_pdf
doc_generator._convertir_a_pdf = lambda x: None
from doc_generator import generar_prueba_trabajo

datos = {
    "paciente": {
        "nombre": "LAURA MARIA CARDONA ZAPATA",
        "documento": "39684141",
        "edad": "63 años",
        "fecha_nacimiento": "05/01/1963",
        "dominancia": "Derecha",
        "estado_civil": "Soltera",
        "nivel_educativo": "Especialización / postgrado / maestría",
        "telefono": "3174419531",
        "direccion": "CALLE 22 No 34 Bis 19",
        "eps_ips": "Sanitas",
        "afp": "Colpensiones",
    },
    "empresa": {
        "nombre": "FISCALIA GENERAL DE LA NACION SECCIONAL HUILA",
        "nit": "800187609-1",
        "contacto": "Diana Cristina Sánchez Pama",
        "cargo_contacto": "Profesional de gestión II y SST",
        "correo": "dianac.sanchez@fiscalia.gov.co",
        "telefono": "3155751303",
        "direccion": "Carrera 21 No 26-65 sur",
    },
    "laboral": {
        "cargo": "Técnico investigador IV",
        "area": "Policía Judicial CTI",
        "fecha_ingreso_cargo": "03/12/2003",
        "antiguedad_cargo": "22 años 10 meses aprox.",
        "fecha_ingreso_empresa": "03/12/2003",
        "antiguedad_empresa": "22 años 10 meses aprox.",
        "vinculacion": "Provisionalidad.",
        "jornada": "Lunes a viernes de 8:00 am a 12:00 pm y 1:00 pm a 5:00 pm (real 7:00 am a 7:00 pm)",
        "ritmo": "Autoadministrado, depende de los informes solicitados",
        "descansos": "1 hora de almuerzo",
        "turnos": "Realiza turnos de disponibilidad cada 5 semanas",
        "horas_extras": "No",
        "rotaciones": "No",
        "tiempos_efectivos": "8 horas diarias",
        "distribucion_semanal": "Lunes a viernes",
    },
    "siniestro": {
        "id_siniestro": "126338404",
        "fecha_evento": "2/03/2013",
        "diagnosticos": "G568 Síndrome de túnel del carpo bilateral",
        "tiempo_incapacidad": "69 días",
        "ultimo_dia_incapacidad": "04/08/2022",
    },
    "consulta": {
        "fecha": "10/02/2026",
        "fecha_texto": "10 de febrero de 2026",
        "hora_visita": "2:30 p.m.",
        "metodologia": (
            "La metodología utilizada para la Prueba de Trabajo es de tipo entrevista, "
            "observacional y descriptivo. Durante la visita, se analizan los procesos y "
            "la biomecánica de las actividades que desempeña la servidora, basándose en "
            "los criterios técnicos de Positiva Compañía de Seguros S.A. El objetivo es "
            "emitir una carta con recomendaciones laborales como seguimiento al diagnóstico "
            "reconocido de origen profesional e integral. La prueba de trabajo de la "
            "servidora Laura María Cardona Zapata con C.C. 39684141 se lleva a cabo a "
            "través de contacto por correo electrónico, en el cual se recibe la asignación "
            "del caso por parte de la IPS Rehabilitación Integral Laboral y Ocupacional "
            "(RILO), proveedor aliado de la ARL Positiva. Posteriormente, se programa la "
            "visita con la fiscalía general de la Nación Seccional Neiva en la Carrera 21 "
            "No 26-65 sur para el día 10 de febrero a las 2:30 p.m. En la visita se llevó "
            "a cabo una entrevista con la servidora, se verificaron las actividades que "
            "realiza, los requerimientos y el paso a paso de cada tarea asignada. También "
            "se hizo un registro fotográfico, con el consentimiento previo de la servidora, "
            "con el fin de socializar las recomendaciones de rehabilitación integral. Las "
            "actividades descritas fueron revisadas y avaladas por la jefe Diana Cuenca "
            "cuyo cargo ES Técnica investigador II."
        ),
        "proceso_productivo": (
            "La Servidora manifiesta las siguientes funciones: Diarias — Realizar el "
            "análisis de dinámicas delictivas de estafa. Realizar informe de dinámicas "
            "delictivas de estafa. Imprimir los informes, gráficas, mapas que se elaboran "
            "de los casos que se analizan de las dinámicas delictivas. La información "
            "llega al correo o a los diferentes sistemas que tiene la fiscalía SPOA, "
            "COGNOS, WATSON ETC, allí busca los datos de los casos que se estudian o el "
            "fenómeno criminal que se está estudiando (los casos llegan de denuncias "
            "presenciales, gestores que son denuncias virtuales, denuncias que llegan por "
            "correo que son por ORFEO, por parte de los fiscales de intervención temprana, "
            "de sus asistentes, del asesor de víctimas, del director de la dirección etc.), "
            "se extrae la información, se realiza las búsquedas y verificaciones, se "
            "estandariza y se analiza la información; para luego emitir el informe a los "
            "servidores de la dirección seccional Huila o a nivel nacional cuando lo "
            "requieran y/o a quien lo requiera. Realiza turnos de disponibilidad cada 5 "
            "semanas de la sección de análisis criminal del CTI, recoge información criminal "
            "y de orden público en tiempo real 7/24, esta actividad es adicional al trabajo; "
            "debe estar pendiente de los diferentes medios locales, regionales y nacionales "
            "y ver situaciones de orden público o cuando se altere la ciudadanía para "
            "reportarlo de acuerdo los formatos establecidos al jefe y así mismo él reporta "
            "al director del CTI y el al director nacional. Apoyar cuando no está el "
            "encargado de medios la función de estar pendientes de los medios, capturas y "
            "hacer el reporte."
        ),
        "apreciacion_trabajador": (
            "La servidora manifiesta que permanece con dolor constante en las manos durante "
            "todo el día, que su trabajo le gusta, es emocionante y trabaja para cumplir "
            "con las solicitudes o informes de análisis de las dinámicas delictivas, pero "
            "refiere que en ocasiones para poder dar cumplimiento se extiende en la jornada "
            "laboral habitual, lo anterior le ocasiona aumento de la sintomatología dolorosa "
            "y refiere que se estresa con todos los informes que le solicitan y que no ha "
            "podido dar respuesta."
        ),
        "estandares_productividad": (
            "La servidora menciona que el trabajo depende de la cantidad de análisis que "
            "demanda la misma dinámica que es un factor externo y que se incrementan cada "
            "día más de las estafas por los avances tecnológicos y el uso de la tecnología."
        ),
        "concepto_desempeno": (
            "Se realizó la Prueba de Trabajo (PT) en las instalaciones de la empresa "
            "fiscalía General de la Nación seccional Huila, ubicada en el municipio de "
            "Neiva, Huila, donde la servidora desempeña el cargo de Técnico investigador "
            "IV. Durante la visita, la servidora manifestó permanecer con la sintomatología "
            "dolorosa de manera constante en mano y muñecas no obstante puede realizar "
            "todas las actividades. Refiere que cuando hay gran demanda de solicitudes para "
            "poder dar cumplimiento se extiende en la jornada laboral habitual y que se "
            "estresa con todos los informes que le solicitan y que no ha podido dar "
            "respuesta; esto le ocasiona aumento de la sintomatología dolorosa. Se sugiere, "
            "en el desarrollo de las funciones laborales, la implementación de pausas "
            "activas cada hora, con una duración mínima de 5 a 7 minutos, enfocadas "
            "especialmente en ejercicios de movilidad y estiramiento del miembro superiores "
            "con énfasis en muñecas y manos. No se evidenció manipulación de carga ni "
            "movimientos que implicaran sobreesfuerzo en la ejecución de las actividades "
            "observadas, como medida preventiva, se recomienda, realizar la actividad de "
            "realización de informes y análisis de casos de forma autoadministrada "
            "procurando siempre que la actividad se ejecute dentro de los límites de "
            "tolerancia funcional. Asimismo, se recomienda la utilización del mouse con "
            "la mano izquierda y alternar tareas con actividades como la revisión y la "
            "impresión de material probatorio y de informes. Estas medidas buscan favorecer "
            "la recuperación funcional, reducir la sintomatología dolorosa y prevenir una "
            "mayor rigidez articular. Asimismo, se considera importante que el servidor "
            "mantenga la posibilidad de organizar y ejecutar sus tareas de acuerdo con su "
            "propio ritmo y nivel de tolerancia, a fin de evitar la sobrecarga física y "
            "preservar su capacidad laboral."
        ),
    },
    "rehabilitacion": {
        "nombre_revisor": "JENNY MARITZA RIVERA POLANIA",
        "cargo_revisor": "LIDER DE OPERACIONES ARL – IPS RILO",
    },
    "visita": {
        "nombre_profesional": "Sandra Patricia Polanía Osorio",
    },
    "tareas_criticas": [
        {
            "actividad": "VERIFICACION DE LA INFORMACION CRIMINAL - ESTAFA",
            "ciclo": "Durante la Jornada Laboral",
            "subactividad": "Verifica en los sistemas información o datos requeridos que sirven para el análisis y comprensión del caso, la información la extrae del sistema penal oral acusatorio, del sistema de información virtual, de los medios abiertos, noticias, redes sociales, de la inteligencia artificial.",
            "estandar": "Depende de los informes solicitados",
            "descripcion": (
                "Posiciones: Sedente. Revisa y/o verifica entre 30 hasta 150 fracciones para leer de un solo 1 caso, en el mes analiza 8 casos de estafa aproximadamente. Movimientos: Ejecuta movimientos en miembros superiores en la digitación, manipulación del mouse, como tarea rutinaria durante la jornada laboral. La servidora realiza estas actividades en posición sedente con postura de cuello en extensión de 0°- 5° y flexión de 0° a 20°, rotación de 0° a 20° e inclinación de hasta 0° a 10°. El tronco en flexión de 0° a 10°, rotación e inclinación de 0° a 15°, sin apoyo de la espalda al espaldar de la silla. Miembros superiores, con hombros en flexión de 0° a 30°, abducción de 0° 30°, rotación de 0° a 10°, flexión de codo 0° a 90°, con antebrazos en pronación 0° a 90° apoyados en el escritorio, muñecas en desviación radiales y cubitales de 0° a 10°, con articulaciones metacarpofalángicas e interfalángicas con flexión 0° a 90°, mano derecha alternando el uso del mouse, con agarre digito palmar esférico mouse. Miembros inferiores: Cadera en flexión 0° a 90°, rodillas y tobillo con ángulo de 0° a 90°, pies apoyados en el piso y/o descansa pies."
            ),
            "apreciacion_trabajador": "Con esta actividad la servidora no tiene dificultad, refiere que descansa la mano porque digita muy poco, aunque el dolor permanece en ocasiones se aumenta por la demanda de solicitudes.",
            "apreciacion_profesional": "No presenta limitación funcional en la actividad; se sugiere realizarla con un ritmo autoadministrado, al recibir las solicitudes, siempre manejar una adecuada higiene postural frente al computador y realizar pausas activas que permitan la recuperación muscular de miembros superiores, teniendo en cuenta las recomendaciones. Estas medidas buscan favorecer la recuperación funcional, reducir el dolor y prevenir una mayor rigidez articular.",
            "conclusion_tipo": "Puede desempeñarla",
            "conclusion_descripcion": "Con esta actividad la servidora manifiesta no tiene dificultad, descansa la mano porque digita muy poco; aunque el dolor permanece en ocasiones se aumenta por la demanda de solicitudes. Se recomienda trabajar a un ritmo autoadministrado, la implementación de pausas activas cada hora, con una duración mínima de 5 a 7 minutos, enfocándose especialmente en ejercicios de movilidad y estiramiento del miembro superior derecho, muñeca y dedos. Asimismo, se sugiere alternar periódicamente la posición sedente con la posición de pie, con el objetivo de activar la musculatura postural y prevenir sobrecargas musculares derivadas del trabajo prolongado en una sola postura. Estas medidas buscan favorecer la recuperación funcional, reducir el dolor y prevenir una mayor rigidez articular.",
        },
        {
            "actividad": "Realización del informe de análisis de casos de estafa",
            "ciclo": "Durante la Semana",
            "subactividad": "Consolida y organiza la información de casos de estafa y realiza el informe para ser enviado a las personas que solicitaron el análisis tales como: servidores de la dirección seccional Huila o a nivel nacional cuando lo requieran y/o a quien lo requiera. El objetivo del informe es la asociación de casos de estafa, en el documento se organiza la información utilizando herramientas de análisis en donde se vea la relación de los casos, se busca también en los diferentes medios, fenómeno, modos operandi para que allá comprensión del caso y el resultado se puede asociar o simplemente se realiza el análisis del fenómeno criminal.",
            "estandar": "Depende las solicitudes",
            "descripcion": (
                "Realiza informe de 8 casos de estafa al mes. Movimientos: Ejecuta movimientos en miembros superiores en la digitación, manipulación del mouse, como tarea rutinaria durante la jornada laboral. Cuello en extensión 0° 5°, flexión de 0° a 15°, rotaciones e inclinaciones de 0° a 10°. El tronco en flexión de 0° a 10°, rotación e inclinación de 0° a 15°, sin apoyo de la espalda al espaldar de la silla. Miembros superiores alternando derecha e izquierda: Hombros flexión de 0° a 50°, abducción de 0° 40°, rotación interna y externa de 0° a 20°, codos en flexión de 0° a 90°, antebrazos alternando pronosupinación de 0° a 90°, muñecas extensión de 0° a 10°, realiza agarres dígito palmar esférico mouse. Miembros inferiores: Cadera en flexión 0° a 90°, rodillas y tobillo con ángulo de 0° a 90°, pies apoyados en el piso y/o descansa pies."
            ),
            "apreciacion_trabajador": "La servidora manifiesta que, aunque el dolor es constante puede desarrollar la actividad; refiere que en esta actividad se demora más y al digitar algunas veces la información se desvía porque los dedos se ponen lentos, no escribe la palabra que es y quedan a veces en desorden, las muñecas le duelen y debe parar y realizar pausas activas porque el dolor se exacerba.",
            "apreciacion_profesional": "Se observa que la servidora al realizar los informes digita de acuerdo con su nivel de tolerancia. Durante la ejecución de las actividades no se evidencian movimientos que impliquen sobreesfuerzo físico. Sin embargo, como medida preventiva, se sugiere realizar la actividad de forma autoadministrada y realizar pausas activas cada hora con una duración de cinco (5) a (7) minutos, enfocadas principalmente en los segmentos comprometidos; Con el objetivo prevenir la aparición de molestias adicionales o el agravamiento de la sintomatología existente en muñecas. Asimismo, utilizar el mouse en la mano izquierda y alternar las funciones, priorizando actividades como la revisión y la impresión de material probatorio y de informes.",
            "conclusion_tipo": "Puede desempeñarla",
            "conclusion_descripcion": "La servidora manifiesta no limitación funcional al realizar la actividad de realizar los informes, ya que siempre la realiza a tolerancia y cuando supera su tolerancia realiza una pausa. Durante la visita no se evidenció manipulación de carga ni movimientos que implicaran sobreesfuerzo en la ejecución de las actividades observadas. No obstante, como medida preventiva se recomienda ejecutar la actividad de forma autoadministrada y realizar pausas activas cada hora con una duración de cinco (5) a (7) minutos, enfocadas principalmente en los segmentos comprometidos; con el objetivo prevenir la aparición de molestias adicionales o el agravamiento de la sintomatología existente muñecas. Asimismo, se recomienda utilizar el mouse en la mano izquierda y alternar las funciones, priorizando actividades como la revisión y la impresión de material probatorio y de informes. Estas recomendaciones tienen como objetivo prevenir la aparición de molestias adicionales o el agravamiento de la sintomatología existente en el hombro derecho.",
        },
        {
            "actividad": "IMPRIMIR",
            "ciclo": "Semanal",
            "subactividad": "Imprime los informes de análisis, las gráficas de relaciones datos y las tablas de datos de las noticias e información relacionada.",
            "estandar": "Depende de las solicitudes",
            "descripcion": (
                "La servidora imprime aproximadamente entre 2 a 10 impresiones diarias. Movimientos: Ejecuta movimientos en miembros superiores al tomar las impresiones de la impresora. La servidora realiza estas actividades en posición sedente con postura de cuello en flexión de 0° a 10°, rotación de 0° a 30° e inclinación de hasta 0° a 15°. El tronco en flexión de 0° a 5°, rotación e inclinación de 0° a 20°, sin apoyo de la espalda al espaldar de la silla. Miembros superiores, con hombros en flexión de 0° a 90°, abducción de 0° 40°, rotación de 0° a 30°, flexión de codo 0° a 100°, con antebrazos en neutro y pronación 0° a 90, muñecas en desviación radiales y cubitales de 0° a 10°, con articulaciones metacarpofalángicas e interfalángicas con flexión 0° a 30°, con agarre digito palmar para tomar la impresión. Miembros inferiores: Cadera en flexión 0° a 90°, rodillas y tobillo con ángulo de 0° a 90°, pies apoyados en el piso y/o descansa pies."
            ),
            "apreciacion_trabajador": "Refiere no tener dificultad para realizar la actividad.",
            "apreciacion_profesional": "No presenta limitación funcional en la actividad; se sugiere realizarla con un ritmo autoadministrado, siempre manejar una adecuada higiene postural en posición sedente, realizar pausas activas que permitan la recuperación muscular de miembros superiores, teniendo en cuenta las recomendaciones. Estas medidas buscan favorecer la recuperación funcional, reducir el dolor y prevenir una mayor rigidez articular.",
            "conclusion_tipo": "Puede desempeñarla",
            "conclusion_descripcion": "La servidora manifiesta que la sintomatología dolorosa permanece de manera constante; sin embargo; cumple con la función de imprimir los informes de análisis, las gráficas de relaciones datos y las tablas de datos de las noticias e información relacionada. Se recomienda la implementación de pausas activas cada hora, con una duración mínima de 5 a 7 minutos, enfocándose especialmente en ejercicios de movilidad y estiramiento de muñecas y manos. Asimismo, se sugiere siempre mantener una adecuada higiene postural en posición sedente (sentada) y alternarla con la posición bípeda (de pie) para realizar cambio de posición. Estas medidas buscan favorecer la recuperación funcional, reducir el dolor y prevenir una mayor rigidez articular.",
        },
    ],
    "materiales": [
        {"nombre": "Video terminal", "estado": "Computador de mesa el cual se encuentra en buen estado.", "requerimientos": "No aplica", "observaciones": "La persona ubica la pantalla del computador de frente, pero se observa que se encuentra por encima de la horizontal visual."},
        {"nombre": "Teclado", "estado": "Adecuado", "requerimientos": "No aplica", "observaciones": "Utilice el teclado de forma bimanual, céntrelo en relación con la pantalla y el cuerpo."},
        {"nombre": "Mouse convencional", "estado": "Se encuentra en buen estado.", "requerimientos": "Agarre esférico con miembro superior derecho.", "observaciones": "Ninguna"},
        {"nombre": "Silla", "estado": "Se evidencia silla ergonómica, de 5 aspas con rodachines graduable en altura y material antitranspirante", "requerimientos": "Siéntese con la espalda recta apoyada en el espaldar de la silla, mantenga la cabeza y el cuello en posición recta, hombros relajados, los codos junto al cuerpo; los antebrazos, puños y manos alineados en posición recta con relación al teclado, los glúteos deben quedar contra el respaldo de la silla, muslos y caderas paralelos al piso formando un ángulo de 90° y pies soportados sobre el piso o apoya pies.", "observaciones": "La servidora refiere que no hay para estirar las piernas, se recomienda alternar la posición cada hora de sedente a bípedo."},
        {"nombre": "Escritorio", "estado": "Se encuentra en buen estado la forma es en L y es amplio.", "requerimientos": "No aplica", "observaciones": "No aplica"},
        {"nombre": "Impresora", "estado": "Herramienta en buen estado.", "requerimientos": "Manipulación manual", "observaciones": "Ninguna."},
        {"nombre": "Lápiz y esfero", "estado": "Bueno", "requerimientos": "Pinza trípode", "observaciones": "Ninguna."},
    ],
    "peligros": [
        {"nombre": "Físicos", "descripcion": "NA", "control": "NA", "recomendaciones": "NA"},
        {"nombre": "Biológicos", "descripcion": "NA", "control": "NA", "recomendaciones": "NA"},
        {"nombre": "Biomecánicos", "descripcion": "Movimientos repetidos en miembros superiores", "control": "Pausas activas, capacitaciones", "recomendaciones": "Continuar con pausas activas y capacitaciones"},
        {"nombre": "Psicosociales", "descripcion": "Comunicación eficaz. Dialogo con cliente interno y externo que ingresa al área. Ambiente y convivencia laboral", "control": "Capacitaciones.", "recomendaciones": "Capacitación del riesgo psicosocial"},
        {"nombre": "Químicos", "descripcion": "NA", "control": "NA", "recomendaciones": "NA"},
        {"nombre": "Cond. Seguridad", "descripcion": "Riesgo caído desde su propio nivel. Riesgo público (Atentados, desorden público)", "control": "Mantenimientos locativos. EPP. Control del calzado. Capacitaciones de autocuidado", "recomendaciones": "Capacitaciones"},
    ],
}

print("\U0001f9ea Generando Prueba de Trabajo...")
docx_path = generar_prueba_trabajo(datos, output_name="prueba-39684141-2026-02-10")
print(f"\u2705 DOCX: {docx_path}")
from pathlib import Path
print(f"   Tamaño: {Path(docx_path).stat().st_size/1024:.0f} KB")
doc_generator._convertir_a_pdf = original_convertir
