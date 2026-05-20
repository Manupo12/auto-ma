---
name: generar-documento
description: Genera los 7 formatos clínicos de fisioterapia a partir del JSON de extracción. Usa python-docx + LibreOffice headless.
triggers:
  - "generar soap"
  - "generar historia"
  - "generar incapacidad"
  - "generar plan"
  - "generar evolución"
  - "generar documento"
  - "generar analisis"
  - "generar medidas"
  - "generar recomendaciones"
  - "generar cierre"
  - "generar citacion"
  - "generar prueba"
  - "generar valoracion"
  - "generar voi"
  - "generar VOI"
---

# Generar documento clínico — 7 formatos

## Tecnología
- **python-docx** — clona la plantilla Word y reemplaza valores por etiqueta (ver `references/estrategia-plantillas.md`)
- **LibreOffice headless** — convierte .docx final a PDF sin interfaz gráfica
- **Plantillas** — en `~/fisioterapia/templates/formatos/` (documentos de ejemplo usados como moldes)
- **Firma** — `~/fisioterapia/templates/assets/firma_sandra.png`
- **Biblioteca** — `~/fisioterapia/backend/doc_generator.py`
- **Envío Telegram** — `references/telegram-envio.md` (API directa para revisión de documentos)

## Estrategia de reemplazo (v2 — CORREGIDA)

**Usar reemplazo por etiqueta, NO por marcador.** Las plantillas son documentos ya rellenos.
El generador busca las etiquetas fijas del formulario (ej: "NOMBRE DEL TRABAJADOR", "CARGO")
en las celdas y reemplaza el valor en la celda adyacente.

### Funciones clave (v5)
- `_buscar_y_reemplazar(doc, etiqueta, valor)` — Busca etiqueta en tablas y reemplaza en la celda de valor.
- `_reemplazar_celda_entera(doc, texto_busqueda, texto_nuevo, bold=None, font_size=None)` — Reemplaza TODO el contenido de una celda. Usar para textos multilínea. **CRÍTICO: buscar por substring del CONTENIDO CLÍNICO, nunca por el label de la fila.**
- `_reemplazar_parrafo(doc, texto_busqueda, texto_nuevo)` — Reemplaza párrafo completo. Limpia hyperlinks.
- `_reemplazar_en_parrafos(doc, viejo, nuevo)` — Reemplaza texto dentro de párrafos.
- `_reemplazar_en_tablas(doc, viejo, nuevo)` — Reemplaza TODAS las ocurrencias de texto en celdas.
- `_poner_fecha_celdas(doc, etiqueta_fecha, fecha_str)` — Escribe dígitos de fecha en celdas D1/D2 M1/M2 A1/A2/A3/A4.
- `_marcar_opcion(doc, etiqueta, opcion)` — Marca X en checkbox. Solo retorna True si encontró y marcó la opción.
- `_marcar_opcion_en_tabla(tabla, opcion)` — Marca X en checkbox de tabla de conclusiones (celda ANTERIOR a la opción).
- `_llenar_perfil_exigencias(tabla, perfil)` — Llena el Anexo de Formato 1 (96 filas, 10 cols). Scores 0-4 en cols 2-6.
- `_poner_parrafo(parrafo, texto)` — Limpia y reescribe párrafo.
- `_eliminar_hyperlinks(parrafo)` — Elimina `<w:hyperlink>` de un párrafo.
- `_poner_texto(celda, texto, bold=None, font_size=None)` — Limpia celda (runs + hyperlinks) y escribe texto nuevo. Solo elimina shading amarillo (FFFF00), respeta colores decorativos (FCE9D9).
- `_poner_texto_multiparrafo(celda, texto, bold=None, font_size=None)` — Como `_poner_texto` pero divide por `\n\n` y escribe cada parte en un párrafo separado. Para secciones con múltiples párrafos.

### Bugs corregidos en v2
1. **`_poner_texto`**: El `elif` muerto (línea 64) fue eliminado. Ahora maneja correctamente runs vacíos.
2. **Celdas combinadas**: `_buscar_y_reemplazar` ahora detecta dónde termina la etiqueta y empieza el valor en tablas con merged cells.
3. **Reemplazo en párrafos**: `_reemplazar_en_parrafos` ya no corrompe texto. Reconstruye el párrafo completo en vez de reemplazar run por run. Además, rechaza strings vacíos para evitar el bug `"".replace("", "X")`.
4. **Funciones obsoletas eliminadas**: `_reemplazar_texto_global`, `_reemplazar_texto_parrafos` (reemplazadas por versiones seguras).
5. **`_marcar_opcion`**: Ahora limpia todas las X existentes en la fila antes de marcar la opción correcta. Evita X residuales del template.

### Pitfalls conocidos (v2)

1. **CRÍTICO — Celdas fusionadas (merged cells) y `cell._tc`**: python-docx itera celdas fusionadas una vez por cada fila que abarcan. Si una celda merged ocupa 40 filas, `for row in table.rows: for cell in row.cells:` la devuelve 40 veces. **Solución**: deduplicar con `cell._tc` como clave única. TODAS las funciones que iteran celdas deben hacerlo:
   ```python
   procesadas = set()
   for row in tabla.rows:
       for cell in row.cells:
           if cell._tc in procesadas:
               continue
           procesadas.add(cell._tc)
           # ahora sí procesar
   ```
   Funciones corregidas: `_reemplazar_en_tablas`, `_buscar_y_reemplazar`, `_marcar_opcion`, `_insertar_firma`. Sin este fix, el texto se repite N× y el documento pasa de 3 a 47 páginas.

2. **Checkboxes — algoritmo de bloques**: `_marcar_opcion` identifica bloques de opciones en una fila (texto contiguo ≠ "" y ≠ "X") y asigna las casillas (celdas entre el fin de un bloque y el inicio del siguiente). La X va en las celdas de casilla, NO sobre la etiqueta. Primero limpia TODAS las X de la fila, luego marca solo la correcta.

3. **String vacío en reemplazos**: `_reemplazar_en_parrafos` y `_reemplazar_en_tablas` ignoran `viejo=""` porque `"".replace("", "X")` inserta X entre cada carácter → corrupción masiva. **Mejor práctica (v3): usar el texto LITERAL de la plantilla como clave de búsqueda** en vez de depender de campos `_original` del JSON. Ej: `_reemplazar_en_parrafos(doc, "Seccional Rama Judicial Neiva", e.get("nombre"))` — el texto de búsqueda es el valor exacto que aparece en el template. Esto elimina la necesidad de campos `nombre_original`, `contacto_original`, etc.

4. **LibreOffice**: El binario puede estar en `/usr/lib/libreoffice/program/soffice` (Debian) o en PATH. `_convertir_a_pdf` prueba ambos. En Docker, `apt-get update` antes de `apt-get install libreoffice-writer`.

5. Etiquetas en citacion: Los nombres de etiquetas varian entre plantillas. Usar substrings comunes como FECHA Y HORA en vez de FECHA Y HORA DE LA VISITA, DESCRIPCI en vez de DESCRIPCION DEL ESTADO ACTUAL.

6. _reemplazar_en_tablas vs _reemplazar_celda_entera: Para celdas con texto multilinea (Seccion 4 actividades, Seccion 5 motivo consulta, Seccion 7 concepto integral), NUNCA usar _reemplazar_en_tablas porque hace append y duplica. Usar _reemplazar_celda_entera que reemplaza TODO el contenido de la celda de una vez. Ver references/debugging-merged-cells.md para guia completa.

7. Preservacion de formato clinico: No reformatear el texto de la doctora. Sin bullets, sin cambios de mayusculas/minusculas, sin resumenes. El JSON debe contener el texto literal.

### Pitfalls v3 — Hipervínculos, doble viñeta, viñetas vacías (corregidos)

8. **CRÍTICO — Hipervínculos fantasma en párrafos**: `paragraph.runs` de python-docx NO incluye los runs dentro de elementos `<w:hyperlink>`. Al reemplazar un párrafo con `_poner_parrafo()`, los hyperlinks sobreviven como texto fantasma al final del párrafo, causando duplicación (ej: email triplicado, siniestro duplicado). **Solución**: `_eliminar_hyperlinks(parrafo)` — busca y elimina todos los `<w:hyperlink>` del párrafo. AMBAS funciones `_reemplazar_parrafo` Y `_reemplazar_en_parrafos` la llaman automáticamente después de escribir el nuevo texto. Si se usa `_poner_parrafo` directamente, llamar `_eliminar_hyperlinks` manualmente después.

