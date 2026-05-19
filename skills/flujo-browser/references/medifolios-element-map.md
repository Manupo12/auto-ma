# Medifolios — Mapa completo del portal (v2 — 2026-05-16)

**URL:** `https://www.server0medifolios.net/`
**Usuario:** Sandra — REHABILITACIÓN INTEGRAL LABORAL Y OCUPACIONAL RILO SAS
**Sesión:** Expira en ~5-10 min. Al re-navegar vuelve a login. Popup "Cambia tu contraseña" aparece SIEMPRE al iniciar sesión.

---

## Dashboard post-login
- "Bienvenido, Sandra" + nombre empresa: "REHABILITACIÓN INTEGRAL LABORAL Y OCUPACIONAL RILO SAS"
- Widgets: Proyectos SCRUM, Tareas (To Do/In Progress/Completed), Calendario (Mayo 2026)
- Alertas: "3 SOLICITUD AGENDA", "2 ALERTAS PACIENTES"
- Tickets: 116236, 121781
- Panel de Notificaciones
- Footer: Version Tag V16.24.63

---

## Menú Principal (click en "Bienvenido, Sandra ")

Se abre panel lateral izquierdo con:
```
Home
Pacientes                    ← registro/búsqueda de pacientes
Admisiones
Agenda Citas                 ← gestión de citas (RHI)
Remisión Servicios
Laboratorio / Imagenología / Hospitalización
Facturación / Inventarios / Notas Contables / Pagos
CRM / Traslados / RIPS/202/0256
Reportes y Transacciones / Calidad en Salud 266
Plataforma Transaccional / Reportes Gerenciales
Agente MF1 / Centro de Soluciones / Mensajería
Parametros Generales / Perfil Usuario / Usuarios Grupos y Permisos
Licencia / Cerrar Sesión
```

---

## SECCIÓN: Pacientes

Página: "Pacientes/Historias" con sub-botones: Configuración, Encuestas, Otros, Reportes, Toma de Estudios/Muestras

### 5 botones de acción (junto al título "Pacientes")
| Botón | Ícono | Función |
|-------|-------|---------|
|  | Documento | Nuevo paciente |
| **** | **Lista** | **Listado de pacientes** ← EL QUE IMPORTA |
|  | Disquete | Guardar/Actualizar paciente |
|  | Calendario | Escanear data del paciente |
|  | Otro | ? |

### Listado de pacientes (popup jqGrid)
- Título: "Listado de Pacientes" (clase `.ui-dialog.ui-front:visible`)
- **Campo ID**: `#gs_numHistoria` (name="numHistoria") — buscar por cédula
- **Requiere dispatch de Enter** para ejecutar la búsqueda (no filtra automágicamente)
- **Tabla de resultados**: `#container_listado_paciente`
- Columnas: **ID** | TIP. ID | NOMBRES | TELEFONO | DIRECCION | EPS | SEDE | ESTADO
- Al hacer click en una fila, carga los datos del paciente en el formulario principal

**Datos de ejemplo encontrados (3 pacientes):**
| ID | TIP | NOMBRES | TELEFONO | DIRECCION | EPS |
|----|-----|---------|----------|-----------|-----|
| 1079609329 | RC | AARON FELIPE PASTRANA LAGUNA | 3208245616 | CALLE 2 N° 3 21 | CAJA DE COMPENSACION FAMILIAR |
| 1077253681 | RC | AARON GABRIEL NEIRA MEDINA | 3212795022 | CARRERA 1B N 21-16 | CAJA DE COMPENSACION FAMILIAR |
| 12117334 | CC | ABEL MARROQUIN CANO | 3175176868 | AVENIDA LA TOMA 4 70 | COLMENA SEGURO SA |

### Formulario DATOS PERSONALES
Campos del formulario principal de paciente:
- Tipo Documento (CÉDULA CIUDADANÍA), Núm. Documento
- 1er/2do Nombre, 1er/2do Apellido
- Fecha Nacimiento, Sexo Biológico, Identidad Género, RH, Estado Civil
- Extranjero?, Municipio Origen/Residencia, Zona, Vereda/Barrio
- Dirección Ppal, Teléfono Ppal/Aux2, Email
- Ocupación, Obs. Ocupación
- Embarazada, Discapacidad?, Etnia
- Documento Voluntad Anticipada?, Oposición Presunción Donación?
- Botones: Firma, Huella

### Formulario DATOS GENERALES (debajo de DATOS PERSONALES)
- EMPRESA CLIENTE, EPS/ASEGURADORA, AFP, ARL
- ... (más campos)

---

## SECCIÓN: Agenda de Citas ⭐ (CORRECCIÓN — Sandra usa esta, no Pacientes para RHI)

**CORRECCIÓN 2026-05-16:** Sandra NO usa "Pacientes" para el programa RHI. Usa **"Agenda de Citas"**. Este es el lugar donde gestiona los casos de rehabilitación.

