# Errores comunes ya conocidos — Checklist de verificación

Estos son errores que YA han ocurrido al generar documentos ARL Positiva.
El verificador DEBE buscar estos patrones específicos.

## 1. Columnas duplicadas
- **Síntoma**: Columna extra a la izquierda con texto repetido y letra pequeña
- **Visto en**: Formato 7 Sección 6 (Tratamiento ATEL), Tabla 1
- **Causa**: `_reemplazar_celda_entera` o `_buscar_y_reemplazar` escribe en celda LABEL en vez de celda VALOR
- **Detección**: Comparar texto de celda[0] entre gen y ej — si gen tiene texto clínico largo donde ej tiene un label corto, hay problema
- **Corrección**: Buscar por texto CLÍNICO del valor (ej: "ENFERMEDAD ACTUAL"), no por el label ("Tratamiento recibido")

## 2. Texto amarillo / fondo de celda heredado
- **Síntoma**: Texto con fondo amarillo donde el ejemplo tiene fondo blanco
- **Visto en**: Formato 6 Sección 2 (Metodología)
- **Causa**: `<w:shd fill="FFFF00">` en el `tcPr` de la plantilla, `_poner_texto` no lo limpia
- **Detección**: XML muestra `shd_fill="FFFF00"` en gen pero no en ej
- **Corrección**: Agregar `tcPr.remove(shd)` en `_poner_texto()` — YA IMPLEMENTADO 2026-05-15

## 3. Viñetas vacías
- **Síntoma**: Párrafos con bullet (•) pero sin texto visible
- **Visto en**: Formato 6 Sección 3.1
- **Causa**: Párrafos sobrantes de la plantilla no eliminados tras escribir sección con menos líneas
- **Detección**: Contar párrafos en la sección — gen tiene más que ej
- **Corrección**: Eliminar párrafos sobrantes en reversa con `p._element.getparent().remove(p._element)`

## 4. Espacio blanco gigante
- **Síntoma**: Sección con un espacio en blanco enorme (varias líneas vacías)
- **Visto en**: Formato 6 Sección 7 (Concepto desempeño)
- **Causa**: Celda con merge vertical procesada N veces sin `cell._tc` dedup — cada escritura expande
- **Detección**: Altura anormal de celda vs ejemplo (comparar `tcW` heights en XML)
- **Corrección**: Verificar `_reemplazar_celda_entera` tenga `cell._tc` dedup YA IMPLEMENTADO

## 5. Nombres incompletos en firmas
- **Síntoma**: "SANDRA PATRICIA POLANIA" sin "OSORIO" o solo en 1 columna
- **Visto en**: Formato 7 Sección 11 (Registro)
- **Causa**: `_buscar_y_reemplazar` solo afecta la primera ocurrencia
- **Detección**: Comparar texto de celdas de firma entre gen y ej
- **Corrección**: Usar `_reemplazar_en_tablas` para TODAS las ocurrencias

## 6. Texto azul en vez de negro
- **Síntoma**: "REHABILITACION INTEGRAL LABORAL Y OCUPACIONAL SAS" en azul
- **Visto en**: Formato 7 Sección 11 (Registro)
- **Causa**: Hyperlinks del template sobreviven a `_poner_texto`
- **Detección**: Buscar `<w:hyperlink>` en XML del generado
- **Corrección**: `_eliminar_hyperlinks(p)` en `_poner_texto` — YA IMPLEMENTADO 2026-05-15

## 7. ID Siniestro pegado/duplicado
- **Síntoma**: "5034638705034638870" en vez de "503463870"
- **Visto en**: Formato 7 Sección 1 (Identificación)
- **Causa**: Hyperlink con valor antiguo sobrevive + texto nuevo del run
- **Detección**: Texto de celda más largo de lo esperado
- **Corrección**: Misma que #6 — YA IMPLEMENTADO

## 8. X de checkbox en columna equivocada
- **Síntoma**: X desplazada a la izquierda/derecha de donde está en el ejemplo
- **Visto en**: Formato 7 Nivel educativo, Formato 7 Ocurrencia ATEL
- **Causa**: `_marcar_opcion` malinterpreta bloques de opciones o procesa fila incorrecta
- **Detección**: Comparar posición de X (columna) entre gen y ej
- **Corrección**: Usar acceso directo a celdas por índice cuando el layout de checkboxes no encaja en el modelo de bloques

