"""Prueba Citación de Empresas - YESID LOZANO CEDEÑO"""
import sys
sys.path.insert(0, "/root/fisioterapia/backend")

import doc_generator
original_convertir = doc_generator._convertir_a_pdf
doc_generator._convertir_a_pdf = lambda x: None

from doc_generator import generar_citacion_empresas

datos = {
    "paciente": {
        "nombre": "YESID LOZANO CEDEÑO",
        "documento": "12124080",
    },
    "empresa": {
        "nombre": "Seccional Rama Judicial Neiva",
        "contacto": "HEBERTH ARMANDO RUIZ PAVA",
        "cargo_contacto": "Coordinador de SST",
        "direccion": "Neiva-Huila",
    },
    "laboral": {
        "cargo": "Escribiente",
    },
    "consulta": {
        "fecha": "23 febrero 2026",
    },
    "visita": {
        "tipo_estudio": "Prueba de trabajo",
        "tiempo_ejecucion": "3 horas",
        "objetivo": (
            "El objetivo es emitir una carta con recomendaciones laborales como "
            "seguimiento al diagnóstico reconocido de origen profesional e integral."
        ),
        "fecha_hora": "Jueves 26 de febrero 2026",
        "nombre_profesional": "Sandra Patricia Polanía Osorio",
        "nombre_auditor": "Angela López",
        "descripcion_estado": (
            "Servidor matriculado en Rehabilitación quien ya paso por medicina laboral, "
            "se encuentra realizando terapias físicas y se va a desarrollar prueba de trabajo."
        ),
        "requisitos": (
            "Se solicita que la visita sea acompañada por un representante del área de "
            "seguridad y salud en el trabajo y jefe inmediato. En los casos con diagnóstico "
            "de esfera mental, se sugiere que se encuentre un representante del comité de "
            "convivencia. Se solicita a la empresa facilitar las funciones del cargo durante "
            "la visita, con el fin de hacer más objetivo el estudio."
        ),
    },
    "proveedor": {
        "telefono": "3182675427",
        "correo": "tocupacionalrilo@gmail.com",
    },
}

print("\U0001f9ea Generando Citación de Empresas...")
docx_path = generar_citacion_empresas(datos, output_name="citacion-12124080-2026-02-23")
print(f"\u2705 DOCX: {docx_path}")
from pathlib import Path
print(f"   Tamaño: {Path(docx_path).stat().st_size/1024:.0f} KB")

doc_generator._convertir_a_pdf = original_convertir
