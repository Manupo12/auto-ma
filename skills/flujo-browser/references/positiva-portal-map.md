# ARL Positiva — Mapa completo del portal

**URL login:** `https://positivacuida.positiva.gov.co/cas/login?service=https://positivacuida.positiva.gov.co/web/j_spring_cas_security_check`
**Usuario:** Maria Greidy Rodriguez Ramirez — PROVEEDOR RHI
**Sesión:** Expira en ~10-15 min de inactividad. No muestra warning, simplemente snapshot vacío al intentar actuar.

## Dashboard post-login
- "Bienvenido" + menú lateral izquierdo con 7 secciones principales
- Barra inferior: Versión 1.0.3-SNAPSHOT, fecha/hora

## Menú lateral — secciones

### Traslados
(no explorado — no relevante para formatos RHI)

### Consulta autorizaciones
(no explorado)

### Servicios de salud
(no explorado)

### Rehabilitación (SUBMENÚ)
Al hacer click en "Rehabilitación" se despliega submenú con 4 opciones:
- **Consultar caso RHI** ← PRINCIPAL
- Cargue agenda proveedor
- Bandeja de entrada
- Reporte transacciones RHI

### Reporte transacciones
Link directo en el menú

### Consulta integral ← LA MÁS RICA EN DATOS
Link directo. Buscador con: Tipo Identificación + Número Identificación + Número Solicitud + checkbox "Todas Las Solicitudes"

### Programa extra
(no explorado)

---

## SECCIÓN: Consulta integral

### Búsqueda
- **Tipo de Identificación**: combobox (Cédula de ciudadanía por defecto)
- **Número Identificación**: textbox — ingresar cédula
- **Número Solicitud**: textbox — búsqueda alternativa por número de caso
- **Checkbox "Todas Las Solicitudes"** + botones Buscar/Limpiar

### Resultados — 6 pestañas
Cuando se busca un afiliado, aparecen 6 pestañas con TODA su información:

#### 1. DATOS ASEGURADO
Datos personales completos:
- Tipo Identificación, Número, Nombre completo
- Fecha de Nacimiento (formato DD-MM-YYYY)
- Departamento, Ciudad/Municipio, Zona, Localidad, Barrio
- Dirección de Residencia
- Correo Electrónico
- Teléfono Fijo Particular, Teléfono Fijo Laboral
- Celular Particular, Celular Laboral
- Sección Tutelas (tabla con solicitudes)

#### 2. SINIESTROS ⭐
Tabla con TODOS los siniestros del afiliado. Columnas:
| Columna | Ejemplo (Juan Carlos Duran) | Campo JSON |
|---------|----------------------------|------------|
| Documento Asegurado | 1193143688 | paciente.documento |
| **Siniestro** | **503463870** | **siniestro.id_siniestro** |
| **Fecha Siniestro** | **02/03/2026** | **siniestro.fecha_evento** |
| Tipo Evento | AT | siniestro.tipo |
| Indicador Tipo Accidente | Propios del Trabajo | — |
| Tipo de accidente | (vacío) | — |
| % PCL | Sin determinar | siniestro.pcl_porcentaje |
| Estado Calificación Origen | CALIFICADO | — |
| Diagnóstico | Consultar (link) / Severo (link) | siniestro.diagnosticos |
| Clasificación de Gravedad | — | — |
| Acciones | botón  | — |

**Cada fila de siniestro tiene:**
- Link en el número de siniestro (click para detalle)
- Link "Consultar" en diagnóstico (abre detalle de calificación)
- Link con clasificación (Severo, Alta Inmediata)
- Botón de acciones ( ui-button)

**CASO REAL — Juan Carlos Duran (CC 1193143688):**
- Siniestro 1: 503463870 | 02/03/2026 | AT | Sin determinar %PCL | CALIFICADO | Severo
- Siniestro 2: 503476658 | 08/04/2026 | AT | 0% PCL | CALIFICADO | Alta Inmediata

