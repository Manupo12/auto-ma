# Estrategia de plantillas — Sistema de fisioterapia

## Situación real
Sandra no tiene plantillas en blanco. Tiene documentos de ejemplo ya rellenos con datos de pacientes reales. Los formatos son oficiales de ARL Positiva con tablas complejas y celdas combinadas.

## Enfoque: reemplazo guiado por etiquetas
En vez de crear plantillas con `{{MARCADORES}}`, usamos los documentos de ejemplo como "moldes". El generador busca **etiquetas fijas** del formulario (texto que nunca cambia, como "NOMBRE DEL TRABAJADOR", "CARGO", "No. CÉDULA") y reemplaza el valor en la celda adyacente.

### Por qué no usar marcadores `{{...}}`
- Los documentos tienen celdas combinadas (merged cells) que parten el texto en múltiples "runs"
- Reemplazar texto con regex dentro de runs rompe el formato cuando el texto original está repartido entre varios runs
- Las etiquetas de los formularios oficiales son texto FIJO — siempre igual sin importar el paciente

### Algoritmo v2 (soporta celdas combinadas)
```python
def _buscar_y_reemplazar(doc, etiqueta, valor):
    """Busca etiqueta en tablas y reemplaza valor en celda adyacente.
    Soporta merged cells: detecta frontera entre celdas de etiqueta y valor."""
    etiqueta_lower = etiqueta.lower().strip()
    for tabla in doc.tables:
        for fila in tabla.rows:
            celdas = fila.cells
            # 1. Encontrar inicio de etiqueta
            label_start = None
            for i, celda in enumerate(celdas):
                if etiqueta_lower in celda.text.lower():
                    label_start = i
                    break
            if label_start is None:
                continue
            # 2. Encontrar fin de etiqueta (primera celda sin la etiqueta)
            value_start = None
            for i in range(label_start, len(celdas)):
                if etiqueta_lower not in celdas[i].text.lower():
                    value_start = i
                    break
            if value_start is None:
                continue
            # 3. Poner valor en la primera celda de valor
            _poner_texto(celdas[value_start], str(valor))
            return True
    return False
```

## Pitfall: reemplazo de párrafos (CORREGIDO en v2)

El enfoque original `_reemplazar_texto_parrafos` fallaba porque Word parte el texto en múltiples runs.

**v2 soluciona esto con dos funciones seguras:**

1. `_reemplazar_en_parrafos(doc, viejo, nuevo)` — Busca `viejo` en `p.text` (texto completo del párrafo), reemplaza, limpia TODOS los runs y pone el texto nuevo en el primer run. Seguro y sin corrupción. **No hace nada si `viejo` está vacío.**

2. `_reemplazar_parrafo(doc, texto_busqueda, texto_nuevo)` — Busca un párrafo que CONTENGA `texto_busqueda` y reemplaza TODO el párrafo. Ideal para cartas donde se quiere regenerar un párrafo completo.

### Regla para cartas (Formato 2 - Carta de Medidas, Formato 3 - Carta de Recomendaciones)
- Usar `_reemplazar_en_parrafos` para sustituir datos puntuales (nombre empresa, contacto, teléfono, etc.)
- Para párrafos de texto libre (metodología, recomendaciones), generar el texto con DeepSeek y usar `_reemplazar_parrafo` o `_reemplazar_en_parrafos`.

## CRÍTICO: Iteración de celdas fusionadas (merged cells) — patrón `cell._tc`

**El problema**: python-docx devuelve las celdas fusionadas una vez por cada fila que abarcan. Si una celda merged ocupa 40 filas, `for row in table.rows: for cell in row.cells:` la entrega 40 veces. Escribir en cada iteración produce texto repetido N× y el documento inflado (ej: 3 páginas → 47 páginas).

**El fix — SIEMPRE deduplicar por `cell._tc`:**
```python
procesadas = set()
for tabla in doc.tables:
    for fila in tabla.rows:
        for celda in fila.cells:
            tc = celda._tc          # identificador único de celda física
            if tc in procesadas:
                continue             # ya fue procesada en otra fila (merged)
            procesadas.add(tc)
            # procesar celda normalmente
```

**TODAS las funciones que iteran celdas deben aplicar este patrón.** En `doc_generator.py`:
- `_reemplazar_en_tablas` — principal causante del bug de 47 páginas
- `_buscar_y_reemplazar` — dedup en la celda de valor
- `_marcar_opcion` — dedup en rangos de checkbox
- `_insertar_firma` — dedup en búsqueda de placeholder