9. **Doble viñeta (• - texto) en secciones de lista**: Al escribir líneas con prefijo "- " en párrafos con estilo "List Paragraph", el bullet de Word (•) se suma al guion manual, resultando en "• - texto". **Solución en `_reemplazar_seccion_parrafos`**:
   - Usar `p.clear()` (no `_poner_parrafo`) para limpiar runs preservando `numPr`
   - Strip de prefijos manuales con regex: `re.sub(r'^[\s]*[-•*]\s*', '', linea)`
   - Detectar `numPr` en párrafos hermanos y copiarlo con `deepcopy(numPr_ref)` a los párrafos que no lo tienen
   - Usar `p.add_run(linea)` en vez de `_poner_parrafo` para que el `numPr` aplique el bullet nativo
   - Si no hay `numPr` disponible (sin bullet de formato), conservar "- " manual como fallback

10. **Viñetas vacías residuales**: Cuando la plantilla tiene M párrafos en una sección pero solo se escriben N < M líneas, los M-N párrafos sobrantes quedan como bullets sin texto (estilo "List Paragraph" con runs vacíos). **Solución**: Después de escribir las N líneas, eliminar los elementos XML sobrantes iterando en reversa con `p._element.getparent().remove(p._element)`. Iterar en reversa (`range(idx_fin-1, idx_inicio+len(lineas), -1)`) para que los índices no se desplacen al borrar.

### Pitfalls v4 — Sombreado heredado y merge vertical (Prueba de Trabajo)

11. **Texto amarillo / sombreado heredado en celdas**: Las plantillas de ARL Positiva usan celdas con color de fondo amarillo (`<w:shd fill="FFFF00">` en `<w:tcPr>`) para resaltar campos como Metodología. Al reemplazar el texto con `_poner_texto()` o `_reemplazar_celda_entera()`, el sombreado se hereda porque estas funciones solo limpian párrafos/runs, no las propiedades de la celda (`tcPr`). **Solución**: Agregar limpieza CONDICIONAL de `shd` en `_poner_texto()` después de limpiar párrafos — SOLO eliminar si `fill == 'FFFF00'` (amarillo). NUNCA eliminar otros colores decorativos como `FCE9D9` (durazno) que son parte del diseño legítimo de la plantilla:
   ```python
   # Limpiar SOLO sombreado amarillo, respetar colores decorativos
   tcPr = celda._tc.find(f'{{{NS_W}}}tcPr')
   if tcPr is not None:
       shd = tcPr.find(f'{{{NS_W}}}shd')
       if shd is not None:
           fill = shd.get(f'{{{NS_W}}}fill', '')
           if fill == 'FFFF00':
               tcPr.remove(shd)
   ```

12. **Espacio en blanco gigante por merge vertical mal manejado**: En la tabla maestra de Prueba de Trabajo (Tabla 0), celdas como "Concepto de desempeño" (Sección 7) están fusionadas verticalmente abarcando 20+ filas. Si la función que escribe el concepto (`_reemplazar_celda_entera`) NO usa `cell._tc` para deduplicar, procesa la celda N veces (una por cada fila del merge). Cada escritura acumula runs en el mismo párrafo, expandiendo la celda desproporcionadamente y generando un espacio en blanco gigante. **Solución**: VERIFICAR que `_reemplazar_celda_entera` tenga `cell._tc` dedup. Si ya lo tiene, el problema puede ser que `cell._tc` sea compartido con otra celda del merge, o que la función `_poner_texto` no esté limpiando correctamente antes de escribir (usa `celda.paragraphs[0].clear()` ANTES de `add_run`).

### Pitfalls v6 — _buscar_y_reemplazar celda equivocada, chr(10), texto multilínea (Análisis Exigencias)

16. **CRÍTICO — `_buscar_y_reemplazar` escribe en celda angosta en filas con celdas de fecha**: En formatos con fechas en celdas individuales (día/mes/año), la fila de datos tiene celdas angostas para dígitos SEGUIDAS de una celda ancha para el texto (ej: antigüedad). `_buscar_y_reemplazar` encuentra el label en la celda [0], y `value_start` cae en la primera celda sin label — que es una celda angosta de dígito (w=500), NO la celda ancha de texto (w=3048). El texto se escribe en una celda minúscula, forzando wrap vertical letra por letra y EXPLOTANDO el documento de 10 a 20+ páginas. **Visto en**: Formato 1 filas 27-30 (antigüedad cargo/empresa). **Solución**: NO usar `_buscar_y_reemplazar` para estos campos. Usar acceso directo por índice: `_poner_texto(doc.tables[0].rows[28].cells[9], antiguedad)`. **Regla**: si una fila tiene celdas de fecha (día/mes/año) seguidas de un campo de texto, siempre usar acceso directo, nunca `_buscar_y_reemplazar`.

17. **CRÍTICO — `chr(10)` para saltos de línea en reemplazos de texto, NUNCA `"\n"` en el código fuente**: Al escribir `texto.replace(" / ", "\n")` en el archivo .py, el `\n` se convierte en un salto de línea FÍSICO en el código fuente, rompiendo el string literal y causando `SyntaxError: unterminated string literal`. **Solución**: Usar `chr(10)` en vez de `"\n"`:
   ```python
   # ✅ CORRECTO
   diag_texto = diag_texto.replace(" / ", chr(10))
   
   # ❌ INCORRECTO — rompe el código fuente
   diag_texto = diag_texto.replace(" / ", "\n")
   ```
   Aplica a TODOS los campos que necesiten convertir separadores " / " en saltos de línea: diagnósticos, programa RHI, contactos, etc.

18. **`_poner_texto_multiparrafo(celda, texto, bold=None, font_size=None)`** — NUEVA función para preservar estructura de párrafos del template. A diferencia de `_poner_texto` que escribe todo en `paragraphs[0]`, esta función divide el texto por `\n\n` y escribe cada parte en un párrafo separado. Limpia shading amarillo, hyperlinks, y párrafos existentes antes de escribir. Usar para secciones donde el template tiene múltiples párrafos independientes (ej: Metodología en Formato 1). Si el texto no contiene `\n\n`, se comporta igual que `_poner_texto`.

19. **Acceso directo por índice como fallback**: Cuando `_buscar_y_reemplazar` o `_reemplazar_celda_entera` no son confiables (celdas de fecha, layouts complejos, búsqueda que matchea múltiples celdas), usar acceso directo: `_poner_texto(doc.tables[T].rows[R].cells[C], valor, bold=False, font_size=7.5)`. Este patrón es más verboso pero 100% determinista. **Casos donde se usa**: antigüedad cargo/empresa (Formato 1), edad (Formato 1), diagnóstico (Formato 1), RHI (Formato 1), checkboxes de Ocurrencia ATEL (Formato 7).

### Pitfalls v5 — _marcar_opcion retorno prematuro y _poner_texto hyperlinks (Valoración Desempeño)

13. **_marcar_opcion retorna True sin marcar**: Si una fila contiene la etiqueta pero NINGUNA de sus opciones coincide con `opcion_a_marcar`, la función retornaba `True` al final del loop de bloques, impidiendo que se revisaran filas subsiguientes. Esto causaba que checkboxes como "Nivel educativo" no se marcaran si una fila anterior con la misma etiqueta (ej: fila 16 "Especificar formación") era procesada primero. **Solución**: Eliminar el `return True` después del loop de bloques. Solo retornar `True` cuando se encuentra y marca la opción. Si no se encuentra en esta fila, continuar con la siguiente.

14. **Hipervínculos fantasma en celdas de tabla**: `paragraph.runs` de python-docx NO incluye runs dentro de `<w:hyperlink>`. `_poner_texto()` solo limpiaba `run.text = ""` pero los hyperlinks sobrevivían, causando texto duplicado (ID siniestro pegado, "Sin datos | Sin datos", columna extra en Sección 6, texto azul en Registro). **Solución**: `_poner_texto()` ahora llama `_eliminar_hyperlinks(p)` para CADA párrafo de la celda, eliminando todo `<w:hyperlink>` antes de escribir el nuevo texto. Esto resuelve de raíz todos los bugs de duplicación en tablas.

