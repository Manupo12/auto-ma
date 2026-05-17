#!/usr/bin/env python3
"""PRUEBA DE FUEGO — Datos IDÉNTICOS al ejemplo."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.doc_generator import generar_analisis_exigencia
import backend.doc_generator as dg
dg._convertir_a_pdf = lambda path: None

datos = {
    "paciente": {
        "nombre": "LAURA ROJAS ZUÑIGA", "documento": "36184789",
        "fecha_nacimiento": "24/05/1965", "edad": "59",
        "dominancia": "Derecha", "estado_civil": "Casada",
        "nivel_educativo": "Especialización / postgrado / maestría",
        "formacion_otros": "Gestión de procesos psicosociales",
        "telefono": "3212326605",
        "direccion": "Calle 56 # 1w-99 Torre 4 apto 402. Conjunto Torres de Ipacaray / Neiva",
        "eps_ips": "Famisanar", "afp": "Colpensiones",
    },
    "empresa": {
        "nombre": "FISCALIA GENERAL DE LA NACION SECCIONAL DE HUILA", "nit": "800187609",
        "contacto": "Diana Cristina Sánchez Pama / Profesional de gestión II y SST / Franky Alexander Briñez Parra / Jefe inmediato líder de grupos delegados de la sección investigaciones",
        "correo": "dianac.sanchez@fiscalia.gov.co", "telefono": "3155751303",
        "direccion": "Cra 21 Sur # 26-65 Fiscalía Neiva",
    },
    "laboral": {
        "cargo": "TÉCNICO INVESTIGADOR I", "area": "Administrativo / Trabajo en campo",
        "fecha_ingreso_cargo": "19/05/1999", "antiguedad_cargo": "25 años y 7 meses",
        "fecha_ingreso_empresa": "19/05/1999", "antiguedad_empresa": "25 años y 7 meses",
        "vinculacion": "Indefinido / Provisionalidad",
        "jornada": "8:00 am a 12:00 pm y 1:00 pm a 5:00 pm con descanso 1 hora para el almuerzo.",
        "ritmo": "Individual",
        "descansos": "1 hora de almuerzo con disponibilidad de pausas activas de 5 a 10 minutos en cada jornada laboral.",
        "turnos": 'Turnos de disponibilidad cada 3 semanas por grupos de martes a martes 24/12 horas. Sin embargo aclara la Servidora "Actualmente no realizo labores operativa en el turno mencionado".',
        "tiempos_efectivos": "8 horas diarias", "rotaciones": "No",
        "horas_extras": "No", "distribucion_semanal": "Lunes a viernes",
    },
    "siniestro": {
        "id_siniestro": "387872120", "fecha_evento": "24/06/2021",
        "diagnosticos": "S934 ESGUINCE GRADO I DE TOBILLO DERECHO\nS824 FRACTURA OBLICUA DEL PERONÉ DISTAL LATERALIDAD DERECHA\nS823 FRACTURA VERTICAL DEL MALÉOLO POSTERIOR DE LA TIBIA DISTAL NO DESPLAZADA LATERALIDAD DERECHA\nS932 LESIÓN PARCIAL DE LIGAMENTOS PERONEOASTRAGALINOS Y TIBIOPERONEO ANTEROINFERIOR DE TOBILLO DERECHO",
        "tiempo_incapacidad": "120 días",
    },
    "consulta": {
        "fecha": "12/12/2024",
        "metodologia": "La metodología utilizada para la visita al sitio de trabajo en el Análisis de Exigencia es de tipo entrevista, observacional y descriptivo. Durante la visita, se analizan los procesos y la biomecánica de las actividades que desempeña la servidora, basándose en los criterios técnicos de Positiva Compañía de Seguros S.A. El objetivo es emitir una carta con recomendaciones laborales como seguimiento al diagnóstico reconocido de origen profesional e integral.\n\nEl análisis de exigencia de trabajo de la servidora LAURA ROJAS ZUÑIGA con C.C. 36184789 se lleva a cabo a través de contacto por correo electrónico, en el cual se recibe la asignación del caso por parte de la IPS Rehabilitación Integral Laboral y Ocupacional (RILO), proveedor aliado de la ARL Positiva. Posteriormente, se programa la visita con la Fiscalía General de la Nación en Neiva para el 12 de diciembre de 2024, a las 9:00 a.m.\n\nLa visita se realizó en las instalaciones de la Fiscalía General de la Nación en Neiva, donde se llevó a cabo una entrevista con la servidora. Durante la entrevista, se verificaron las actividades que realiza la servidora, los requerimientos y el paso a paso de cada tarea asignada. También se hizo un registro fotográfico, con el consentimiento previo de la servidora, con el fin de socializar las recomendaciones de rehabilitación integral y corroborar si estas se están cumpliendo en el puesto de trabajo actual.",
        "resultados_valoracion": "Servidora de 59 años de edad, con antecedente de Accidente laboral con fecha 24/06/2021. Diagnósticos: S934 ESGUINCE GRADO I DE TOBILLO DERECHO, S824 FRACTURA OBLICUA DEL PERONÉ DISTAL LATERALIDAD DERECHA, S823 FRACTURA VERTICAL DEL MALÉOLO POSTERIOR DE LA TIBIA DISTAL NO DESPLAZADA LATERALIDAD DERECHA, S932 LESIÓN PARCIAL DE LIGAMENTOS PERONEOASTRAGALINOS Y TIBIOPERONEO ANTEROINFERIOR DE TOBILLO DERECHO. Quien labora en el cargo de Técnico Investigador I, realizando funciones de Administrativo: Elaboración de informes (entrevista o arraigos mínimo 17 máximo 35, realizar citaciones 5 a 10 citaciones en al día, realización de oficios para solicitar información mínimo 7 actuaciones por cada informe máximo 24), de 8 a 12 am entrega. Trabajo en campo: Desplazamientos a los diferentes sectores de la ciudad para la entrega de citaciones mínimo 1 a 2 veces por semana entrega de citaciones 10 entregas, en barrios peligrosos de la ciudad información referida por la Servidora, verificaciones de arraigo, investigación si el denunciado (a) vive en la dirección suministrada, labores de vecindad (validación de la información) a 7 a 2 veces al mes. Componentes del desempeño ocupacional. Sensorio - motor: Refiere presentar dificultad moderada para desplazamientos por diferentes terrenos, al subir escaleras, rampas, correr, saltar. Manifiesta inflamación y dolor según EVA 8/10 frecuentemente al caminar y al reposo 6/10 disminuye. Psicológicos: Refiere que se siente desmotivada, triste porque lo que le paso en el Accidente laboral, piensa que la funcionalidad del tobillo derecho no va ser igual. Social: Refiere que sus roles familiares y amigos se han visto afectados y se ha distanciado por la limitación del movimiento en el tobillo derecho. Se muestra independiente en las actividades básicas cotidianas y de la vida diaria, sin embargo manifiesta dolor e inestabilidad en la marcha al caminar o estar de pie por tiempos prolongados.",
        "programa_rhi": "Medicina laboral\nOrtopedia y traumatología\nFisiatría\nMedicina del dolor\nAnálisis de exigencias\nCarta de recomendaciones",
        "proceso_productivo": "La Servidora manifiesta las siguientes funciones: Administrativo: Elaborar informes (Entrevista, arraigos, citaciones, oficios, actuaciones, informes). Trabajo en campo: Desplazamientos a los diferentes sectores de la ciudad para la entrega de citaciones; Verificaciones de arraigo, investigación de la dirección de la residencia de las personas denunciadas para la entrega de la citación, ejecutando labores de vecindad (validación de la información).",
        "apreciacion_trabajador": "La servidora menciona que ejecuta las tareas de acuerdo con su ritmo y tolerancia. Sin embargo, manifiesta una limitación moderada en la tarea de entrega de citaciones en campo, debido a que experimenta dolor e inflamación en el tobillo derecho al caminar, además de sentir inseguridad por la inestabilidad del segmento comprometido, especialmente al caminar por terrenos irregulares o al correr en una situación de emergencia.",
        "estandares_productividad": "El ritmo de trabajo se desarrolla a diario en donde la Servidora puede ejecutar las tareas de acuerdo con su ritmo y tolerancia, todo depende de las solicitudes del servicio. Manifiesta tener una meta mensual de mínimo 20 informes de investigador de campo.",
        "concepto_desempeno": "La servidora se desempeña en el cargo de Técnico Investigador I, con funciones asignadas en dos áreas: Administrativa y Operativa. En el área administrativa, realiza investigación de datos en plataformas, elaboración de informes de entrevistas, arraigos, citaciones y realización de oficios. En el área operativa, se desplaza utilizando un vehículo asignado por la empresa con apoyo de un conductor, para la entrega de citaciones en la zona urbana de la ciudad. La servidora indica que debe caminar desde el vehículo hasta la vivienda para realizar la entrega, y menciona que la distancia de desplazamiento depende de hasta dónde pueda ingresar el vehículo, proporcionando ejemplos de direcciones en callejones o vías donde el vehículo no puede acceder. En cuanto a las posturas y movimientos, las tareas se realizan principalmente en posición sedente, alternando con breves desplazamientos hacia la impresora dentro de la oficina. El trabajo de campo también implica estar sentada dentro del vehículo y caminar durante la entrega de citaciones. Se sugiere un reintegro sin modificaciones, pero con recomendaciones específicas. Se debe realizar pausas activas cada dos horas de trabajo continuo, con especial énfasis en el tobillo izquierdo. Además, se sugiere alternar entre posiciones bípeda y sedente cada dos horas. En el área operativa, se recomienda tener precaución al observar el entorno, caminar con cuidado para evitar tropezones y la inestabilidad de terrenos irregulares, y evitar acelerar la marcha, correr o saltar para reducir el riesgo de caídas. Estas medidas son necesarias para prevenir el aumento de la sintomatología de dolor, inflamación e inestabilidad en el tobillo derecho, según lo manifestado por la servidora.",
    },
    "tareas_criticas": [
        {
            "actividad": "Administrativas: Digitación y Manipulación de documentos",
            "ciclo": "Durante la jornada laboral",
            "subactividad": "Elaboración de informes, citaciones, entrevistas, arraigos, organizar documentación, imprimir y escanear.",
            "estandar": "N/A",
            "descripcion": "La Servidora realiza las siguientes tareas con uso de computador de escritorio, impresora y utiliza herramientas manuales de oficina como grapadora, perforadora, sacaganchos: Posiciones: Sedente con alternancia en posición bípeda y deambulando desde el puesto de trabajo hasta la impresora que esta aproximadamente 12 metros. Movimientos: Ejecuta movimientos en miembros superiores en la digitación durante la jornada laboral en la elaboración de informes (Entrevista o arraigos mínimo 17 máximo 35, realizar citaciones 5 a 10 citaciones en al día, realización de oficios para solicitar información mínimo 7 actuaciones, por cada actuación mencionada elabora 24 máximo citaciones o informes para ser entregadas). Posición y movimiento: bípeda estática y marcha. La Servidora realiza desplazamiento al imprimir, escanear o fotocopiar aproximadamente a una distancia de 12 metros con una frecuencia de 2 a 5 veces durante la jornada laboral, seguidamente la servidora organiza la documentación de las citaciones para la entrega.",
            "apreciacion_trabajador": "La servidora indica que realiza las tareas administrativas asignadas según su tolerancia y expresa estar conforme con las funciones que desempeña actualmente, sin mostrar inconformidad respecto a sus actividades laborales.",
            "apreciacion_profesional": "Servidora sin limitación en las funciones signadas administrativas, se recomienda realizar pausas activas con mayor énfasis en la movilización de tobillo derecho, se sugiere alternar la posición de sedente a bípeda para la activación muscular de segmento comprometido.",
            "conclusion_tipo": "Puede desempeñarla", "conclusion_descripcion": "La actividad puede ser realizada por la trabajadora siguiendo las recomendaciones laborales.",
        },
        {
            "actividad": "Trabajo en campo (Entrega de citaciones)",
            "ciclo": "1 a 2 veces por semana",
            "subactividad": "Desplazamientos fuera de las instalaciones de la empresa para la entrega de citaciones a las viviendas, en la zona urbana de la ciudad.",
            "estandar": "Mensual: Mínimo 20 informes de investigador de campo.",
            "descripcion": "La servidora realiza trabajo de campo y menciona que se desplaza utilizando un vehículo asignado por la empresa con apoyo de un conductor, para la entrega de citaciones en la zona urbana de la ciudad. Indica que debe caminar desde el vehículo hasta la vivienda para realizar la entrega. La servidora señala que la distancia de desplazamiento depende de hasta dónde pueda ingresar el vehículo, proporcionando ejemplos de direcciones en callejones o vías donde el vehículo no puede acceder. Durante la semana, se programa de uno a dos días para la entrega de 10 citaciones en barrios de alto riesgo de la ciudad con mayor frecuencia. Además, se realizan verificaciones de arraigo para investigar si la persona denunciada reside o no en la dirección indicada, ejecutando labores de vecindad para validar la información. La servidora señala que se programa entre 2 y 7 veces al mes para realizar estas investigaciones de campo.",
            "apreciacion_trabajador": "La trabajadora manifiesta limitación moderada en el momento de desplazarse por el entorno a las viviendas para la entrega de las citaciones por temor de caídas, menciona experimentar ocasionalmente inestabilidad en la marcha, dolor e inflamación del tobillo derecho.",
            "apreciacion_profesional": "La servidora puede realizar la actividad teniendo la prevención en la observación del entorno, se sugiere caminar de forma cuidadosa para evitar tropezones, inestabilidad de terrenos irregulares, sin aceleración de la marcha, correr o saltar por riesgo de caídas.",
            "conclusion_tipo": "Puede desempeñarla", "conclusion_descripcion": "La actividad puede ser realizada por la trabajadora siguiendo las recomendaciones laborales.",
        },
    ],
    "materiales": [
        {"nombre": "Monitor", "estado": "Adecuado", "requerimientos": "Alineación de la pantalla"},
        {"nombre": "Teclado", "estado": "Adecuado", "requerimientos": "Agarres bimanuales y unimanuales"},
        {"nombre": "Mouse", "estado": "Adecuado", "requerimientos": "Agarres esférico - unimanual"},
        {"nombre": "Impresora", "estado": "Adecuada", "requerimientos": "N/A"},
        {"nombre": "Vehículo", "estado": "Adecuado", "requerimientos": "N/A"},
    ],
    "peligros": [
        {"nombre": "Físicos", "descripcion": "Radiaciones no ionizante (Sol) / Temperatura ambiente", "control": "No se evidencia los controles en la visita", "recomendacion": "No se evidencia los controles en la visita"},
        {"nombre": "Biológicos", "descripcion": "NA", "control": "NA", "recomendacion": "NA"},
        {"nombre": "Biomecánicos", "descripcion": "Movimientos repetitivos en miembros superiores", "control": "Pausas activas, capacitaciones", "recomendacion": "Continuar con pausas activas y capacitaciones"},
        {"nombre": "Psicosociales", "descripcion": "Comunicación eficaz / Dialogo con personas demandas / Agresión, insultos, percepción de emociones de los demandados. / Ambiente y convivencia laboral", "control": "Capacitaciones.", "recomendacion": "Capacitación del riesgo psicosocial"},
        {"nombre": "Químicos", "descripcion": "NA", "control": "NA", "recomendacion": "NA"},
        {"nombre": "Cond. Seguridad", "descripcion": "Riesgo caída desde su propio nivel / Riesgo público (Atentados, desorden público)", "control": "Mantenimientos locativos EPP. Control del calzado. Capacitaciones de autocuidado", "recomendacion": "Capacitaciones"},
    ],
    "recomendaciones": {
        "trabajador": "Las recomendaciones relacionadas con el presente análisis de exigencias serán enviadas en un documento formal a la empresa.",
        "empresa": "Las recomendaciones relacionadas con el presente análisis de exigencias serán enviadas en un documento formal a la empresa.",
    },
    "perfil_exigencias": {
        "vision": {"Percepción del Color": 4, "Percepción de Formas": 4, "Percepción de Tamaño": 4, "Relaciones Espaciales": 4},
        "audicion": {"Ubicación de Fuentes Sonoras": 4, "Discriminación Auditiva": 4},
        "sensibilidad": {"Estereognosia": 4, "Barognosia": 4, "Tacto Superficial": 4, "Percepción de Temperatura": 4, "Propiocepción": 4},
        "olfato_gusto": {"Percepción de olores o sabores": 4, "Discriminación de olores o sabores": 4},
        "motricidad_gruesa": {"Postura Bípeda": 3, "Postura Sedente": 4, "Posición de rodillas": 0, "Posición de Cuclillas": 0, "Caminar": (4, "Desplazamientos para entregar citaciones"), "Subir (escaleras, rampas)": 4, "Bajar (escaleras, rampas)": 4, "Levantar pesos": 0, "Transportar pesos": 0, "Agacharse": 0, "Inclinarse": 0, "Alcanzar": 1, "Halar": 0, "Empujar": 0, "Rapidez Motriz": 4, "Equilibrio": 4},
        "motricidad_fina": {"Enganche": 0, "Agarre": (4, "Las actividades realizadas requieren manipulación de Elementos (mouse y documentos)"), "Pinza": 2, "Pinza Fina": 0},
        "armonia": {"Uso de Ambas Manos": (4, "Habilidades necesarias para el desarrollo de las actividades Laborales de digitación."), "Coordinación Ojo - Mano": 4, "Coordinación Bimanual": 4, "Coordinación Mano - Pie": 4},
        "cognitivos": {"Atención": 4, "Concentración": 4, "Creatividad": 1, "Flexibilidad": 3, "Responsabilidad": 4, "Rapidez de Reacción": 4, "Percepción Herramientas de Trabajo": 4, "Percepción Estética": 1},
        "sociales_laborales": {"Adaptación al Grupo de Trabajo": (4, "Habilidades necesarias para ejecutar su oficio y garantizar la culminación exitosa de las tareas."), "Adaptación al Ambiente Laboral": 4, "Relación con la Autoridad": 4, "Relación con Compañeros de Trabajo": 4, "Liderazgo": 3, "Enfoque Constructivo": 4, "Cooperación": 4, "Confiabilidad": 4, "Estabilidad Emocional": 4, "Confianza en sí mismo": 4},
        "laborales": {"Rendimiento": (4, "Habilidades necesarias para poder ejecutar cualquier tipo de Labor remunerada."), "Asistencia": 4, "Puntualidad": 4, "Compromiso": 4, "Autocontrol": 4, "Eficiencia": 4, "Organización y Métodos de Trabajo": 4, "Calidad de Trabajo": 4, "Cuidado con los elementos de Trabajo": 4, "Higiene": 4, "Pulcritud": 4},
    },
    "registro": {
        "elaboro": "BIBIANA HORTA PERDOMO\nFisioterapeuta Esp. SO",
        "reviso": "JENNY MARITZA RIVERA POLANIA\nLIDER DE OPERACIONES ARL – IPS RILO",
    },
}

if __name__ == "__main__":
    print("🔥 PRUEBA DE FUEGO — Datos idénticos al ejemplo")
    try:
        path = generar_analisis_exigencia(datos)
        print(f"✅ Generado: {path}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback; traceback.print_exc()