### Página principal
- Encabezado: "Agenda de Citas"
- Botones superiores:
  - **Configuración** (menú desplegable)
  - **Solicitudes Pendientes [3]** ← muestra pacientes con citas solicitadas
  - Cuadro de Turnos
  - Ver Agenda en TV
  - Reportes
  - Encuestas (menú desplegable)
  - Buscar Disponibilidad
- Tabs: Agenda de Citas | Lista de Espera
- Selector: "PROFESIONALES/EQUIPOS DISPONIBLES" → "SELECCIONE PROFESIONAL/EQUIPO"
- Tabla de estados de citas: CUMPLIDAS, INCUMPLIDAS, PENDIENTES, PRIORITARIAS, BLOQUEOS
  - Sub-estados: CONFIRMADA, EN SALA, TELESALUD

### Popup "Solicitudes Pendientes"
Al hacer click en el botón "Solicitudes Pendientes [3]" se abre un popup con tabla:
- **Columnas**: PROFESIONAL | FEC. SOLICITADA | FEC. SOLICITUD | NOMBRES | IDENTIFICACION | TELEFONO | DIRECCION | EMAIL | REGIMEN | EPS | OBSERVACIONES
- La tabla puede aparecer vacía si no se ha seleccionado un profesional primero
- Selector de profesional en la página principal puede ser necesario

### Datos que Sandra extrae de aquí
- **Desarrollo del programa de RHI** (historial de citas, evolución del paciente)
- Información vinculada a cada cita: fechas, profesional asignado, estado

---

## Selectores JavaScript estables (usar cuando los refs del snapshot cambian)

| Elemento | Selector CSS/ID |
|----------|-----------------|
| Campo búsqueda ID (listado pacientes) | `#gs_numHistoria` |
| Tabla resultados listado | `#container_listado_paciente` |
| Popup listado pacientes | `.ui-dialog.ui-front:visible` |
| Menú hamburguesa | `a:has-text("Bienvenido, Sandra")` |
| Panel menú principal | `.navigation [role="navigation"]` |
| Botón listado pacientes | Botón con ícono  en heading Pacientes |

---

## Pitfalls Medifolios (actualizado 2026-05-16)

1. **Sesión expira MUY rápido** — ~5-10 minutos. Snapshot devuelve página vacía o login.
   - Solución: verificar antes de cada acción. Si snapshot vacío → re-navegar y re-autenticar.
2. **Popup contraseña SIEMPRE aparece** al iniciar sesión. Cerrar antes de cualquier otra acción.
3. **jqGrid usa JavaScript** — los refs del snapshot no son confiables entre sesiones. Usar selectores ID fijos.
4. **El campo ID del popup requiere Enter** — solo escribir no ejecuta la búsqueda. Hacer dispatch de KeyboardEvent.
5. **Agenda de Citas vs Pacientes** — Sandra usa Agenda de Citas para seguimiento RHI, no Pacientes. El formulario de Pacientes es para registro/consulta general.
6. **El selector de profesional puede ser obligatorio** — en Agenda de Citas, sin seleccionar profesional no se muestran datos.

> Mapeado en sesión 2026-05-16 con browser-use.
> Los refs numéricos (e15, e24) cambian entre sesiones. Usar los selectores CSS/ID estables.

## Login
| Paso | Elemento | Selector estable | Descripción |
|------|----------|-----------------|-------------|
| URL | https://www.server0medifolios.net/ | — | Página de inicio de sesión |
| Usuario | textbox "USUARIO" | `input[placeholder*="USUARIO"]` | Campo de usuario/documento |
| Contraseña | textbox "CONTRASEÑA" | `input[placeholder*="CONTRASEÑA"]` | Campo de contraseña |
| Ingresar | button "Ingresar" | `button:contains("Ingresar")` | Botón de submit |

**Popup post-login (SIEMPRE aparece):**
| Elemento | Selector |
|----------|----------|
| Diálogo "Cambia tu contraseña" | `.ui-dialog:contains("Cambia tu contraseña")` |
| Botón Close | `.ui-dialog .ui-button:contains("Close")` |

## Dashboard
| Elemento | Selector | Descripción |
|----------|----------|-------------|
| Bienvenido | `a:contains("Bienvenido, Sandra")` | Menú hamburguesa superior izq |
| Empresa | RILO SAS | Nombre visible en header |
| Tickets | 116236, 121781 | Tickets activos |

## Menú Principal (panel lateral)
Se abre con click en "Bienvenido, Sandra". Encabezado: "Menu Principal".

