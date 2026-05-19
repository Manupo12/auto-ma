# Medifolios — Pacientes + Historia Clínica (Deep Dive)

> Descubierto en sesión 2026-05-16/17. Paciente: Sandra Patricia Polania Osorio (CC 55162801).

## Cómo cargar un paciente
1. Ir a Pacientes (Menú → Pacientes)
2. Campo `numero_id` en DATOS PERSONALES → escribir CC
3. Disparar Enter (o usar JS: `dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', keyCode:13, bubbles:true}))`)
4. Verificar: `document.getElementById('nombre1').value` debe tener "SANDRA"
5. El formulario se bloquea (campos disabled) — comportamiento normal

## Menú lateral (visible solo con paciente cargado)
El sidebar tiene 5 items. Todos deben explorarse.

### Pacientes
- DATOS PERSONALES: tipo doc, CC, nombres, fecha nac, sexo, RH, estado civil, dirección, tel, email, ocupación
- DATOS GENERALES: EMPRESA CLIENTE, EPS/ASEGURADORA, AFP, ARL
- DATOS ADICIONALES: responsable, acompañante
- DATOS DE HISTORIA: (sección oculta, visible con toggle)

### Historia Clínica (3 sub-pestañas)

#### Visión Clinica General (`dataUSCDIPaciente` → `USCDIPaciente`)
Renderizado en iframe. Secciones:
1. Alertas Clínicas Activas (contador + lista)
2. Alergias e Intolerancias [Editar] — contador, lista, descripción FHIR
3. Antecedentes Familiares [Editar] — contador, lista
4. Antecedentes Personales [Editar] — contador, lista
5. Antecedentes Farmacológicos [Editar] — contador, lista
6. Exposición a Factores de Riesgo [Editar] — contador, lista
7. Evaluación y Plan de Tratamiento [Editar]
8. Preocupaciones de Salud [Editar]

Cada sección tiene:
- Icono + nombre en negrita + contador numérico
- Botón [Editar] para agregar/modificar
- Texto descriptivo FHIR del estándar USCDI
- Lista de items o "No hay X registrados"

#### IA Insights (`dataInsigthsIA` → `InsightsPaciente`)
- Placeholder: "¿Te gusto esta sugerencia? Ayúdanos a mejorar"
- Requiere datos poblados para generar sugerencias

#### Abrir Formato de Historia (`dataAbrirFormatoHistoria` → `abrirFormatoHistoria`)
- Selector `slct_filtros_avanzados_historia_clinica` (Select2)
- **Lista de formatos clínicos disponibles** (dropdown):
  - CERTIFICADO DE ASISTENCIA V.2
  - CONSENTIMIENTO DE CARTA COMPROMISO PROCESO DE REHABILITACION INTEGRAL
  - CONSENTIMIENTO INFORMADO PROCESO DE REHABILITACION INTEGRAL
  - EVOLUCIÓN TERAPIAS V.2
  - FORMATO DE ASISTENCIAS CONSULTAS ESPECIALES
  - HISTORIA CLÍNICA D...
  - (lista completa truncada en snapshot — requiere scroll)
- Filtro por fechas: `txt_fecha_inicial_filtro_avanzados_historia_clinica` / `txt_fecha_final`
- Botón: "BUSCAR FECHAS DESDE INGRESOS HOSPITALARIOS"
- Editor: `iframe_editar_historia_guardada`
- Panel lateral: `div_panel_lateral_historia` → Visualizar/Resumir Seleccionado
- Impresión: `iframeImpresionHistoria` → `balanceo-reportes.medifolios.net`

### Admisiones del Paciente
- iframe: `iframe_admisiones_paciente` (src=about:blank hasta activarse)
- Contenido: ingresos hospitalarios del paciente

### Recaudos del Paciente
- iframe: `iframe_recaudos_paciente` (src=about:blank hasta activarse)
- Contenido: pagos y recaudos

### Agenda de Citas
- Grid: `container_agenda_medico`
- Filtros: Solo Pendientes, Solo Cumplidas, Solo Incumplidas, Todas
- Botón: Ver Agenda Semanal
- Columnas: HORA, PACIENTE, EMPRESA, ...

## Dropdowns superiores
1. **Configuración**: Base de Datos Externa, Configuración Formulario, Importar, Verificación Autorización, Hoja Epicrisis, Resolución 202, Fusión Pacientes, Tablas (Médicos, Medicamentos, Sedes, CUPS), **Formatos de Historia**, Variables Discretas
2. **Encuestas**: RESOLUCIÓN 0256/2016, ENCUESTA ATENCIÓN, ENCUESTA SATISFACCIÓN
3. **Otros**: Anexos Técnicos 1-10, FURIPS, FURTRAN, SOAT, Importar Alertas, **Importar Historias De Plantillas**, Solicitud Materiales

## Calculadoras médicas (accordions)
- COCKCROFT-GAULT, ESCALA GLASGOW, GASTO ENERGETICO, INDICES DE BARTEL, IMC, FRAMINGHAM, PAQUETES CIGARRILLO, CKD-EPI

## APIs de verificación
- API Nueva EPS, API ECOPETROL
- Verificación ADRES, Asmet Salud, Capital Salud, Comfamiliar, Medimas, Nueva EPS
