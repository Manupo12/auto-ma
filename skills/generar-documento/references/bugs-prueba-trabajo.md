# Bugs conocidos — Prueba de Trabajo (Formato 6)

Sesión: 2026-05-10. Paciente: LAURA MARIA CARDONA ZAPATA (CC 39684141).
Archivo generado: `prueba-39684141-2026-02-10.docx` (~551 KB).

## Bug 1 — Texto amarillo en Metodología (Sección 2)

**Síntoma**: El texto de Metodología aparece con fondo amarillo, idéntico al highlight de la plantilla.

**Causa**: La celda de Metodología en la plantilla `ejemplo prueba de trabajo.docx` tiene `<w:shd>` (shading) en `<w:tcPr>`. `_reemplazar_celda_entera()` llama a `_poner_texto()`, que limpia los párrafos/runs de la celda pero NO toca `tcPr`. El sombreado sobrevive y se aplica al nuevo texto.

**Fix en `_poner_texto()`** (CORREGIDO 2026-05-15):
```python
# Al inicio de _poner_texto(), después de limpiar párrafos:
tcPr = celda._tc.find(f'{{{NS_W}}}tcPr')
if tcPr is not None:
    shd = tcPr.find(f'{{{NS_W}}}shd')
    if shd is not None:
        fill = shd.get(f'{{{NS_W}}}fill', '')
        # Solo eliminar sombreado AMARILLO (FFFF00).
        # NUNCA eliminar otros colores decorativos como FCE9D9 (durazno).
        if fill == 'FFFF00':
            tcPr.remove(shd)
```
**⚠️ Importante**: Antes se eliminaba TODO el sombreado, lo que borraba colores decorativos legítimos de la plantilla (ej: durazno FCE9D9 en celdas de fecha). Ahora solo se elimina el amarillo.

**Verificación**: Abrir el DOCX generado, ir a Sección 2 (Metodología). El texto debe aparecer sin fondo de color.

---

## Bug 2 — Viñetas vacías en Sección 3.1

**Síntoma**: La sección 3.1 (Proceso productivo) muestra bullets (•) sin texto al final de la lista.

**Causa**: Mismo patrón que el Pitfall 10 (Carta de Medidas). La plantilla tiene M párrafos con estilo "List Paragraph" en esta sección, pero solo se escriben N < M líneas desde el JSON. Los párrafos sobrantes quedan como bullets vacíos.

**Fix**: 
1. Si la sección 3.1 usa `_reemplazar_seccion_parrafos`, verificar que la función elimine párrafos sobrantes (ya debería tenerlo del fix v3).
2. Si la sección 3.1 se escribe de otra forma (ej: directo a celdas de tabla), implementar eliminación de párrafos sobrantes.

**Verificación**: Contar bullets en la sección 3.1 del DOCX generado. Deben coincidir exactamente con el número de líneas en `consulta.proceso_productivo`.

---

## Bug 3 — Columna duplicada en Sección 3.4

**Síntoma**: Los valores de Requerimientos del desempeño (JORNADA, RITMO, DESCANSOS, etc.) aparecen duplicados — una vez en la celda correcta y otra en una celda adyacente.

**Causa**: Las etiquetas (JORNADA, RITMO, etc.) están en celdas fusionadas horizontalmente en la tabla maestra. `_buscar_y_reemplazar()` detecta la etiqueta y escribe en la "celda de valor" adyacente, pero el merge horizontal hace que la celda de valor y alguna celda vecina compartan referencia o que el algoritmo de frontera label→valor falle.

**Fix posibles**:
A) Usar `_reemplazar_en_tabla_por_idx(tabla, fila, col, valor)` con índices fijos si las posiciones son conocidas.
B) Mejorar `_buscar_y_reemplazar` para que detecte correctamente la frontera label→valor en merges horizontales.

**Diagnóstico**: Ejecutar este script para ver el layout real:
```python
from docx import Document
doc = Document("prueba-39684141-2026-02-10.docx")
t0 = doc.tables[0]
for i, row in enumerate(t0.rows):
    textos = [c.text[:30] for c in row.cells]
    if any("JORNADA" in t or "RITMO" in t or "DESCANSOS" in t for t in textos):
        print(f"Fila {i}: {textos}")
```

---

## Bug 4 — Espacio en blanco gigante en Sección 7

**Síntoma**: La Sección 7 (Concepto de desempeño) tiene un espacio en blanco enorme, como si la celda se hubiera expandido desproporcionadamente.

**Causa más probable**: La celda "Concepto de desempeño" está fusionada verticalmente (abarca 20+ filas). `_reemplazar_celda_entera()` procesa la celda una vez por cada fila del merge porque NO tiene `cell._tc` dedup. Cada iteración agrega runs al mismo párrafo → la celda crece N×.

**Fix**: Agregar `cell._tc` dedup en `_reemplazar_celda_entera()`:
```python
def _reemplazar_celda_entera(doc, texto_busqueda, texto_nuevo, bold=None):
    procesadas = set()
    for tabla in doc.tables:
        for row in tabla.rows:
            for cell in row.cells:
                if cell._tc in procesadas:
                    continue
                procesadas.add(cell._tc)
                if texto_busqueda in cell.text:
                    _poner_texto(cell, texto_nuevo, bold=bold)
                    return True
    return False
```

**Causa alternativa**: Si ya tiene dedup, el problema puede ser que `_poner_texto()` no limpia correctamente. Verificar que `celda.paragraphs[0].clear()` se ejecute ANTES de `add_run()`.

**Verificación**: Abrir el DOCX, comparar altura de Sección 7 vs la plantilla original. Si el texto del concepto es similar en longitud al original pero la sección es mucho más alta, es merge vertical mal manejado.

---

## Procedimiento de prueba

```bash
cd /root/fisioterapia

# 1. Generar el documento
python3 test_prueba_laura.py

# 2. Verificar estructura
python3 -c "
from docx import Document
doc = Document('storage/docs/prueba-39684141-2026-02-10.docx')

# Bug 1: Revisar shading en celda de Metodología
for t in doc.tables:
    for r in t.rows:
        for c in r.cells:
            if 'metodología' in c.text.lower()[:50]:
                tcPr = c._tc.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tcPr')
                if tcPr is not None:
                    shd = tcPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}shd')
                    if shd is not None:
                        print(f'⚠️  Bug 1: Celda Metodología tiene shading: {shd.attrib}')
                    else:
                        print('✅ Bug 1: Sin shading en Metodología')

# Bug 4: Contar filas de merge en Sección 7
t0 = doc.tables[0]
concepto_filas = 0
for r in t0.rows:
    for c in r.cells:
        if 'Se realizó la Prueba de Trabajo' in c.text[:60]:
            concepto_filas += 1
if concepto_filas > 1:
    print(f'⚠️  Bug 4: Concepto aparece en {concepto_filas} filas (merge vertical sin dedup)')
else:
    print('✅ Bug 4: Concepto en 1 sola fila')
"
```