15. **`_reemplazar_celda_entera` sobreescribe el LABEL si se busca por texto del label**: La función busca la PRIMERA celda que contenga el texto de búsqueda. Si el texto de búsqueda aparece en la celda del label (ej: "Tratamiento recibido por Rehabilitación"), reemplaza el label en vez del valor. **Solución**: Buscar SIEMPRE por un substring del CONTENIDO CLÍNICO que solo aparezca en la celda de valor (ej: "ENFERMEDAD ACTUAL", "HERIDA DEL CUARTO DEDO", "ESGUINCE GRADO I"). Si no hay contenido clínico distintivo, usar acceso directo por índice de celda con `_poner_texto(tabla.rows[fila].cells[col], texto)`.

## Flujo de generación (TODOS los formatos)
0. **ANTES de generar: VERIFICACIÓN OBLIGATORIA contra portales.** Todo dato del paciente DEBE ser confirmado en Medifolios y ARL Positiva antes de generar el documento. Sin verificación, el formato NO se da por terminado:
   - Siniestro: cruzar Medifolios (Agenda Citas → Observaciones) vs Positiva (Consulta integral → SINIESTROS). Prevalecer Positiva.
   - Datos personales: confirmar nombre, CC, fecha nacimiento, dirección en Medifolios.
   - Diagnóstico: confirmar CIE-10 en Positiva (Rehabilitación Integral).
   - Empresa: confirmar NIT y razón social en Positiva (Datos Asegurado).
   - Marcas: ✅ verificado ⚠️ pendiente ❌ discrepancia 👤 dato paciente.
   - Si no hay datos extraídos → disparar extracción vía `POST /api/verificar/{cc}/extraer` (usa `puente_docker.py` → docker exec).
   - Si la extracción no es posible → marcar TODOS los campos como ⚠️ pendiente y advertir a Sandra.
1. **Validar JSON** con `backend/json_validator.py` — verifica que el JSON tenga todos los campos requeridos para el formato. Si faltan campos `required`, la generación se BLOQUEA. Campos `recommended` faltantes se auto-completan con `[VERIFICAR]`. Ver `references/flujo-pre-generacion.md`.
2. Cargar plantilla desde `templates/formatos/[nombre].docx`
3. Reemplazar valores usando etiquetas fijas del formulario
4. Marcar opciones checkbox con `_marcar_opcion`
5. Insertar fechas en celdas individuales con `_poner_fecha_celdas`
6. Insertar firma de la doctora
7. Guardar .docx en `storage/docs/[tipo]-[documento]-[fecha].docx`
8. Convertir a PDF
9. Si APROBADO: PDF/A + metadata custodia

### v3 — Reemplazo de celdas completas y preservación de texto clínico

**`_reemplazar_celda_entera(doc, texto_busqueda, texto_nuevo, bold=None, font_size=None)`** — NUEVA función.
Busca una celda que CONTENGA `texto_busqueda` y reemplaza TODO su contenido de una sola vez.
Usar SIEMPRE en vez de `_reemplazar_en_tablas` para celdas con texto multilínea
(actividades, motivo consulta, concepto integral, etc.). `_reemplazar_en_tablas` hace append
y duplica el contenido. `_reemplazar_celda_entera` escribe la celda completa de una vez.
Soporta `bold=None/True/False` para control de formato, `font_size` en puntos, y `cell._tc` para dedup.

**`_reemplazar_seccion_parrafos(doc, inicio, fin, texto_nuevo)`** — NUEVA función.
Para cartas (formatos 2 y 3). Busca párrafos ancla (`inicio` y `fin`) y reemplaza todos
los párrafos ENTRE ellos con el contenido de `texto_nuevo`. Cada línea se vuelve un párrafo.
**Corrección v3:** Usa `p.clear()` + `p.add_run(linea)` en vez de `_poner_parrafo`. Detecta `numPr`
(bullet de Word) para heredarlo entre párrafos hermanos y NUNCA incluye guion manual (-) si el
párrafo ya tiene formato bullet, evitando el bug de "• - texto" (doble viñeta). Elimina párrafos
sobrantes de la plantilla iterando en reversa para no dejar viñetas vacías.
Usar para secciones de recomendaciones donde el contenido varía completamente entre pacientes.
Ejemplo: `_reemplazar_seccion_parrafos(doc, "PARA LA SERVIDORA:", "RECOMENDACIONES PARA EL DESARROLLO", texto)`

**`_poner_texto(celda, texto, bold=None)`** — Ahora acepta `bold` para forzar
negrita (True) o quitarla (False). Útil cuando la plantilla tiene bold que se hereda
al nuevo texto.

**Regla de preservación de texto clínico**: El texto que proporciona la doctora debe
copiarse EXACTAMENTE como ella lo escribió. Cero reformateo, cero bullets, cero cambios
de mayúsculas/minúsculas, cero resúmenes. El JSON clínico es el texto LITERAL del
documento oficial de ARL Positiva. Si la doctora escribió "GONIOMETRIA RANGO DE
MOVILIDAD PASIVO" en mayúsculas, así se conserva.

### Campos nuevos en `consulta` y `recomendaciones`
Para Cierre de Caso (Formato 4), Sección 5:
- `motivo_consulta`, `enfermedad_actual`, `descripcion_furat` (texto FURAT literal),
  `examen_fisico`, `analisis_recomendaciones`, `plan_manejo`

Para Carta de Medidas (Formato 2):
- `consulta.cuerpo_carta` — párrafo inicial
- `recomendaciones.trabajador_texto` — sección "PARA LA SERVIDORA" (texto con \n)
- `recomendaciones.tareas_texto` — sección "RECOMENDACIONES PARA EL DESARROLLO DE LAS TAREAS"
- `recomendaciones.empresa_texto` — sección "PARA LA ENTIDAD"
```python
from backend.doc_generator import generar_documento
# O importar generadores individuales:
from backend.doc_generator import (
    generar_analisis_exigencia,
    generar_carta_medidas,
    generar_carta_recomendaciones,
    generar_cierre_caso,
    generar_citacion_empresas,
    generar_prueba_trabajo,
    generar_valoracion_desempeno,
)
# Uso:
docx_path = generar_documento("cierre", datos, output_name="cierre-1193143688-2026-05-01")
# → storage/docs/cierre-1193143688-2026-05-01.docx + PDF

# Acceso a datos: usar _extraer_secciones(datos, extra=[...])
# Retorna (p, e, l, s, c, *extras) donde p=paciente, e=empresa, l=laboral, s=siniestro, c=consulta
```

## Reglas absolutas
1. **Nunca inventar información clínica.** Usar solo lo que está en las fuentes.
2. Si un campo no tiene información: escribir `[VERIFICAR]`
3. Ningún documento se envía sin aprobación explícita de la doctora
4. Campos de fecha en celdas individuales: un dígito por celda (D1 D2 / M1 M2 / A1 A2 A3 A4)
5. Casillas con X: la opción correcta lleva "X", las demás vacías
6. Fotos no disponibles: "Sin registro fotográfico en el momento de la visita"
7. Fecha desconocida: `[VERIFICAR FECHA]`
8. Atribucion fija al pie SIEMPRE: SANDRA PATRICIA POLANIA OSORIO / Fisioterapeuta Esp. SO / REHABILITACION INTEGRAL LABORAL Y OCUPACIONAL SAS
9. Cedulas colombianas: Sandra escribe 12'130.558 pero el sistema usa 12130558. Limpiar siempre puntos y apostrofes.

---

## FORMATO 1 — Análisis de Exigencias / Homologación
**Archivo plantilla:** `ejemplo analisis de exigencia.docx` | **Complejidad:** Alta
**Función:** `generar_analisis_exigencia(datos, output_name=None)` — expandida 2026-05-15 para cubrir TODAS las secciones.
**Script prueba:** `test_analisis_laura.py` (LAURA ROJAS ZUÑIGA, CC 36184789)
**Cuándo:** Visita al puesto de trabajo para analizar si el trabajador puede desempeñar su cargo.