| Opción | Visible |
|--------|---------|
| Home | ✅ |
| **Pacientes** | ✅ ← OBJETIVO |
| Admisiones | ✅ |
| Agenda Citas | ✅ |
| Remisión Servicios | ✅ |
| Laboratorio | ✅ |
| Imagenología | ✅ |
| Hospitalización | ✅ |
| Facturación | ✅ |
| Inventarios | ✅ |
| CRM | ✅ |
| Traslados | ✅ |
| RIPS/202/0256 | ✅ |
| Reportes y Transacciones | ✅ |
| Cerrar Sesión | ✅ |

## Página Pacientes/Historias
URL: se mantiene en el dashboard pero carga panel de pacientes.

**Submenú superior:**
- Configuración
- Encuestas
- Otros
- Reportes
- Toma de Estudios/Muestras

**5 Botones de acción (íconos junto a "Pacientes"):**

| Ícono | Nombre | Función |
|-------|--------|---------|
|  | Nuevo paciente | Crear registro nuevo |
| **** | **Listado de pacientes** | Abrir popup de búsqueda |
|  | Guardar/Actualizar | Guardar cambios del formulario |
|  | Escanear data | Escanear datos del paciente |
|  | ? | Por confirmar |

## Popup "Listado de Pacientes"

**Contenedor:** `.ui-dialog.ui-front:visible` con título "Listado de Pacientes"

**jqGrid:** `#container_listado_paciente` (`.ui-jqgrid-btable`)

**Barra de búsqueda/filtros:**
| Campo | ID estable | Name | Descripción |
|-------|-----------|------|-------------|
| **ID** | `#gs_numHistoria` | `numHistoria` | **Número de documento** ← ingresar cédula aquí |
| TIP. ID | `#gs_codDocumentoIdentidad` | `codDocumentoIdentidad` | Tipo de documento |
| NOMBRES | `#gs_nombreCompleto` | `nombres` | Nombre completo |
| TELEFONO | `#gs_telefono` | `telefono` | Teléfono |
| DIRECCION | `#gs_direccion` | `direccion` | Dirección |
| EPS | `#gs_eps.nomEps` | `nomEps` | EPS |
| SEDE | `#gs_nom_sede` | `nomSede` | Sede |
| ESTADO | `#gs_estadoPaciente` | `estadoPaciente` | Estado del paciente |

**Columnas de la tabla de resultados:**
| Col | Nombre | Ejemplo |
|-----|--------|---------|
| 1 | ID | 1079609329 |
| 2 | TIP. ID | RC (Registro Civil), CC (Cédula) |
| 3 | NOMBRES | AARON FELIPE PASTRANA LAGUNA |
| 4 | TELEFONO | 3208245616 |
| 5 | DIRECCION | CALLE 2 N° 3 21 |
| 6 | EPS | CAJA DE COMPENSACION FAMILIAR |
| 7 | SEDE | (vacío en pruebas) |
| 8 | ESTADO | (vacío en pruebas) |

## Formulario DATOS PERSONALES (post-selección de paciente)
Una vez seleccionado un paciente del listado, sus datos cargan en este formulario.

**Campos relevantes para extracción:**
| Campo | ID aproximado | Uso |
|-------|--------------|-----|
| Tipo Documento | combobox CÉDULA CIUDADANÍA | Tipo de ID |
| Núm. Documento | textbox | Cédula |
| 1er Nombre | textbox | Nombre |
| 2do Nombre | textbox | Segundo nombre |
| 1er Apellido | textbox | Apellido |
| 2do Apellido | textbox | Segundo apellido |
| Fecha Nacimiento | textbox | DD/MM/AAAA |
| Sexo Biológico | combobox | M/F |
| Estado Civil | combobox | Estado |
| Municipio Residencia | combobox | Ciudad |
| Zona | combobox | Urbana/Rural |
| Dirección Ppal | textbox | Dirección |
| Teléfono Ppal | textbox | Teléfono |
| Email | textbox | Correo |
| Ocupación | combobox | Cargo |
| EPS/ASEGURADORA | combobox | EPS |
| AFP | combobox | AFP |
| ARL | combobox | ARL |

## DATOS GENERALES (debajo de DATOS PERSONALES)
- EMPRESA CLIENTE
- EPS/ASEGURADORA
- AFP
- ARL

## Sesiones — Comportamiento observado
- **Timeout:** ~5-10 minutos de inactividad → sesión expira → vuelve al login
- **Popup contraseña:** Aparece CADA VEZ que se inicia sesión (contraseña = usuario)
- **Snapshots vacíos:** Cuando la sesión expira, browser_snapshot() devuelve "(empty page)"
- **Re-autenticación:** Navegar de nuevo a MEDIFOLIOS_URL y repetir login. No se pierde el contexto.

## Técnicas útiles
- **Cuando el snapshot es muy largo (>500 líneas):** usar `browser_console()` para extraer datos específicos
- **jqGrid no responde a click normal:** usar `browser_console()` con `.jqGrid('setSelection', rowId)` 
- **Campo ID del popup:** requiere `dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', ...}))` para ejecutar búsqueda
