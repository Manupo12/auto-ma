# Workaround: Fechas en celdas individuales sin machacar labels

## Problema

En formatos como Análisis de Exigencias (Formato 1), las fechas se escriben en celdas
individuales (día/mes/año). La función `_poner_fecha_celdas` busca celdas con texto
"día"/"mes"/"año" y escribe los dígitos EN esas mismas celdas. Esto machaca los labels
de la fila de encabezado (que dice "Día", "mes", "año") con los dígitos de la fecha.

**Ejemplo del problema:**
- Template fila 8 (labels): `C1='Día'`, `C2='mes'`, `C3='año'`
- Template fila 9 (datos): dígitos de la fecha
- Después de `_poner_fecha_celdas`: fila 8 C1='2' (dígito), C2='4' (dígito) — labels perdidos

## Solución: Guardar y restaurar labels

```python
if p.get("fecha_nacimiento"):
    t0 = doc.tables[0]
    # 1. Guardar textos de la fila de labels
    labels_guardados = {}
    for ci in range(len(t0.rows[8].cells)):
        txt = t0.rows[8].cells[ci].text.strip()
        if txt and len(txt) < 20:
            labels_guardados[ci] = txt
    
    # 2. Escribir fecha (sobrescribe labels)
    _poner_fecha_celdas(doc, "Fecha de nacimiento/edad", p["fecha_nacimiento"])
    
    # 3. Restaurar labels
    for ci, txt in labels_guardados.items():
        if ci < len(t0.rows[8].cells):
            _poner_texto(t0.rows[8].cells[ci], txt)
```

## Posiciones de filas en Formato 1

| Campo | Fila labels | Fila datos | Etiqueta búsqueda |
|-------|------------|------------|-------------------|
| Fecha nacimiento | 8 | 9 | "Fecha de nacimiento/edad" |
| Fecha ingreso cargo | 27 | 28 | "Fecha ingreso cargo" |
| Fecha ingreso empresa | 29 | 30 | "Fecha ingreso a la empresa" |

## Alternativa más robusta (si la plantilla lo permite)

Si se conoce la posición exacta de las celdas de dígitos en la fila de datos,
usar acceso directo:

```python
# Escribir dígitos secuencialmente en fila de datos
dia, mes, ano = fecha_str.split("/")
digitos = list(dia.zfill(2)) + list(mes.zfill(2)) + list(ano.zfill(4))
fila_datos = doc.tables[0].rows[9]
for i, d in enumerate(digitos):
    _poner_texto(fila_datos.cells[1 + i], d)
```

⚠️ Este método asume que los dígitos empiezan en C1 y son contiguos (8 celdas),
lo cual es cierto para el Formato 1 pero puede variar en otros formatos.

## Lección aprendida

`_poner_fecha_celdas` es una función genérica que funciona para formatos donde
las celdas "día"/"mes"/"año" SON las celdas de datos. En formatos donde estas
celdas son LABELS (y los datos van en otra fila), se requiere el workaround
de guardar/restaurar o acceso directo a la fila de datos.