### Arquitectura del template (7 tablas)
- **Tabla 0 (32 filas × 22 cols):** Encabezado (F00-F04) + Sección 1 Identificación (F05-F31). Fecha en celdas individuales, campos label→value, checkboxes de dominancia y nivel educativo, fechas de nacimiento/ingreso en celdas día/mes/año.
- **Tabla 1 (33 filas × 5 cols):** Contacto empresa (F00-F03) + Sección 2 Metodología (F05-F06) + Sección 3 Antecedentes (F08-F10) + Sección 4 Condiciones de trabajo 4.1-4.4 (F12-F26) + Sección 5 Tarea 1 datos (F28-F32).
- **Tabla 2 (10 filas × 8 cols):** Tarea 1 — Apreciaciones (trabajador + profesional) y Conclusión (checkbox + descripción).
- **Tabla 3 (4 filas × 4 cols):** Tarea 2 — Datos (actividad, ciclo, subactividad, estándar, descripción).
- **Tabla 4 (10 filas × 8 cols):** Tarea 2 — Apreciaciones y Conclusión.
- **Tabla 5 (25 filas × 6 cols):** Sección 6 Materiales (F02-F06, 5 items) + Sección 7 Peligros (F10-F15, 6 categorías) + Sección 8 Concepto desempeño (F17-F18) + Sección 9 Recomendaciones (F20-F24).
- **Tabla 6 (96 filas × 10 cols):** Anexo Perfil de Exigencias (F00-F90, ~85 ítems) + Sección 10 Registro/Firmas (F91-F95).

### Estrategia de reemplazo por sección

**Sección 1 — Identificación (Tabla 0):**
Usar `_buscar_y_reemplazar` con substrings del template. Las fechas usan `_poner_fecha_celdas`. El diagnóstico usa `_reemplazar_celda_entera` con `font_size=7.5, bold=False` buscando por substring del contenido clínico (ej: "ESGUINCE GRADO I"). Campos:
- `"Nombre del trabajador"` → `p.nombre`
- `"Número de documento"` → `p.documento`
- `"Identificación del siniestro"` → `s.id_siniestro`
- `"Fecha de nacimiento/edad"` → `_poner_fecha_celdas` + `"años"` → `p.edad`
- `"Dominancia"` → `_marcar_opcion`
- `"Estado civil"` → `p.estado_civil`
- `"Nivel educativo"` → `_marcar_opcion` + `"Otros"` → `p.formacion_otros`
- `"Teléfonos trabajador"` → `p.telefono`
- `"Dirección residencia"` → `p.direccion`
- Diagnóstico: `_reemplazar_celda_entera(doc, "ESGUINCE GRADO I", s.diagnosticos, bold=False, font_size=7.5)`
- `"Fecha(s) del evento(s) ATEL"` → `s.fecha_evento`
- `"EPS - IPS"`, `"AFP"`, `"Tiempo total de incapacidad"`
- `"Empresa donde labora"`, `"NIT de la Empresa"`, `"Cargo actual"`, `"Área/sección/proceso"`
- `"Fecha ingreso cargo"` → `_poner_fecha_celdas` + `"antigüedad en el cargo"`
- `"Fecha ingreso a la empresa"` → `_poner_fecha_celdas` + `"antigüedad en la empresa"`
- `"Forma de vinculación laboral"` → `l.vinculacion`

**Sección 2 — Metodología (Tabla 1 F06):**
`_reemplazar_celda_entera(doc, "La metodología utilizada", c.metodologia, bold=False, font_size=7.5)`

**Sección 3 — Antecedentes (Tabla 1 F09-F10):**
- `_reemplazar_celda_entera(doc, "Servidora de", c.resultados_valoracion, ...)`
- `_reemplazar_celda_entera(doc, "Medicina laboral", c.programa_rhi, ...)`

**Sección 4 — Condiciones de trabajo (Tabla 1 F12-F26):**
- 4.1: `_reemplazar_celda_entera(doc, "La Servidora manifiesta las siguientes funciones", c.proceso_productivo, ...)`
- 4.2: `_reemplazar_celda_entera(doc, "La servidora menciona que ejecuta las tareas", c.apreciacion_trabajador, ...)`
- 4.3: `_reemplazar_celda_entera(doc, "El ritmo de trabajo se desarrolla", c.estandares_productividad, ...)`
- 4.4: `_buscar_y_reemplazar` para Jornada, Ritmo, Descansos programados, Turnos, Tiempos efectivos, Rotaciones, Horas extras, Distribución semanal. Datos de `laboral.*`.

**Sección 5 — Tareas críticas:**
- Tarea 1: Datos en Tabla 1 (F28-F32) con `_buscar_y_reemplazar` para Actividad, Ciclo, Subactividad, Estándar. Descripción con `_reemplazar_celda_entera(doc, "La Servidora realiza las siguientes tareas con uso de computador", ...)`. Apreciaciones en Tabla 2 con `_reemplazar_celda_entera` buscando "La servidora indica que realiza las tareas administrativas" y "Servidora sin limitación en las funciones". Conclusión con `_marcar_opcion_en_tabla(tabla2, tipo)` y `_reemplazar_celda_entera` para la descripción.
- Tarea 2: Datos en Tabla 3 con `_poner_texto` directo por índice de celda (`.cells[1]`, `.cells[3]`). Apreciaciones en Tabla 4 con `_reemplazar_celda_entera` buscando "La trabajadora manifiesta limitación moderada" y "La servidora puede realizar la actividad teniendo". Conclusión igual que Tarea 1.

**Sección 6 — Materiales (Tabla 5 F02-F06):**
5 filas máximo. `_poner_texto` directo en `tabla.rows[2+idx].cells[0,2,3]` para nombre, estado, requerimientos.

**Sección 7 — Peligros (Tabla 5 F10-F15):**
6 filas máximo. `_poner_texto` directo en `tabla.rows[10+idx].cells[0,2,4,5]` para nombre, descripción, control, recomendación.

**Sección 8 — Concepto (Tabla 5 F18):**
`_reemplazar_celda_entera(doc, "La servidora se desempeña en el cargo", c.concepto_desempeno, bold=False, font_size=7.5)`

**Sección 9 — Recomendaciones (Tabla 5 F22, F24):**
`_reemplazar_celda_entera(doc, "Las recomendaciones relacionadas con el presente análisis", rec.trabajador, ...)`. Si trabajador y empresa tienen el mismo texto, el segundo match se omite (la función retorna tras el primer éxito).

**Anexo Perfil de Exigencias (Tabla 6, 96 filas):**
Función `_llenar_perfil_exigencias(tabla, perfil)`. Itera todas las filas de la tabla, busca cada ítem por nombre en el dict `perfil`, y marca X en la columna correspondiente:
- Columnas de score: [2]=0, [3]=1, [4]=2, [5]=3, [6]=4. Columna [7]=observaciones.
- Los valores pueden ser `int` (solo score) o `tuple(score, observacion)`.
- Primero limpia X previas en las columnas 2-6, luego escribe X en la correcta.
- Secciones del perfil: vision, audicion, sensibilidad, olfato_gusto, motricidad_gruesa, motricidad_fina, armonia, cognitivos, sociales_laborales, laborales.

**Sección 10 — Registro (Tabla 6 F91-F95):**
`_reemplazar_celda_entera` buscando "BIBIANA HORTA PERDOMO" → `registro.elaboro` y "JENNY MARITZA RIVERA POLANIA" → `registro.reviso`.

### Funciones auxiliares específicas de este formato

- **`_llenar_perfil_exigencias(tabla, perfil)`** — Llena el Anexo completo (96 filas). Busca cada ítem en el dict `perfil`, marca X en columna 2+score, escribe observación en columna 7. Ver `references/perfil-exigencias-scoring.md`.

- **`_marcar_opcion_en_tabla(tabla, opcion)`** — Marca X en el checkbox de una fila de conclusiones. Busca la fila con "Conclusión:", encuentra la opción correcta, y pone X en la celda ANTERIOR a dicha opción (que es el checkbox). Limpia X previas en celdas checkbox cercanas.

