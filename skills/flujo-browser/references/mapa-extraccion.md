# Mapa de extracción → Campos del JSON

## Flujo completo de extracción (orden correcto)

```
PASO 1: MEDIFOLIOS → Agenda Citas → Obtener siniestro
  1. Login Medifolios
  2. Menú → Agenda Citas
  3. Seleccionar "SANDRA PATRICIA POLANIA"
  4. Buscar paciente por fecha en calendario
  5. Click en cita → Popup "Detalle Solicitud"
  6. Extraer de observaciones: NO. SINIESTRO<numero>
  7. Extraer datos del paciente: ID, nombre, tel, email, empresa

PASO 2: POSITIVA → Consulta integral → Buscar por cédula
  1. Login Positiva
  2. Menú → Consulta integral
  3. Ingresar número de documento (cédula)
  4. Click Buscar
  5. Extraer de DATOS ASEGURADO: datos personales
  6. Extraer de SINIESTROS: id_siniestro, fecha_evento, diagnóstico
  7. Extraer de REHABILITACIÓN INTEGRAL: código CIE10, proveedor, estado

PASO 3: POSITIVA → Consultar caso RHI → Verificar siniestro
  1. Menú → Rehabilitación → Consultar caso rhi
  2. Buscar por documento o matrícula
  3. Verificar que el siniestro coincida
```

## Campos JSON y su fuente

### paciente.*
| Campo | Fuente | Dónde |
|-------|--------|-------|
| nombre | Positiva | Consulta integral → DATOS ASEGURADO → Nombre |
| documento | Ambas | Medifolios: #txt_num_identificacion / Positiva: Número Identificación |
| fecha_nacimiento | Positiva | DATOS ASEGURADO → Fecha de Nacimiento |
| edad | Medifolios | #txt_edad_paciente |
| telefono | Medifolios | #txt_telefono |
| direccion | Positiva | DATOS ASEGURADO → Dirección de Residencia |
| email | Medifolios | #txt_email |
| ciudad | Medifolios | #txt_ciudad_residencia |
| eps_ips | Medifolios | Formulario DATOS GENERALES → EPS |
| afp | Medifolios | Formulario DATOS GENERALES → AFP |

### siniestro.*
| Campo | Fuente | Dónde |
|-------|--------|-------|
| id_siniestro | Medifolios primero, Positiva después | Medifolios: txt_observaciones (regex). Positiva: SINIESTROS → columna Siniestro |
| fecha_evento | Positiva | SINIESTROS → columna Fecha Siniestro |
| diagnosticos | Positiva | REHAB INTEGRAL → columna Diagnóstico (código CIE10 + descripción) |
| tipo | Positiva | SINIESTROS → Tipo Evento (AT) |
| tiempo_incapacidad | Positiva | (por determinar en tabs EVOLUCIONES/BITACORAS) |
| pcl_porcentaje | Positiva | SINIESTROS → % PCL |

### empresa.*
| Campo | Fuente | Dónde |
|-------|--------|-------|
| nombre | Medifolios | Popup → "EMPRESA CLIENTE" |
| nit | Positiva | (por determinar) |
| contacto | Positiva | (por determinar — posiblemente en detalle siniestro) |

### laboral.*
| Campo | Fuente | Dónde |
|-------|--------|-------|
| cargo | Positiva + Audio | Consulta integral (posiblemente en detalle) |

### rehabilitacion.*
| Campo | Fuente | Dónde |
|-------|--------|-------|
| proveedor | Positiva | REHAB INTEGRAL → Proveedor Asignado |
| estado | Positiva | REHAB INTEGRAL → Estado |
| calificacion_origen | Positiva | REHAB INTEGRAL → Calificación origen |
| fecha_ingreso | Positiva | REHAB INTEGRAL → Fecha Ingreso |

## IDs de elementos clave

### Medifolios
- Popup detalle: `.ui-dialog[title="Detalle Solicitud"]` o `div:has(> .ui-dialog-title:contains("Detalle Solicitud"))`
- Identificación: `#txt_num_identificacion`
- Nombre: `#txt_nombre_completo`
- Observaciones (siniestro): `#txt_observaciones`
- Teléfono: `#txt_telefono`
- Email: `#txt_email`
- Ciudad: `#txt_ciudad_residencia`
- Listado pacientes: `#container_listado_paciente`
- Campo búsqueda listado: `#gs_numHistoria`

### Positiva
- Tabs: `.tablist [role="tab"]` → hacer click según texto ("SINIESTROS", "REHABILITACIÓN INTEGRAL", etc.)
- Tabla siniestros: jqGrid dentro del tabpanel
- Tabla rehab integral: jqGrid dentro del tabpanel
- Campo búsqueda: `input[placeholder*="Número Identificación"]` o `input[placeholder*="Documento"]`

## Scripts a construir (futuro)
- `backend/extract_medifolios.py` — login → agenda → extraer siniestro y datos paciente
- `backend/extract_positiva.py` — login → consulta integral → extraer todas las pestañas
- `backend/merge_datos.py` — fusionar datos de ambas fuentes + valores por defecto