**Verificación post-generación:**
- Número de celdas por fila debe ser idéntico al template
- `len(set(id(c._tc) for ...))` debe ser 1 para celdas merged
- Texto no debe aparecer repetido dentro de una misma celda (`celda.text.count("texto") == 1`)


## Algoritmo de checkboxes — `_marcar_opcion` (CORREGIDO en v2)

**Estructura de una fila de checkboxes:**
```
[Label][Opción1][casillas1][Opción2][casillas2][Opción3][casillas3]...
```
Ejemplo real (Cierre de Caso, fila Dominancia):
```
[0-13: "Dominancia"][14-22: "Derecha"][23-24: vacías][25-32: "Izquierda"][33-37: "X"][38-45: "Ambidiestra"][46-47: vacías]
```

**Algoritmo:**
1. Encontrar la fila que contiene la etiqueta (ej: "Dominancia")
2. Identificar dónde termina la etiqueta (`label_end`)
3. Mapear bloques de opciones: texto contiguo ≠ "" y ≠ "X" desde `label_end`
4. Para cada bloque, sus casillas van desde `bloque.end` hasta `bloque_siguiente.start`
5. Limpiar TODAS las X en cada rango de casillas (dedup por `_tc`)
6. Para la opción seleccionada, poner "X" en su rango de casillas (dedup por `_tc`)

Las X van en celdas separadas de las etiquetas — el nombre de la opción NO se borra.

### Formato 1 — Análisis de Exigencias (analisis_de_exigencia.docx)
Tabla 0: encabezado con fecha en celdas individuales
Tabla 1: identificación del trabajador y empresa
- "NOMBRE DEL TRABAJADOR" → nombre
- "No. CÉDULA" → documento
- "ID del SINIESTRO" → id_siniestro
- "Contacto en empresa" → contacto_empresa (con offset)
- etc.

### Formato 5 — Citación de Empresas (ejemplo formato de citacion de empresas.docx)
El más simple — una tabla con pares etiqueta/valor. **Usar substrings** porque los textos exactos varían:
- "CARGO" → l.cargo (funciona: la celda dice "CARGO")
- "TIPO DE ESTUDIO" → v.tipo_estudio (la celda dice "TIPO DE ESTUDIO A REALIZAR")
- "TIEMPO DE EJECUCIÓN" → v.tiempo_ejecucion (la celda dice "TIEMPO DE EJECUCIÓN DEL ESTUDIO")
- "OBJETIVO DEL ESTUDIO" → v.objetivo (coincidencia exacta)
- "FECHA Y HORA" → v.fecha_hora (la celda dice "FECHA Y HORA EN LA CUAL SE REALIZARÁ LA VISITA")
- "AUDITOR" → v.nombre_auditor (la celda dice "NOMBRE DEL AUDITOR DE REHABILITACION")
- "DESCRIPCI" → v.descripcion_estado (la celda dice "DESCRIPCION DEL ESTADO DEL CASO")

**Párrafos**: Usar `_reemplazar_en_parrafos` con los valores ORIGINALES del template (nombre_original, contacto_original). Si no se dispone de los originales, las búsquedas con string vacío se ignoran automáticamente (seguro).

## Archivos de backup
Los originales se respaldan como `.bak` al crear plantillas. Para restaurar:
```bash
cp "archivo.docx.bak" "archivo.docx"
```

## Dependencias
- python-docx — leer/escribir .docx
- LibreOffice headless — convertir .docx a PDF
- Firmas: `~/fisioterapia/templates/assets/firma_sandra.png` (pendiente)

## Constantes y convenciones en doc_generator.py

**`NS_W`** — Namespace XML de WordprocessingML:
```python
NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
```
Usar en todas las funciones que manipulen XML directamente (findall, xpath, SubElement).
Evita hardcodear el namespace y facilita migración entre versiones de OOXML.

**`_eliminar_hyperlinks(parrafo)`** — Helper para limpiar hyperlinks huérfanos.
`paragraph.runs` NO incluye runs dentro de `<w:hyperlink>`, así que
`_poner_parrafo()` no los limpia. Al reemplazar un párrafo completo, llamar
`_eliminar_hyperlinks(p)` después de escribir el nuevo texto para evitar
que el hyperlink original aparezca duplicado al final del párrafo.