### JSON Schema específico
```json
{
  "paciente": {
    "nombre": "", "documento": "", "fecha_nacimiento": "DD/MM/AAAA",
    "edad": "", "dominancia": "Derecha/Izquierda",
    "estado_civil": "", "nivel_educativo": "",
    "formacion_otros": "", "telefono": "", "direccion": "",
    "eps_ips": "", "afp": ""
  },
  "empresa": {
    "nombre": "", "nit": "", "contacto": "",
    "correo": "", "telefono": "", "direccion": ""
  },
  "laboral": {
    "cargo": "", "area": "",
    "fecha_ingreso_cargo": "DD/MM/AAAA", "antiguedad_cargo": "",
    "fecha_ingreso_empresa": "DD/MM/AAAA", "antiguedad_empresa": "",
    "vinculacion": "",
    "jornada": "", "ritmo": "", "descansos": "",
    "turnos": "", "tiempos_efectivos": "", "rotaciones": "",
    "horas_extras": "", "distribucion_semanal": ""
  },
  "siniestro": {
    "id_siniestro": "", "fecha_evento": "DD/MM/AAAA",
    "diagnosticos": "", "tiempo_incapacidad": ""
  },
  "consulta": {
    "fecha": "DD/MM/AAAA",
    "metodologia": "", "resultados_valoracion": "",
    "programa_rhi": "", "proceso_productivo": "",
    "apreciacion_trabajador": "", "estandares_productividad": "",
    "concepto_desempeno": ""
  },
  "tareas_criticas": [
    {
      "actividad": "", "ciclo": "", "subactividad": "",
      "estandar": "", "descripcion": "",
      "apreciacion_trabajador": "", "apreciacion_profesional": "",
      "conclusion_tipo": "Puede desempeñarla",
      "conclusion_descripcion": ""
    }
  ],
  "materiales": [
    {"nombre": "", "estado": "", "requerimientos": ""}
  ],
  "peligros": [
    {"nombre": "", "descripcion": "", "control": "", "recomendacion": ""}
  ],
  "recomendaciones": {
    "trabajador": "", "empresa": ""
  },
  "perfil_exigencias": {
    "vision": {"Percepción del Color": 4, ...},
    "audicion": {...}, "sensibilidad": {...},
    "olfato_gusto": {...}, "motricidad_gruesa": {...},
    "motricidad_fina": {...}, "armonia": {...},
    "cognitivos": {...}, "sociales_laborales": {...},
    "laborales": {...}
  },
  "registro": {
    "elaboro": "NOMBRE — Cargo",
    "reviso": "NOMBRE — Cargo"
  }
}
```

---

## FORMATO 2 — Carta de Medidas Preventivas
**Archivo:** `ejemplo carta de medidas.docx` | **Complejidad:** Media
**Cuándo:** Informar a la empresa medidas para un trabajador con condición de salud.
**Función:** `generar_carta_medidas(datos, output_name=None)`
**Script prueba:** `test_carta_medidas.py` (OLGA LUCIA PAREDES ORTIZ) — ver `references/test-scripts.md`

### Campos
**Encabezado:** `{{NOMBRE_EMPRESA_DESTINATARIO}}` `{{NOMBRE_CONTACTO}}` `{{CARGO_CONTACTO}}` `{{DIRECCION_EMPRESA}}` `{{TELEFONO_EMPRESA}}` `{{CORREO_EMPRESA}}` `{{CIUDAD}}` (siempre Neiva, Huila)
**Asunto:** `{{NOMBRE_TRABAJADOR}}` `{{CEDULA_TRABAJADOR}}`
**Cuerpo:** `{{ID_SINIESTRO}}` (con link) `{{FECHA_SINIESTRO}}` `{{CARGO_TRABAJADOR}}` `{{FECHA_VISITA}}` `{{PERIODO_VIGENCIA}}`
**Recomendaciones trabajador:** `{{LISTA_RECOMENDACIONES_TRABAJADOR}}` — viñetas, generadas por DeepSeek según diagnóstico
**Recomendaciones tareas:** `{{RECOMENDACIONES_TAREAS}}` — por tarea específica
**Recomendaciones empresa:** `{{LISTA_RECOMENDACIONES_EMPRESA}}`
**Cierre:** Texto fijo ARL Positiva (no modificar). Firma: SANDRA PATRICIA POLANIA OSORIO / Fisioterapeuta. Esp. Salud Ocupacional

---

## FORMATO 3 — Carta de Recomendaciones / Reincorporación Laboral
**Archivo:** `ejemplo carta de recomendaciones.docx` | **Complejidad:** Media
**Cuándo:** Cierre de rehabilitación cuando el trabajador puede reincorporarse.
**Función:** `generar_carta_recomendaciones(datos, output_name=None)`
**Script prueba:** `test_carta_recomendaciones.py` (JUAN CARLOS DURAN NARVAEZ) — ver `references/test-scripts.md`

### Estructura y campos
**Encabezado (párrafos):** Fecha, destinatario (empresa, contacto, cargo, dirección, teléfono). Reemplazados con `_reemplazar_en_parrafos`.
**Asunto:** Párrafo con `Programación de la visita...` — reemplazado con `_reemplazar_parrafo`.

**Tabla 0 — Datos del caso (12 filas × 2 cols, label-value):**
- NOMBRE AFILIADO, DOCUMENTO CC, TIPO DE SINIESTRO, FECHA DEL EVENTO, SEGMENTO LESIONADO, CARGO → `_buscar_y_reemplazar`
- CONCEPTO (texto largo) → `_reemplazar_celda_entera` (busca "Una vez realizada la Valoración de desempeño")
- TIEMPO DE VIGENCIA, INCAPACITADO (Sí/No), FECHA ULTIMA INCAPACIDAD, FORMA DE INTEGRACIÓN → `_buscar_y_reemplazar`

**Tabla 1 — Tareas + Recomendaciones (1 fila × 2 cols):**
- Celda izquierda: `recomendaciones.tareas` (lista) → `_poner_texto` con `\n\n`.join()
- Celda derecha: `recomendaciones.trabajador` (lista) → `_poner_texto` con `\n\n`.join()

**RECOMENDACIONES PARA LA EMPRESA:** Sección entre "RECOMENDACIONES PARA LA EMPRESA:" y "Una vez se cumpla el tiempo de vigencia" → `_reemplazar_seccion_parrafos` con `recomendaciones.empresa_texto` (texto con \n).

**Párrafos finales:** Texto fijo ARL Positiva (no se modifican, vienen de la plantilla).

**Firmas:** SANDRA PATRICIA POLANIA OSORIO + DANIEL ALEXANDER MEDINA VICTORIA (Médico Laboral).

---

## FORMATO 4 — Certificado de Rehabilitación Integral / Cierre de Caso
**Archivo:** `cierre_de_caso.docx` | **Páginas:** 7 | **Complejidad:** Alta
**Cuándo:** Finalizar el proceso de rehabilitación integral del afiliado.

### Campos
`{{FECHA_DIA/MES/ANO}}` `{{ULTIMO_DIA_INCAPACIDAD}}` (8 celdas) `{{PROVEEDOR_RHI}}`
**Sección 1:** Identificación (mismos campos Formato 1)
**Sección 2:** Marcar X: Reintegro sin/con modificaciones / Reubicación temporal/definitiva / Reconversión / Orientación Profesional
**Sección 3:** Marcar X si aplica: Sin compromiso / Deserción sin/con conocimiento de causa
**Sección 4:** `{{ACTIVIDADES_PROVEEDOR_FUNCIONAL}}` `{{ACTIVIDADES_PROVEEDOR_OCUPACIONAL}}`
**Sección 5:** `{{MOTIVO_CONSULTA}}` `{{ENFERMEDAD_ACTUAL}}` `{{EXAMEN_FISICO}}` `{{ANALISIS_RECOMENDACIONES}}`
**Sección 6:** `{{OBSTACULOS}}` o "Ninguno frente al caso"
**Sección 7:** `{{CONCEPTO_INTEGRAL}}` — generado por DeepSeek con resumen completo
**Sección 8:** `{{OBSERVACION}}` o "Ninguna frente al caso"
**Sección 9:** Firmas: Elaboró (doctora) / `{{NOMBRE_REVISOR}}` / Gerencia Médica (blanco)

---

## FORMATO 5 — Citación de Empresas
**Archivo:** `ejemplo formato de citacion de empresas.docx` | **Complejidad:** Baja
**Cuándo:** Notificar a la empresa de una visita programada.
**Función:** `generar_citacion_empresas(datos, output_name=None)`
**Script prueba:** `test_citacion_yesid.py` (YESID LOZANO CEDEÑO, CC 12124080)

