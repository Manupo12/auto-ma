# Perfil de Exigencias — Sistema de scoring

El Anexo Perfil de Exigencias ocupa la **Tabla 6** del template (96 filas × 10 cols).
Contiene ~85 ítems agrupados en 10 categorías.

## Estructura de columnas

| Col | Contenido |
|-----|-----------|
| 0   | Nombre del ítem (ej: "Percepción del Color") |
| 1   | (parte del merge de col 0) |
| 2   | Score 0 |
| 3   | Score 1 |
| 4   | Score 2 |
| 5   | Score 3 |
| 6   | Score 4 |
| 7   | Observaciones |
| 8-9 | (merge del bloque de firma) |

## Categorías y sus filas

| Categoría | Key en JSON | # Ítems | Fila inicio (aprox) |
|-----------|-------------|---------|---------------------|
| VISIÓN | `vision` | 4 | F05 |
| AUDICIÓN | `audicion` | 2 | F10 |
| SENSIBILIDAD SUPERFICIAL Y PROFUNDA | `sensibilidad` | 5 | F13 |
| OLFATO / GUSTO | `olfato_gusto` | 2 | F19 |
| MOTRICIDAD GRUESA | `motricidad_gruesa` | 18 | F22 |
| MOTRICIDAD FINA | `motricidad_fina` | 4 | F41 |
| ARMONÍA | `armonia` | 4 | F46 |
| COGNITIVOS | `cognitivos` | 8 | F51 |
| (COGNITIVOS) Sociales/Laborales | `sociales_laborales` | 10 | F60 |
| LABORALES | `laborales` | 11 | F73 |

## Formato de datos JSON

Cada categoría es un dict donde la clave es el nombre exacto del ítem (case-sensitive, con tildes) y el valor es:
- `int` (0-4): solo el score, sin observación
- `tuple (int, str)`: score + texto de observación

```python
"motricidad_gruesa": {
    "Postura Bípeda": 3,
    "Postura Sedente": 4,
    "Caminar": (4, "Desplazamientos para entregar citaciones"),
    "Levantar pesos": 0,
    ...
}
```

## Algoritmo de marcado

La función `_llenar_perfil_exigencias(tabla, perfil)`:
1. Itera TODAS las filas de la Tabla 6
2. Para cada fila, lee `fila.cells[0].text.strip()` → nombre del ítem
3. Busca ese nombre en TODAS las categorías del dict `perfil`
4. Si encuentra match:
   - Limpia X existentes en columnas [2..6]
   - Marca X en `fila.cells[2 + score]`
   - Si hay observación, la escribe en `fila.cells[7]`

## Pitfalls

- **Nombres exactos**: Los nombres de ítems en el JSON deben coincidir EXACTAMENTE con los del template (tildes, mayúsculas, puntuación). Ej: "Percepción del Color" ≠ "Percepcion del color".
- **Dos secciones de COGNITIVOS**: La tabla tiene "COGNITIVOS" (atención, concentración, etc.) y luego otra sub-sección con ítems sociales/laborales. En el JSON van en keys separadas: `cognitivos` y `sociales_laborales`.
- **Columnas merged**: Las columnas 0-1, 2-6, 7-9 están fusionadas. Usar `cell._tc` dedup al iterar.
- **X previas**: Siempre limpiar TODAS las columnas de score (2-6) antes de marcar, no solo la del score anterior.
