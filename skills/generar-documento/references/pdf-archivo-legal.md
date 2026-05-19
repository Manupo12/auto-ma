# PDF/A para Archivo Legal

## ¿Qué es?
PDF/A (ISO 19005) es el estándar internacional para preservación digital de documentos a largo plazo. Es el formato exigido por notarías y juzgados en Colombia.

## ¿Por qué PDF/A y no PDF normal?
- **Autocontenido**: todas las fuentes, imágenes y metadatos van dentro del archivo
- **Independiente del software**: se verá igual en 20 años aunque cambie LibreOffice/Word
- **Sin dependencias externas**: no requiere fuentes del sistema ni enlaces rotos
- **Metadatos obligatorios**: autor, título, fecha de creación

## Perfil usado: PDF/A-2b
- **2**: soporta transparencias, capas y compresión moderna
- **b (basic)**: nivel de conformidad básico — suficiente para documentos clínicos

## Generación
```python
from backend.pdf_archivo import convertir_a_pdfa, verificar_pdfa

# Convertir documento aprobado
pdfa_path = convertir_a_pdfa("/ruta/documento.docx")
# → genera PDF/A-2b + archivo .pdf.meta.json con hash y metadata

# Verificar que se puede abrir
if verificar_pdfa(pdfa_path):
    print("PDF/A válido")
```

## Flujo automático
Cuando Sandra APRUEBA un documento:
1. Se genera el .docx normalmente
2. Se convierte a PDF/A con LibreOffice headless
3. Se calcula hash SHA-256 del PDF
4. Se guarda metadata (.pdf.meta.json)
5. La versión APROBADA se marca como inmutable (chmod 555)