#### 3. REHABILITACIÓN INTEGRAL ⭐
Tabla de ingresos a programa RHI. Columnas:
| Columna | Ejemplo | Campo JSON |
|---------|---------|------------|
| Asegurado | CC. 1193143688 JUAN CARLOS DURAN NARVAEZ | — |
| **Id Ingreso** | **48685733** | rehabilitacion.id_ingreso |
| **Fecha Ingreso** | **03/03/2026 13:03** | rehabilitacion.fecha_ingreso |
| **No. Siniestro** | **503463870** | siniestro.id_siniestro |
| Fecha de Siniestro | 02/03/2026 00:03 | — |
| **Proveedor Asignado** | **REHABILITACION INTEGRAL LABORAL Y OCUPACIONAL SAS** | proveedor.nombre |
| **Diagnóstico** | **S611 HERIDA DE DEDO(S) DE LA MANO, CON DAÑO DE LA(S) UÑA(S)** | siniestro.diagnosticos + siniestro.codigos_cie10 |
| Calificación origen | PROFESIONAL | — |
| **Estado** | **Cerrada** | rehabilitacion.estado |
| Acciones | botón  | — |

#### 4. GESTIÓN AUTORIZACIONES
(no explorado a fondo — probablemente autorizaciones de servicios)

#### 5. EVOLUCIONES
(no explorado a fondo — probablemente historial de valoraciones/consultas)

#### 6. BITACORAS
(no explorado a fondo — probablemente registro de actividades/seguimiento)

---

## SECCIÓN: Rehabilitación → Consultar caso RHI

### Búsqueda
- Tipo de Documento: combobox (Seleccionar por defecto)
- Número de Documento: textbox
- Nro. de Matricula: textbox
- Botones Buscar / Limpiar

### Resultados — Tabla MATRICULAS
Columnas:
| Columna | Descripción |
|---------|-------------|
| No Matrícula | ID de la matrícula RHI |
| Fecha Matrícula | Fecha de ingreso al programa |
| No Siniestro | Número del siniestro asociado |
| Fecha Siniestro | Fecha del evento |
| Diagnóstico | Descripción del diagnóstico |
| Calificación Origen | Tipo de calificación (PROFESIONAL, etc.) |
| Acciones | Botones de acción |

**Nota:** Sin buscar un paciente específico, la tabla muestra "No hay matriculas para mostrar."

---

## Datos extraíbles de Positiva para los 7 formatos

### Formato 1 — Análisis de Exigencias
| Dato | Fuente en Positiva | Pestaña/Tabla |
|------|-------------------|---------------|
| ID siniestro | SINIESTROS → columna "Siniestro" | Consulta integral |
| Fecha evento ATEL | SINIESTROS → columna "Fecha Siniestro" | Consulta integral |
| Diagnóstico | REHAB INTEGRAL → columna "Diagnóstico" (código CIE10 + texto) | Consulta integral |
| % PCL | SINIESTROS → columna "% PCL" | Consulta integral |
| Nombre paciente | DATOS ASEGURADO | Consulta integral |
| Documento | DATOS ASEGURADO | Consulta integral |
| Fecha nacimiento | DATOS ASEGURADO | Consulta integral |
| Dirección | DATOS ASEGURADO | Consulta integral |
| Teléfono | DATOS ASEGURADO | Consulta integral |
| Email | DATOS ASEGURADO | Consulta integral |

### Formato 4 — Cierre de Caso
| Dato | Fuente |
|------|--------|
| Estado RHI | REHAB INTEGRAL → columna "Estado" (Cerrada/Activa) |
| Fecha ingreso RHI | REHAB INTEGRAL → columna "Fecha Ingreso" |
| Proveedor RHI | REHAB INTEGRAL → columna "Proveedor Asignado" |
| Calif. origen | REHAB INTEGRAL → columna "Calificación origen" |

### Formato 7 — Valoración Desempeño
| Dato | Fuente |
|------|--------|
| TODOS los datos del asegurado | DATOS ASEGURADO |
| TODOS los siniestros | SINIESTROS |
| Ingreso RHI | REHAB INTEGRAL |

---

## Notas de sesión 2026-05-16
- Login exitoso con credenciales 1075209386MR / Rilo2026*
- Juan Carlos Duran (1193143688) encontrado — 2 siniestros, 1 ingreso RHI, estado "Cerrada"
- La sesión expira frecuentemente (~10 min) — el snapshot devuelve página vacía
- El link del número de siniestro en SINIESTROS no abrió detalle visible (posiblemente abre en nueva pestaña o modal oculto)
- Los tabs se activan con click en el link del tab (no en el tab completo)