### Estructura y campos
**Encabezado (párrafos):** Fecha "Neiva, [fecha]" → `_reemplazar_en_parrafos` con template literal "Neiva, 23 febrero 2026". Empresa, contacto, cargo, dirección también reemplazados con `_reemplazar_en_parrafos`.

**Asunto:** NO es tabla — es un párrafo suelto. Generado con `_reemplazar_parrafo` usando template: "Asunto: Programación de la visita a la empresa {empresa} con el fin de realizar: {tipo_estudio} del afiliado {nombre} identificado con CC {documento} por parte de la ARL positiva...". Buscar por "Programación de la visita a la empresa". **IMPORTANTE:** Incluir el prefijo "Asunto: " en el texto generado; `_reemplazar_parrafo` reemplaza TODO el contenido del párrafo.

**Tabla (11 filas × 2 cols):**
- CARGO, TIPO DE ESTUDIO, TIEMPO DE EJECUCIÓN, OBJETIVO DEL ESTUDIO, FECHA Y HORA → `_buscar_y_reemplazar`
- NOMBRE DEL PROFESIONAL, AUDITOR, DESCRIPCIÓN DEL ESTADO DEL CASO (substring "DESCRIPCI"), REQUISITOS → `_buscar_y_reemplazar`

**Cierre (párrafos):** Teléfono y correo del proveedor desde `datos.proveedor.telefono` y `datos.proveedor.correo`. Reemplazados con `_reemplazar_en_parrafos` buscando los valores literales de la plantilla ("3182675427", "tocupacionalrilo@gmail.com"). El fix de hyperlinks en `_reemplazar_en_parrafos` evita duplicación del email.

**Firma:** `_insertar_firma` + SANDRA PATRICIA POLANIA OSORIO / Fisioterapeuta Esp. SST / IPS RILO.

### JSON Schema para Citación
```json
{
  "paciente": {"nombre": "", "documento": ""},
  "empresa": {"nombre": "", "contacto": "", "cargo_contacto": "", "direccion": ""},
  "laboral": {"cargo": ""},
  "consulta": {"fecha": ""},
  "visita": {
    "tipo_estudio": "", "tiempo_ejecucion": "", "objetivo": "",
    "fecha_hora": "", "nombre_profesional": "", "nombre_auditor": "",
    "descripcion_estado": "", "requisitos": ""
  },
  "proveedor": {"telefono": "", "correo": ""}
}
```

---

## FORMATO 6 — Prueba de Trabajo
**Archivo:** `ejemplo prueba de trabajo.docx` | **Complejidad:** MUY ALTA (8 tablas, ~56 filas en tabla maestra)
**Cuándo:** Evaluar si el trabajador puede ejecutar sus tareas reales (observación directa).
**Función:** `generar_prueba_trabajo(datos, output_name=None)`
**Script prueba:** `test_prueba_laura.py` (LAURA MARIA CARDONA ZAPATA, CC 39684141)

### Arquitectura del documento
1. **Tabla 0 (maestra, 56+ filas × 26 cols):** Contiene TODAS las secciones del documento en un solo grid con celdas masivamente fusionadas. Usa `_buscar_y_reemplazar` y `_poner_fecha_celdas` con labels literales de la plantilla.
2. **Tablas 1-6 (tareas críticas):** 3 tareas × 2 tablas cada una (actividad/subactividad + apreciaciones/conclusiones).
3. **Tabla 7 (materiales + peligros):** Combinada — filas 2-8 para materiales, filas 12+ para peligros.
4. **Párrafos:** Muy pocos — casi todo está dentro de Tabla 0.

### Funciones auxiliares nuevas (agregadas en esta sesión)
- `_reemplazar_tabla_tarea_critica(doc, idx, tarea)` — Llena una tarea crítica (actividad, subactividad, ciclo, estándar, descripción, apreciaciones, conclusión checkbox X + descripción). Mapea idx 0→tablas 1-2, idx 1→tablas 3-4, idx 2→tablas 5-6.
- `_reemplazar_en_tabla_por_idx(tabla, fila_idx, col_start, texto)` — Reemplaza en celda única (dedup con `cell._tc`) por índice de fila y columna lógica.
- `_marcar_opcion_en_tabla(tabla, opcion)` — Marca X en celda checkbox de tabla de conclusiones (la X va en la celda ANTERIOR a la que contiene el texto de la opción).
- `_reemplazar_tabla_materiales(doc, materiales)` — Llena 7 filas de materiales (Nombre, Estado, Requerimientos, Observaciones) en Tabla 7 filas 2-8.
- `_reemplazar_tabla_peligros(doc, peligros)` — Llena 6 filas de peligros (Nombre, Descripción, Control, Recomendaciones) en Tabla 7 filas 12+.

### Campos en Tabla 0 (Sección 1 — Identificación)
**Fechas:** `_poner_fecha_celdas` con etiquetas "FECHA DE VALORACIÓN", "ÚLTIMO DIA DE INCAPACIDAD", "Fecha de nacimiento", "Fecha ingreso cargo", "Fecha ingreso a la empresa".
**Campos label→value:** `_buscar_y_reemplazar` con labels exactos:
- Nombre del trabajador, Número de documento, Identificación del siniestro
- Teléfonos trabajadores, Dirección residencia/ciudad
- Diagnóstico(s) clínico(s) por evento ATEL, Fecha(s) del evento(s) ATEL
- EPS - IPS, AFP, Tiempo total de incapacidad
- Empresa donde labora, NIT de la Empresa, Cargo actual, Área/sección/proceso
- Forma de vinculación laboral, Contacto en empresa/cargo, Correo(s) electrónico(s)
- Teléfonos de contacto empresa, Dirección de empresa/ciudad
**Checkboxes:** `_marcar_opcion` con "Dominancia" y "Nivel educativo". `_buscar_y_reemplazar` para "Estado civil" y "63 años" (edad).

### Textos largos (buscar por primeras palabras con `_reemplazar_celda_entera`)
- **Metodología:** "La metodología utilizada para la Prueba de Trabajo" → `consulta.metodologia` ⚠️ La celda de la plantilla tiene sombreado amarillo (`<w:shd>`). `_reemplazar_celda_entera` debe limpiar el shading o el texto nuevo aparecerá con fondo amarillo. Ver Pitfall 11.
- **Proceso productivo:** "La Servidora manifiesta las siguientes funciones" → `consulta.proceso_productivo`
- **Apreciación trabajador:** "La servidora manifiesta que permanece con dolor" → `consulta.apreciacion_trabajador`
- **Estándares productividad:** "La servidora menciona que el trabajo depende" → `consulta.estandares_productividad`
- **Concepto desempeño:** "Se realizó la Prueba de Trabajo (PT)" → `consulta.concepto_desempeno`

### Requerimientos del desempeño (Sección 3.4)
Campos con `_buscar_y_reemplazar`: JORNADA, RITMO, DESCANSOS, TURNOS, HORAS EXTRAS, ROTACIONES, TIEMPOS EFECTIVOS, DISTRIBUCIÓN SEMANAL. Vienen de `laboral.*`.

**⚠️ ALERTA — Columna duplicada**: La tabla maestra tiene labels de Requerimientos del desempeño en celdas fusionadas horizontalmente (varias columnas). Si `_buscar_y_reemplazar` no distingue entre la celda de etiqueta y la de valor correctamente, escribe el valor en MÚLTIPLES celdas (la original y las del merge). Revisar que la detección de frontera label→valor funcione para este layout específico.

### Bugs conocidos en Prueba de Trabajo (sesión 2026-05-10)

Estos bugs fueron reportados por el usuario al revisar el documento generado contra la plantilla de ejemplo. Son específicos de este formato y no afectan a los otros 6:

| # | Bug | Sección | Causa raíz | Fix necesario |
|---|-----|---------|------------|---------------|
| 1 | Texto amarillo | Sección 2 (Metodología) | `_poner_texto` no limpia `<w:shd>` del `tcPr` de la celda | Agregar limpieza de shading en `_poner_texto` y `_reemplazar_celda_entera` (ver Pitfall 11) |
| 2 | Viñetas vacías | Sección 3.1 | Párrafos sobrantes de la plantilla no se eliminan | Asegurar que `_reemplazar_seccion_parrafos` elimine surplus paragraphs (ver Pitfall 10). Si la sección 3.1 no usa esta función, implementarlo. |
| 3 | Columna duplicada | Sección 3.4 (Requerimientos del desempeño) | `_buscar_y_reemplazar` escribe en label + valor por merge horizontal | Revisar detección de frontera label→valor para este layout. Considerar `_reemplazar_en_tabla_por_idx` con índices fijos si las celdas están en posiciones conocidas. |
| 4 | Espacio blanco gigante | Sección 7 (Concepto desempeño) | `_reemplazar_celda_entera` procesa celda merged N× sin `cell._tc` dedup | Agregar/verificar `cell._tc` dedup en `_reemplazar_celda_entera`. Limpiar párrafos completamente antes de escribir. (ver Pitfall 12) |

