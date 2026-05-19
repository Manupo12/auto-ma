# Medifolios — Mapa completo de extracción

## URL y credenciales
- URL: https://www.server0medifolios.net/
- User: 55162801-2
- Pass: 55162801-2

## Flujo de login
1. Navegar a la URL
2. Campo USUARIO (id o name contiene "usuario") → 55162801-2
3. Campo CONTRASEÑA → 55162801-2
4. Botón "Ingresar"
5. **Siempre aparece popup** "Cambia tu contraseña que no es segura" → click Close
6. Dashboard: "Bienvenido, Sandra" + "REHABILITACIÓN INTEGRAL LABORAL Y OCUPACIONAL RILO SAS"

## Secciones relevantes para extracción

### 1. AGENDA DE CITAS (fuente principal de siniestros) ⭐
**Ruta:** Menú hamburguesa (Bienvenido, Sandra) → Agenda Citas

**Selector de profesional:**
- Dropdown "SELECCIONE PROFESIONAL/EQUIPO" → buscar "SANDRA PATRICIA POLANIA"
- Opciones: "SANDRA PATRICIA POLANIA - TODOS LOS PUNTOS DE ATENCION" (value=168-0) o por punto específico (168-3, 168-4, etc.)

**Calendario:**
- Vista semanal (Lun-Dom) con bloques de citas por hora
- Cada cita muestra: hora + nombre paciente + tipo servicio [código]
- Ej: "8:10-8:45 DAVID ESTIVEN FALLA [TERAPIA FISICA INTEGRAL [931001]]"
- Botones: HOY, ACTUALIZAR, MES, SEMANA, 3 DIAS, 2 DIAS, DIA

**Popup "Detalle Solicitud" (al hacer click en una cita):**
Tiene 3 tabs:
- **Datos Solicitud**: ID, nombres, edad, teléfono, email, ciudad, empresa cliente, servicio, # autorización, profesional, quien asigna, observaciones
- **Historial de Citas**: tabla con todas las citas del paciente (fecha, profesional, servicio, estado, observaciones)
- **Solicitudes Pendientes**: lista de solicitudes pendientes

**Dónde está el siniestro:**
- Campo: `txt_observaciones` (id)
- Formato: `"12 SESIONES\nNO. SINIESTRO503401505\nADMISION 28397"`
- Regex para extraer: `NO\.?\s*SINIESTRO\s*(\d+)`

**Campos extraíbles del popup:**
| Campo | Elemento | Ejemplo |
|-------|----------|---------|
| ID | `#txt_num_identificacion` | 36169589 |
| Nombre | `#txt_nombre_completo` | NUBIA MARIA RIVERA SUAREZ |
| Edad | `#txt_edad_paciente` | 64 Años, 9 Meses, 15 Dias |
| Teléfono | `#txt_telefono` | 3144054406 |
| Email | `#txt_email` | RIVERANUBIAMARIA@GMAIL.COM |
| Ciudad | `#txt_ciudad_residencia` | NEIVA - HUILA |
| Empresa | link en "EMPRESA CLIENTE" | POSITIVA COMPANIA DE SEGUROS SA |
| Servicio | `#slct_servicio_agenda_medico` | TERAPIA FISICA INTEGRAL |
| # Autorización | `#txt_num_autorizacion` | 49289330 |
| Siniestro | `#txt_observaciones` (regex) | 503401505 |
| Admisión | `#txt_observaciones` (regex) | 28397 |
| Fecha cita | `#txt_fecha_sugerida` | 2026-05-15 10:30 |
| Profesional | texto en label | SANDRA PATRICIA POLANIA |

### 2. PACIENTES (datos generales y búsqueda)
**Ruta:** Menú hamburguesa → Pacientes

**Botones en la barra superior:**
-  Nuevo paciente
-  **Listado de pacientes** (popup con tabla)
-  Guardar/Actualizar
-  Escanear data
-  ?

**Popup "Listado de Pacientes":**
- Campo búsqueda: `#gs_numHistoria` (ID del paciente, poner cédula + Enter)
- Tabla jqGrid: `#container_listado_paciente`
- Columnas: ID | TIP. ID | NOMBRES | TELEFONO | DIRECCION | EPS | SEDE | ESTADO

**Formulario DATOS PERSONALES (al buscar/crear paciente):**
- Tipo Documento, Núm. Documento, Nombres, Apellidos
- Fecha Nacimiento, Sexo, RH, Estado Civil
- Dirección, Teléfono, Email, Ocupación
- Embarazada, Discapacidad, Etnia

**Formulario DATOS GENERALES:**
- EMPRESA CLIENTE, EPS/ASEGURADORA, AFP, ARL

## Notas
- La sesión expira en ~10-15 minutos de inactividad
- El popup de cambio de contraseña aparece en cada login
- Las citas muestran pacientes por día; navegar entre fechas para encontrar pacientes específicos
- El siniestro NO está en un campo dedicado — siempre en observaciones como texto libre
