# Flujo pre-generación (v2)

Antes de llamar a `doc_generator.py`, el flujo v2 exige dos pasos:

## 1. Validar JSON — `backend/json_validator.py`

```python
from backend.json_validator import validar_json, validar_para_formatos, reporte_legible

# Para un formato
ok, errores, warnings, json_corregido, stats = validar_json(datos, "analisis_exigencias")
if not ok:
    print(f"BLOQUEADO: {errores}")
    # No generar — faltan campos required
else:
    # json_corregido ya tiene defaults y [VERIFICAR] aplicados
    generar_documento("analisis_exigencias", json_corregido)

# Para múltiples formatos
resultados = validar_para_formatos(datos, ["analisis_exigencias", "carta_medidas"])
print(reporte_legible(resultados))
```

**Jerarquía de campos:**
- `required` — falta = ERROR, bloquea generación
- `recommended` — falta = WARNING, auto-completa con `[VERIFICAR]`
- `optional` — falta = ignora
- `defaults` — auto-rellena (fecha actual, "Neiva", nombres fijos)

## 2. Seleccionar formatos — `backend/format_selector.py`

```python
from backend.format_selector import seleccionar_con_contexto

ctx = seleccionar_con_contexto(datos)
# → {estado_detectado: 'NUEVO', formatos: ['citacion_empresas', ...]}

# O forzar estado
ctx = seleccionar_con_contexto(datos, estado="SEGUIMIENTO")
```

**Estados y formatos:**
| Estado | Formatos |
|--------|----------|
| NUEVO | 5→1→2 |
| SEGUIMIENTO | 7→2→3 |
| CIERRE | 7→4→3 |
| PRUEBA_TRABAJO | 6 + formato según estado base |

## 3. Orquestador — `backend/orquestador.py`

```bash
python backend/orquestador.py --datos storage/data/paciente.json --generar
python backend/orquestador.py --datos storage/data/paciente.json --estado CIERRE --generar
python backend/orquestador.py --datos storage/data/paciente.json --forzar "cierre_caso" --generar
```

## Loop de corrección post-rechazo

Si Sandra rechaza un documento por Telegram:
1. `backend/correction_loop.analizar_mensaje_rechazo(mensaje)` → detecta tipo y campo
2. Corrige (JSON, template, o re-extrae del portal)
3. Regenera con `doc_generator`
4. Reenvía a Telegram