**Diagnóstico general**: La tabla maestra de Prueba de Trabajo es la más compleja de todos los formatos (56+ filas × 26 cols con fusiones masivas). Las funciones auxiliares (`_reemplazar_celda_entera`, `_buscar_y_reemplazar`, `_reemplazar_en_tabla_por_idx`) DEBEN tener `cell._tc` dedup Y limpiar propiedades de celda (shading, column span) al escribir. Sin esto, los 4 bugs son inevitables.

Ver `references/bugs-prueba-trabajo.md` para diagnóstico detallado, scripts de verificación y procedimientos de fix por bug.

### JSON Schema para Prueba de Trabajo
```json
{
  "paciente": {
    "nombre": "", "documento": "", "edad": "", "fecha_nacimiento": "",
    "dominancia": "", "estado_civil": "", "nivel_educativo": "",
    "telefono": "", "direccion": "", "eps_ips": "", "afp": ""
  },
  "empresa": {
    "nombre": "", "nit": "", "contacto": "", "cargo_contacto": "",
    "correo": "", "telefono": "", "direccion": ""
  },
  "laboral": {
    "cargo": "", "area": "", "fecha_ingreso_cargo": "", "antiguedad_cargo": "",
    "fecha_ingreso_empresa": "", "antiguedad_empresa": "", "vinculacion": "",
    "jornada": "", "ritmo": "", "descansos": "", "turnos": "",
    "horas_extras": "", "rotaciones": "", "tiempos_efectivos": "", "distribucion_semanal": ""
  },
  "siniestro": {
    "id_siniestro": "", "fecha_evento": "", "diagnosticos": "",
    "tiempo_incapacidad": "", "ultimo_dia_incapacidad": ""
  },
  "consulta": {
    "fecha": "DD/MM/AAAA", "metodologia": "", "proceso_productivo": "",
    "apreciacion_trabajador": "", "estandares_productividad": "",
    "concepto_desempeno": ""
  },
  "tareas_criticas": [
    {
      "actividad": "", "ciclo": "", "subactividad": "", "estandar": "",
      "descripcion": "", "apreciacion_trabajador": "",
      "apreciacion_profesional": "", "conclusion_tipo": "Puede desempeñarla",
      "conclusion_descripcion": ""
    }
  ],
  "materiales": [
    {"nombre": "", "estado": "", "requerimientos": "", "observaciones": ""}
  ],
  "peligros": [
    {"nombre": "", "descripcion": "", "control": "", "recomendaciones": ""}
  ]
}
```

---

## FORMATO 7 — Valoración del Desempeño Ocupacional Final (VOI)
**Archivo:** `ejemplo valoracion de desempeño ocupacional.docx` | **Complejidad:** MUY ALTA (5 tablas, ~190 filas)
**Abreviación:** Sandra la llama "VOI" (Valoración de Ocupacional Integral) o "VOI" a secas.
**Cuándo:** Valoración final antes del cierre o reintegro.
**Función:** `generar_valoracion_desempeno(datos, output_name=None)`
**Script prueba:** `test_valoracion_juan.py` (JUAN CARLOS DURAN NARVAEZ, CC 1193143688)

**⚠️ Referencia de bugs:** `references/bugs-valoracion-desempeno.md` — 10 errores detectados por Sandra en revisión 2026-05-15 con diagnóstico detallado y fixes. Cargar este archivo antes de modificar el generador de Formato 7.

### Estructura del template
- **Tabla 0 (38 filas × 35 cols):** Sección 1-2 (Objetivo + Identificación completa). Fecha en celdas individuales (día/mes/año), campos label→value con `_buscar_y_reemplazar`, checkboxes con `_marcar_opcion`. Celdas MASIVAMENTE fusionadas horizontalmente (gridSpan hasta 35).
- **Tabla 1 (24 filas × 14 cols):** Sección 3-6 (Historia ocupacional 2 entradas, Descripción laboral, Rol laboral, Tratamiento ATEL). Campos multilínea con `_reemplazar_celda_entera`.
- **Tabla 2 (39 filas × 12 cols):** Adaptaciones + Sección 7 (Composición familiar) + Sección 8 parcial (Cuidado personal, Comunicación). Checkboxes de nivel de dificultad.
- **Tabla 3 (40 filas × 7 cols):** Sección 8 cont. (Movilidad, Aprendizaje, Vida doméstica) + Sección 9 (Concepto ocupacional).
- **Tabla 4 (8 filas × 3 cols):** Concepto cont. + Sección 10 (Orientación) + Sección 11 (Registro/Firmas).

### Pitfalls específicos
- **Checkboxes en tablas con distinto número de columnas:** `_marcar_nivel_dificultad` (función interna) detecta num_cols para mapear correctamente las columnas de nivel (Tabla 2 usa columnas dobles 2-3/4-5/..., Tabla 3 usa columnas simples 1/2/3/...).
- **Último bloque en _marcar_opcion:** Para el último bloque de checkboxes, limitar a celdas que compartan el mismo `_tc` que la primera celda checkbox (máx 4 celdas). Evita invadir celdas fusionadas masivas (bug: Vinculación laboral escribía X en 27 celdas).
- **Workaround Eventos No laborales:** La celda tc[9] (Diagnostico, gridSpan=13, cols 22-34) puede contener X residuales. Limpiar manualmente después de `_marcar_opcion`.

### Bugs corregidos 2026-05-15 — 10 errores detectados por Sandra

Estos bugs fueron reportados al revisar el documento generado (msg 48 Telegram) contra la plantilla original. Todos corregidos en sesión 2026-05-15:

| # | Bug | Sección | Causa raíz | Fix |
|---|-----|---------|------------|-----|
| 1 | ID Siniestro pegado "5034638705034638870" | Pág 1 Identificación | Hyperlinks fantasma en celda de valor (pitfall 14) | `_poner_texto` ahora llama `_eliminar_hyperlinks` en cada párrafo |
| 2 | X de "Bachillerato: vocacional 9°" en columna incorrecta | Pág 1 Nivel educativo | `_marcar_opcion` retornaba True sin marcar (pitfall 13) | Eliminado `return True` prematuro; sigue buscando en otras filas |
| 3 | Diagnóstico en mayúsculas + negrita + letra grande | Pág 1 Diagnóstico | `_buscar_y_reemplazar` heredaba formato del template | Usar `_reemplazar_celda_entera(doc, "HERIDA DEL CUARTO DEDO", ..., bold=False, font_size=7.5)` |
| 4 | "Sin datos \| Sin datos" duplicado | Pág 1 Tiempo incapacidad | `_buscar_y_reemplazar` pisa "0" sin limpiar "Sin datos" original | Si `tiempo_incapacidad == "Sin datos"`, NO reemplazar — conservar "0 \| Sin datos" del template |
| 5 | X no marcada en Ocurrencia ATEL + PUESTO DE TRABAJO | Pág 2 Sección 5 | Estructura de checkbox no compatible con algoritmo de bloques (checkbox pegado al label sin opción intermedia) | Manejo directo de celdas: `_poner_texto(celdas[1], "X")` para ocurrencia, `celdas[4]` para PUESTO DE TRABAJO |
| 6 | Columna extra con texto repetido en letra pequeña | Pág 2 Sección 6 | `_reemplazar_celda_entera` encontraba "Tratamiento recibido" en la celda LABEL [0], no en la celda VALOR [2] | Buscar por texto clínico: `"ENFERMEDAD ACTUAL"` (contenido del valor, no del label) |
| 7 | "Página 3 de 7" vs "3 de 6" | Encabezados | Las duplicaciones de texto (fix 1,4,6) expandían el documento | Se corrige solo con los demás fixes |
| 8 | Concepto en 2 bloques separados con línea en blanco | Pág 6 Sección 9 | `concepto.split("\n\n", 1)` dividía en 2 partes y las escribía en celdas distintas | Escribir TODO el concepto como un solo bloque: `_reemplazar_celda_entera(doc, "Afiliado de", concepto, bold=False, font_size=7.5)` |
| 9a | Nombre "SANDRA PATRICIA POLANIA" sin "OSORIO" | Pág 7 Registro col izq | `_buscar_y_reemplazar` solo tocaba la primera ocurrencia; columna derecha decía "Nombre y Apellido" | `_reemplazar_en_tablas` para reemplazar TODAS las ocurrencias de "SANDRA PATRICIA POLANIA OSORIO" Y "Nombre y Apellido" |
| 9b | "REHABILITACION INTEGRAL..." en color azul | Pág 7 Registro | Hyperlink del template no se eliminaba (pitfall 14) | `_poner_texto` ahora limpia hyperlinks → texto negro |
| 10 | Columna izquierda estrecha parte el texto | Sección 6 | Consecuencia del bug 6 (label cell reemplazada con texto clínico, value cell con texto viejo) | Se corrige con fix 6 |