## 9. Texto clínico con formato incorrecto
- **Síntoma**: Diagnóstico en negrita/grande cuando el ejemplo lo tiene normal/pequeño
- **Visto en**: Formato 7 Diagnóstico clínico
- **Causa**: `_poner_texto` hereda formato del run original de la plantilla
- **Detección**: Comparar `bold` y `sz` (font size) en runs XML
- **Corrección**: Pasar `bold=False` + `font_size=7.5` en `_reemplazar_celda_entera`

## 10. Párrafos separados cuando deben ir juntos
- **Síntoma**: Concepto dividido en 2 bloques con línea en blanco
- **Visto en**: Formato 7 Sección 9 (Concepto ocupacional)
- **Causa**: Split por `\n\n` y escritura en 2 celdas diferentes
- **Detección**: Número de párrafos en la celda del concepto
- **Corrección**: Escribir TODO el texto en UNA sola celda como bloque único

### 11. Número de páginas incorrecto
- **Síntoma**: Encabezado dice "Página 3 de 7" en vez de "Página 3 de 6"
- **Visto en**: Formato 7 general, Formato 1
- **Causa**: Columnas extra, espacio blanco, o texto duplicado que expande el documento
- **Detección**: Comparar número total de páginas (PDF) entre gen y ej
- **Corrección**: Arreglar causa raíz (columnas extra, merge issues, texto en celda angosta)

## Errores descubiertos 2026-05-15 (Análisis de Exigencias)

### 12. Texto vertical / celda angosta explota documento
- **Síntoma**: Texto "25 años y 7 meses" escrito letra por letra verticalmente, documento pasa de 10 a 20+ páginas
- **Visto en**: Formato 1 Filas 27-30 (antigüedad cargo/empresa)
- **Causa**: `_buscar_y_reemplazar` escribe en celda angosta de fecha (C01, w=500) en vez de celda ancha de texto (C09, w=3048)
- **Detección**: Comparar ancho de celda donde se escribe el texto (tcW en XML). Si gen tiene texto en celda con w<1000 pero ej tiene texto en celda con w>3000, hay problema
- **Corrección**: Usar acceso directo `_poner_texto(doc.tables[0].rows[28].cells[9], texto)` en vez de `_buscar_y_reemplazar`

### 13. " / " en vez de saltos de línea
- **Síntoma**: Diagnósticos, programa RHI, o contactos separados por " / " en vez de líneas separadas
- **Visto en**: Formato 1 Diagnóstico, RHI, Contacto empresa
- **Causa**: JSON trae " / " como separador; no se convierte a saltos de línea
- **Detección**: Buscar " / " en celdas de texto clínico del documento generado
- **Corrección**: `texto.replace(" / ", chr(10))` — NUNCA usar `"\n"` literal en el código fuente (rompe el string)

### 14. Número duplicado al final de fila
- **Síntoma**: "59" aparece dos veces en la fila de fecha nacimiento/edad
- **Visto en**: Formato 1 Fila 9 (edad)
- **Causa**: `_buscar_y_reemplazar(doc, "años", edad)` encuentra "Años" en C16 pero escribe en celda equivocada; el valor original del template sobrevive
- **Detección**: Contar ocurrencias del valor en la fila
- **Corrección**: Escribir directo a `doc.tables[0].rows[9].cells[14]`

### 15. Párrafos colapsados en uno solo
- **Síntoma**: Texto continuo donde el ejemplo tiene múltiples párrafos separados
- **Visto en**: Formato 1 Sección 2 (Metodología)
- **Causa**: `_poner_texto` escribe todo en `paragraphs[0]`, ignorando estructura multi-párrafo del template
- **Detección**: Contar elementos `<w:p>` en la celda del generado vs ejemplo
- **Corrección**: Usar `_poner_texto_multiparrafo` que divide por `\n\n` y escribe en párrafos separados

## Protocolo de detección rápida

Al verificar un documento, buscar en este orden:
1. `grep -c "gridSpan"` en XML → ¿mismo número?
2. `grep "FFFF00"` en XML del generado → ¿texto amarillo?
3. `grep "hyperlink"` en XML del generado → ¿hyperlinks residuales?
4. Contar párrafos con bullet → ¿viñetas vacías?
5. Comparar número de páginas del PDF
