# Mapa de campos por portal — Referencia rápida para extracción

## MEDIFOLIOS

### Agenda de Citas → Popup "Detalle Solicitud"

| Dato JSON | Campo HTML | ID / Selector |
|-----------|-----------|---------------|
| paciente.documento | IDENTIFICACIÓN | `#txt_num_identificacion` |
| paciente.nombre | NOMBRES | `#txt_nombre_completo` |
| paciente.edad | EDAD | `#txt_edad_paciente` |
| paciente.telefono | TELEFONO | `#txt_telefono` |
| paciente.email | EMAIL | `#txt_email` |
| paciente.ciudad | CIUDAD RESIDENCIA | `#txt_ciudad_residencia` |
| siniestro.id_siniestro | OBSERVACIONES | `#txt_observaciones` → regex: `NO\.?\s*SINIESTRO\s*(\d+)` |
| siniestro.admision | OBSERVACIONES | `#txt_observaciones` → regex: `ADMISION\s*(\d+)` |
| rehabilitacion.num_autorizacion | NUM. AUTORIZACIÓN | `#txt_num_autorizacion` |
| rehabilitacion.sesiones | OBSERVACIONES | `#txt_observaciones` → regex: `(\d+)\s*SESIONES` |
| empresa.nombre | EMPRESA CLIENTE | Link con nombre de empresa |
| consulta.servicio | SERVICIO | `#slct_servicio_agenda_medico` |
| consulta.profesional | PROFESIONAL | Texto "SANDRA PATRICIA POLANIA" |
| consulta.fecha_inicio | INICIO ATENCION | `#txt_fecha_inicio_atencion` |
| consulta.fecha_solicitud | FECHA SOLICITUD | `#txt_fecha_solicitud` |
| consulta.quien_asigna | QUIEN ASIGNO | `#txt_quien_asigna` |

### Pacientes → Formulario DATOS PERSONALES

| Dato JSON | Campo HTML | ID / Selector |
|-----------|-----------|---------------|
| paciente.tipo_documento | Tipo Documento | combobox (CÉDULA CIUDADANÍA) |
| paciente.documento | Núm. Documento | `#numero_id` |
| paciente.nombre | 1er Nombre + 2do Nombre | `#nombre1`, `#nombre2` |
| paciente.apellido | 1er Apellido + 2do Apellido | `#apellido1`, `#apellido2` |
| paciente.fecha_nacimiento | Fecha Nacimiento | `#fecha_nacimiento` |
| paciente.direccion | Dirección Ppal | `#direccion` |
| paciente.telefono | Teléfono Ppal | `#telefono` |
| paciente.telefono_aux | Teléfono Aux2 | `#tel3_paciente` |
| paciente.email | Email | `#email` |
| paciente.eps_ips | EPS/ASEGURADORA | combobox en DATOS GENERALES |
| paciente.afp | AFP | combobox en DATOS GENERALES |
| paciente.arl | ARL | combobox en DATOS GENERALES |
| empresa.nombre | EMPRESA CLIENTE | combobox en DATOS GENERALES |

### Pacientes → Popup "Listado de Pacientes"

| Dato | Campo | Selector |
|------|-------|----------|
| Búsqueda por cédula | ID | `#gs_numHistoria` |
| Tipo documento | TIP. ID | `#gs_codDocumentoIdentidad` |
| Nombres | NOMBRES | `#gs_nombreCompleto` |
| Teléfono | TELEFONO | `#gs_telefono` |
| Dirección | DIRECCION | `#gs_direccion` |
| EPS | EPS | `#gs_eps\\.nomEps` |
| Tabla resultados | container_listado_paciente | `#container_listado_paciente` |

---

## ARL POSITIVA

### Consulta integral → Pestaña DATOS ASEGURADO

| Dato JSON | Campo | Ubicación |
|-----------|-------|-----------|
| paciente.tipo_documento | Tipo de Identificación | LabelText |
| paciente.documento | Número Identificación | LabelText |
| paciente.nombre | Nombre | LabelText |
| paciente.fecha_nacimiento | Fecha de Nacimiento | LabelText (formato DD-MM-YYYY) |
| paciente.departamento | Departamento | LabelText |
| paciente.ciudad | Ciudad/Municipio | LabelText |
| paciente.zona | Zona | LabelText |
| paciente.direccion | Dirección de Residencia | LabelText |
| paciente.email | Correo Electronico | LabelText |
| paciente.telefono | Teléfono Fijo Particular | LabelText |

### Consulta integral → Pestaña SINIESTROS (tabla)

| Columna | Dato JSON |
|---------|-----------|
| Documento Asegurado | paciente.documento |
| Siniestro (link) | siniestro.id_siniestro |
| Fecha Siniestro | siniestro.fecha_evento |
| Tipo Evento | siniestro.tipo (AT, EL, etc.) |
| % PCL | siniestro.pcl_porcentaje |
| Estado Calificación Origen | siniestro.estado_calificacion |
| Diagnóstico | siniestro.diagnosticos |
| Clasificación de Gravedad | siniestro.gravedad |

### Consulta integral → Pestaña REHABILITACIÓN INTEGRAL (tabla)

| Columna | Dato JSON |
|---------|-----------|
| Asegurado | paciente.documento + nombre |
| Id Ingreso | rehabilitacion.id_ingreso |
| Fecha Ingreso | rehabilitacion.fecha_ingreso |
| No. Siniestro | siniestro.id_siniestro |
| Fecha de Siniestro | siniestro.fecha_evento |
| Proveedor Asignado | rehabilitacion.proveedor |
| Diagnóstico | siniestro.diagnosticos (CIE10 + descripción) |
| Calificación origen | siniestro.calificacion_origen |
| Estado | rehabilitacion.estado |

### Rehabilitación → Consultar caso RHI (tabla MATRICULAS)

| Columna | Dato JSON |
|---------|-----------|
| No Matrícula | rehabilitacion.no_matricula |
| Fecha Matrícula | rehabilitacion.fecha_matricula |
| No Siniestro | siniestro.id_siniestro |
| Fecha Siniestro | siniestro.fecha_evento |
| Diagnóstico | siniestro.diagnosticos |
| Calificación Origen | siniestro.calificacion_origen |

---

## Datos de prueba confirmados

### Juan Carlos Duran Narvaez (CC 1193143688)
- **Existe en Positiva** ✅
- Siniestros: 503463870 (02/03/2026, Severo) + 503476658 (08/04/2026, Alta Inmediata)
- Diagnóstico CIE10: S611 HERIDA DE DEDO(S) DE LA MANO, CON DAÑO DE LA(S) UÑA(S)
- Id Ingreso RHI: 48685733
- Proveedor: REHABILITACION INTEGRAL LABORAL Y OCUPACIONAL SAS
- Estado: Cerrada
- **NO encontrado en Medifolios** (posiblemente no registrado o fuera del alcance de Sandra)

### Nubia Maria Rivera Suarez (CC 36169589)
- **Existe en Medifolios** ✅
- Siniestro: 503401505
- Empresa: POSITIVA COMPANIA DE SEGUROS SA
- Autorización: 49289330
- Admisión: 28397
- Servicio: TERAPIA FISICA INTEGRAL [931001]
