# Scripts de prueba por formato

Cada formato tiene un script de prueba con datos de un paciente real.
Ejecutar desde `/root/fisioterapia/`.

## Formato 1 — Análisis de Exigencias
- **Script**: `test_analisis_laura.py`
- **Paciente**: LAURA ROJAS ZUÑIGA (CC 36184789)
- **Fecha**: 12/12/2024
- **Función**: `generar_analisis_exigencia(datos)`
- **Secciones**: 1-10 + Anexo Perfil de Exigencias (85 ítems)
- **Verificación**: `python3 scripts/verificar.py storage/docs/analisis-*.docx templates/formatos/ejemplo\ analisis\ de\ exigencia.docx`

## Formato 2 — Carta de Medidas
- **Script**: `test_carta_medidas.py`
- **Paciente**: OLGA LUCIA PAREDES ORTIZ
- **Función**: `generar_carta_medidas(datos)`

## Formato 3 — Carta de Recomendaciones
- **Script**: `test_carta_recomendaciones.py`
- **Paciente**: JUAN CARLOS DURAN NARVAEZ (CC 1193143688)
- **Función**: `generar_carta_recomendaciones(datos)`

## Formato 4 — Cierre de Caso
- **Script**: `test_cierre_juan.py`
- **Paciente**: JUAN CARLOS DURAN NARVAEZ (CC 1193143688)
- **Función**: `generar_cierre_caso(datos)`

## Formato 5 — Citación de Empresas
- **Script**: `test_citacion_yesid.py`
- **Paciente**: YESID LOZANO CEDEÑO (CC 12124080)
- **Función**: `generar_citacion_empresas(datos)`

## Formato 6 — Prueba de Trabajo
- **Script**: `test_prueba_laura.py`
- **Paciente**: LAURA MARIA CARDONA ZAPATA (CC 39684141)
- **Función**: `generar_prueba_trabajo(datos)`

## Formato 7 — Valoración del Desempeño
- **Script**: `test_valoracion_juan.py`
- **Paciente**: JUAN CARLOS DURAN NARVAEZ (CC 1193143688)
- **Función**: `generar_valoracion_desempeno(datos)`