**Lecciones aprendidas**:
- **NUNCA usar el texto del LABEL como búsqueda para `_reemplazar_celda_entera`**. La celda que contiene el label NO es la celda de valor. Buscar por un substring del CONTENIDO clínico (ej: "ENFERMEDAD ACTUAL", "HERIDA DEL CUARTO DEDO").
- **`_marcar_opcion` no funciona cuando el checkbox está pegado al label** sin texto de opción intermedio. En esos casos, manipular celdas directamente por índice.
- **Tabla 0 de Valoración tiene celdas fusionadas horizontalmente en TODAS las columnas** (label en [0], valor en [1..34] como UN solo merged cell). Esto es diferente de otros formatos donde label y valor son celdas separadas. `_buscar_y_reemplazar` funciona pero `_reemplazar_celda_entera` puede sobreescribir el label si no se elige bien el texto de búsqueda.

### Campos adicionales
**Modalidad:** `{{MODALIDAD}}` (marcar X) `{{TIEMPO_MODALIDAD}}`
**Sección 3 — Historia Ocupacional:** `{{EMPRESA_ANTERIOR_N}}` `{{CARGO_ANTERIOR_N}}` `{{DURACION_N}}` `{{MOTIVO_RETIRO_N}}` `{{OTROS_OFICIOS}}` `{{OFICIOS_INTERES}}`
**Sección 4:** `{{NOMBRE_CARGO}}` `{{DESCRIPCION_TAREAS}}` `{{HERRAMIENTAS_TRABAJO}}` `{{HORARIO_TRABAJO}}` `{{EPP}}` `{{ANTIGUEDAD_CARGO}}` `{{REQUERIMIENTOS_MOTRICES}}`
**Sección 5 — Rol laboral:** `{{TAREAS_OPERACIONES}}` `{{COMPONENTES_DESEMPENO}}` `{{TIEMPO_EJECUCION}}` `{{FORMA_INTEGRACION}}`
**Sección 6 — Evento ATEL:** `{{TRATAMIENTO_RECIBIDO}}` — resumen cronológico valoraciones
**Adaptaciones:** Marcar X: Bastón/Muletas/Caminador/Prótesis/Audífono/Gafas/Bastón guía/Otros
**PCL:** `{{PCL_SI_NO}}` `{{PCL_PORCENTAJE}}`

---

## Schema JSON clínico completo
```json
{
  "paciente": {
    "nombre": "", "documento": "", "fecha_nacimiento": "", "edad": 0,
    "telefono": "", "direccion": "", "ciudad": "", "estado_civil": "",
    "nivel_educativo": "", "dominancia": "", "eps_ips": "", "afp": ""
  },
  "empresa": {
    "nombre": "", "nit": "", "direccion": "", "telefono": "", "correo": "",
    "contacto": "", "cargo_contacto": "", "ciudad": "Neiva"
  },
  "laboral": {
    "cargo": "", "area": "", "cno_cargo": "",
    "fecha_ingreso_cargo": "", "fecha_ingreso_empresa": "",
    "antiguedad_cargo": "", "antiguedad_empresa": "",
    "vinculacion": "", "modalidad": "", "tiempo_modalidad": "",
    "jornada": "", "ritmo": "", "descansos": "", "turnos": "",
    "tiempo_efectivo": "", "rotaciones": "", "horas_extras": "", "distribucion_semanal": "",
    "herramientas": "", "epp": "", "requerimientos_motrices": ""
  },
  "siniestro": {
    "id_siniestro": "", "tipo": "", "fecha_evento": "",
    "segmento_lesionado": "", "diagnosticos": "", "codigos_cie10": [],
    "tiempo_incapacidad": 0, "ultimo_dia_incapacidad": "",
    "incapacitado": false, "fecha_ultima_incapacidad": "",
    "pcl_aplica": false, "pcl_porcentaje": 0
  },
  "consulta": {
    "fecha": "", "tipo": "", "numero_sesion": 0,
    "motivo_consulta": "", "enfermedad_actual": "",
    "examen_fisico": "", "diagnostico_definitivo": "",
    "tratamiento_recibido": "", "plan_tratamiento": []
  },
  "visita": {
    "fecha": "", "tipo_estudio": "", "tiempo_ejecucion": "",
    "objetivo": "", "nombre_auditor": "", "nombre_profesional": "Sandra Patricia Polania Osorio"
  },
  "rehabilitacion": {
    "programa_rhi": [], "actividades_funcional": [], "actividades_ocupacional": [],
    "logros": "", "obstaculos": "", "forma_integracion": "",
    "tiempo_vigencia": "", "periodo_vigencia": "",
    "concepto_integral": "", "observaciones": ""
  },
  "tareas": [
    {
      "nombre": "", "ciclo": "", "subactividad": "", "descripcion_biomecanica": "",
      "estandar_productividad": "", "apreciacion_trabajador": "",
      "apreciacion_profesional": "", "conclusion": "", "descripcion_conclusion": "",
      "foto": ""
    }
  ],
  "materiales_equipos": [{"nombre": "", "estado": "", "requerimientos": ""}],
  "peligros": [{"tipo": "", "descripcion": "", "control_existente": "", "recomendacion": ""}],
  "recomendaciones": {
    "trabajador": [], "empresa": [], "por_tarea": {}
  },
  "historia_ocupacional": [
    {"empresa": "", "cargo": "", "duracion": "", "motivo_retiro": ""}
  ],
  "otros_oficios": "", "oficios_interes": "",
  "perfil_exigencias": {}
}
```

## Orden de generación por tipo de caso
- **Caso nuevo:** Citación → Análisis/Prueba → Carta Medidas/Recomendaciones
- **Seguimiento:** Valoración Desempeño → Carta Recomendaciones
- **Cierre:** Valoración Desempeño Final → Cierre de Caso → Carta Recomendaciones

## Tomy Completo (Mayo 2026) — Integración con el pipeline

### Paso 6 del workflow: `workflow_steps/generar_formatos.py`
Este skill es llamado por el wrapper `backend/workflow_steps/generar_formatos.py` (Paso 6 del pipeline de 9 pasos). El wrapper:
1. Recibe el JSON maestro sintetizado del Paso 5
2. Selecciona formatos aplicables según estado del caso (via `format_selector.py`)
3. Llama a `doc_generator.generar_*()` para cada formato
4. Guarda DOCX en `storage/docs/`
5. Pasa los paths al siguiente paso (qa_formatos)

### Organizador de formatos crudos: `backend/organizador_formato.py`
Caso alterno: Sandra tiene un DOCX antiguo con info incompleta/desordenada.
- **Endpoint**: `POST /api/organizar-formato` — recibe DOCX + CC
- **Lógica**: Lee DOCX, detecta campos vacíos vs llenos vs contradictorios, cruza con datos verificados de portales, reescribe limpio
- **Acceso chat**: Comando "organiza este formato {nombre}" → detecta intención y delega al endpoint
- **Modelo**: `deepseek-v4-pro` (requiere razonamiento para reorganizar contexto)

## Nomenclatura de archivos
`[tipo]-[documento-paciente]-[fecha].docx` / `.pdf`
Ejemplo: `analisis-123456789-2026-05-09.docx`
