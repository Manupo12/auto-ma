# Debugging: merged cells y duplicación de texto

## Síntoma
Documento generado con texto repetido decenas de veces. Un documento de 3 páginas
se vuelve de 47 páginas. El mismo párrafo aparece 40+ veces en una misma sección.

## Causa raíz
python-docx itera celdas fusionadas (merged cells) una vez por cada fila que abarcan.
Si una celda está fusionada verticalmente y ocupa 40 filas, `for row in table.rows:
for cell in row.cells:` la devuelve 40 veces. Cada llamada a `_poner_texto` escribe
en la misma celda física 40 veces.

## Fix universal
Deduplicar con `cell._tc` (el elemento XML único de la celda):

```python
# MAL — escribe N veces si hay merge
for row in tabla.rows:
    for cell in row.cells:
        _poner_texto(cell, valor)

# BIEN — procesa cada celda física una sola vez
procesadas = set()
for row in tabla.rows:
    for cell in row.cells:
        if cell._tc in procesadas:
            continue
        procesadas.add(cell._tc)
        _poner_texto(cell, valor)
```

## Funciones que REQUIEREN este fix
Toda función que itere `table.rows → row.cells`:

1. **`_reemplazar_en_tablas`** — La principal causante. Sin fix, reemplaza texto en la
   misma celda N veces, acumulando contenido.
2. **`_buscar_y_reemplazar`** — Aunque retorna tras el primer match, si la etiqueta
   aparece en una celda fusionada que abarca múltiples filas, puede procesarse más de
   una vez en llamadas sucesivas.
3. **`_marcar_opcion`** — Busca etiquetas en filas. Si la etiqueta está en celdas
   fusionadas verticalmente, la función se ejecuta para cada fila del merge.
4. **`_insertar_firma`** — Mismo patrón de iteración.

## Función `_reemplazar_celda_entera` vs `_reemplazar_en_tablas`

| Función | Cuándo usar | Cuándo NO usar |
|---------|-------------|----------------|
| `_reemplazar_en_tablas` | Reemplazar strings cortos en celdas simples (ej: cambiar "RILO SAS" por el nombre del proveedor) | Celdas con texto multilínea donde el nuevo texto es muy diferente del original |
| `_reemplazar_celda_entera` | Celdas con bloques de texto completo (Sección 4 actividades, Sección 5 motivo consulta, Sección 7 concepto integral) | Cambios puntuales de una palabra o número |

**Regla**: Si el nuevo texto es estructuralmente diferente del original (más líneas,
diferente formato), usar `_reemplazar_celda_entera`. Si es un reemplazo 1:1 simple,
`_reemplazar_en_tablas` es suficiente.

## Verificación post-generación
```python
from docx import Document
doc = Document("documento_generado.docx")

# Verificar que no hay texto duplicado dentro de celdas
for t in doc.tables:
    for r in t.rows:
        for c in r.cells:
            txt = c.text
            for keyword in ["Medicina laboral", "MOTIVO DE CONSULTA", "Proveedor Funcional"]:
                count = txt.count(keyword)
                if count > 1:
                    print(f"⚠️  '{keyword}' repetido {count}x en una celda")

# Verificar estructura
t0 = doc.tables[0]
print(f"Filas: {len(t0.rows)}, Columnas: {len(t0.columns)}")
```
