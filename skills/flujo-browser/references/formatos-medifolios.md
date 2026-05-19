# Formatos Clínicos Disponibles en Medifolios
# Extraídos de "Abrir Formato de Historia" → selector dropdown
# Paciente: Sandra Patricia Polania Osorio (CC 55162801)
# Fecha: 2026-05-17

## Lista completa de formatos

| # | ID | Formato | Relevancia ARL |
|---|----|---------|---------------|
| 1 | ? | CERTIFICADO DE ASISTENCIA V.2 | Baja |
| 2 | ? | CONSENTIMIENTO DE CARTA COMPROMISO PROCESO DE REHABILITACION INTEGRAL | Media |
| 3 | ? | CONSENTIMIENTO INFORMADO PROCESO DE REHABILITACION INTEGRAL | Media |
| 4 | ? | EVOLUCIÓN TERAPIAS V.2 | Alta - Formato 4 Cierre |
| 5 | ? | FORMATO DE ASISTENCIAS CONSULTAS ESPECIALES | Baja |
| 6 | 80 | HISTORIA CLÍNICA DE FISIOTERAPIA V.2 | Alta - Base para todos |
| 7 | ? | INFORME DE TERAPIA V.2 | Alta - Formato 7 |
| 8 | ? | NOTA DE EVOLUCIÓN, NO RIPS | Media |
| 9 | ? | RECOMENDACIONES | Alta - Formatos 2 y 3 |
| 10 | ? | TEST ARTICULAR | Media - Anexo Formato 1 |

## IDs técnicos

- Selector principal: `#slct_filtros_avanzados_historia_clinica` (Select2)
- Contenedor formatos: `#myTabFormatosHistoriaContent`
- Lista de tabs: `#myTabFormatosHistoriaList`
- Iframe donde se renderiza el formato: `#iframe_formato_seleccionado`

## Panel lateral de documentos

- Panel: `#div_panel_lateral_historia` (display:none por defecto)
- Visualización: `#div_visualizar_historia2`
- Iframe de impresión: `#iframeImpresionHistoria` → `balanceo-reportes.medifolios.net`
- Tabla de documentos seleccionables con columnas:
  - FECHA INICIO
  - COD. RIESGO/ALERGIA
  - DESC. RIESGO/ALERGIA
  - ESTADO
  - FECHA INACTIVACION
  - TRATAMIENTO

## Cómo se usa (flujo de Sandra)

1. Click en "Abrir Formato de Historia" (tercera pestaña de Historia Clínica)
2. Seleccionar formato del dropdown
3. El panel lateral se activa mostrando documentos del paciente
4. Marcar checkboxes de documentos a visualizar
5. Click en "Visualizar Seleccionado" → se renderiza en iframe
6. Click en "Imprimir" para generar PDF/salida
