# Bugs Formato 7 — Valoración del Desempeño Ocupacional Final
# Detectados por Sandra en revisión 2026-05-10, corregidos 2026-05-15

## Contexto
Documento generado para JUAN CARLOS DURAN NARVAEZ (CC 1193143688) y enviado a Telegram (msg 48).
Sandra revisó en Word y encontró 10 errores. Todos corregidos en sesión 2026-05-15.

## Lista de bugs

### Bug 1 — ID Siniestro pegado
- **Página**: 1 — Identificación del siniestro
- **Síntoma**: "5034638705034638870" en vez de "503463870"
- **Causa**: Hyperlinks fantasma (pitfall 14). `_poner_texto` limpia runs pero no `<w:hyperlink>`
- **Fix**: `_poner_texto` ahora llama `_eliminar_hyperlinks(p)` en cada párrafo de la celda

### Bug 2 — Nivel educativo X en columna equivocada
- **Página**: 1 — Nivel educativo
- **Síntoma**: X de "Bachillerato: vocacional 9°" desplazada a la izquierda
- **Causa**: `_marcar_opcion` retornaba `True` sin marcar (pitfall 13). La fila 16 ("Especificar formación") era procesada primero, no encontraba la opción, y retornaba impidiendo revisar filas 13-15.
- **Fix**: Eliminar `return True` después del loop de bloques. Solo retornar cuando se marca la opción.

### Bug 3 — Diagnóstico en mayúsculas + negrita + grande
- **Página**: 1 — Diagnóstico clínico
- **Síntoma**: Texto en ALL CAPS, bold, fuente grande
- **Causa**: `_buscar_y_reemplazar` hereda formato del template (bold, font size)
- **Fix**: `_reemplazar_celda_entera(doc, "HERIDA DEL CUARTO DEDO", diag, bold=False, font_size=7.5)`

### Bug 4 — Tiempo incapacidad duplicado
- **Página**: 1 — Tiempo total de incapacidad
- **Síntoma**: "Sin datos | Sin datos" en vez de "0 | Sin datos"
- **Causa**: `_buscar_y_reemplazar` escribe "Sin datos" en celda de "0" sin limpiar el "Sin datos" original
- **Fix**: Si el valor JSON es "Sin datos", NO reemplazar. Conservar "0 | Sin datos" del template.

### Bug 5 — Ocurrencia ATEL sin X marcada
- **Página**: 2 — Sección 5
- **Síntoma**: X no aparece en "Ocurrencia del ATEL" ni en "PUESTO DE TRABAJO — SI"
- **Causa**: El checkbox está pegado al label sin texto de opción intermedio. El algoritmo de bloques de `_marcar_opcion` no puede mapearlo.
- **Fix**: Manejo directo de celdas: `_poner_texto(celdas[1], "X")` para ocurrencia, `celdas[4]` para PUESTO DE TRABAJO. Limpiar checkbox de AREA si no aplica.

### Bug 6 — Columna extra Sección 6
- **Página**: 2 — Información del evento ATEL
- **Síntoma**: Columna extra a la izquierda con texto repetido en letra pequeña
- **Causa**: `_reemplazar_celda_entera(doc, "Tratamiento recibido por Rehabilitación", ...)` encuentra "Tratamiento recibido" en la celda LABEL [0], no en la celda VALOR [2]. Reemplaza el label con texto clínico, dejando el valor viejo en otra celda → columna extra.
- **Fix**: Buscar por texto CLÍNICO: `"ENFERMEDAD ACTUAL"` (presente solo en la celda de valor, no en el label).

### Bug 7 — "Página 3 de 7" vs "3 de 6"
- **Síntoma**: Número de páginas incorrecto en encabezados
- **Causa**: Duplicaciones de texto (bugs 1,4,6) expanden el documento
- **Fix**: Se corrige automáticamente con los demás fixes.

### Bug 8 — Concepto en 2 bloques separados
- **Página**: 6 — Concepto ocupacional
- **Síntoma**: Texto en fuente grande, dos bloques con línea en blanco
- **Causa**: `concepto.split("\n\n", 1)` divide en 2 partes escritas en celdas distintas (Tabla 3 F39 y Tabla 4 F00)
- **Fix**: Escribir TODO como un solo bloque: `_reemplazar_celda_entera(doc, "Afiliado de", concepto, bold=False, font_size=7.5)`

### Bug 9a — Nombre incompleto en Registro
- **Página**: 7 — Registro columna izquierda
- **Síntoma**: "SANDRA PATRICIA POLANIA" sin "OSORIO"
- **Causa**: `_buscar_y_reemplazar` solo primera ocurrencia. Columna derecha tenía "Nombre y Apellido".
- **Fix**: `_reemplazar_en_tablas` para reemplazar TODAS las ocurrencias de ambos textos.

### Bug 9b — Texto azul en Registro
- **Página**: 7 — "REHABILITACION INTEGRAL LABORAL Y OCUPACIONAL SAS" en azul
- **Causa**: Hyperlink del template sobrevive (pitfall 14)
- **Fix**: `_poner_texto` ahora limpia hyperlinks → texto negro.

### Bug 10 — Columna estrecha Sección 6
- **Síntoma**: Columna izquierda demasiado estrecha, texto ilegible
- **Causa**: Consecuencia del bug 6
- **Fix**: Se corrige con fix 6.

## Lecciones aprendidas

1. **NUNCA buscar por texto del LABEL en `_reemplazar_celda_entera`** — buscar por contenido CLÍNICO
2. **`_marcar_opcion` no funciona con checkboxes pegados al label** — usar acceso directo
3. **`_buscar_y_reemplazar` solo afecta primera ocurrencia** — usar `_reemplazar_en_tablas` para múltiples
4. **Hipervínculos son la causa #1 de duplicación** — `_poner_texto` debe limpiarlos siempre
