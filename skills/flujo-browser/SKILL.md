---
name: flujo-browser
description: Flujo completo v2 para extracción de portales, generación de documentos clínicos con validación, selección de formato, y loop de corrección post-rechazo. MAPA COMPLETO de Medifolios y ARL Positiva tras 7 pasadas de exploración profunda (27/27 secciones). Incluye dashboard Next.js y módulo de custodia.
triggers:
  - "extraer de portal"
  - "generar documentos"
  - "flujo completo"
  - "abrir medifolios"
  - "abrir positiva"
  - "corregir documento"
  - "mapa portales"
---

# Flujo Completo v2 — MAPA DEFINITIVO (6 pasadas)

## 🟢 MEDIFOLIOS (server0medifolios.net)

**Login:** USUARIO=55162801-2 / CONTRASEÑA=55162801-2
**Usuario:** Sandra (REHABILITACIÓN INTEGRAL LABORAL Y OCUPACIONAL RILO SAS)
⚠️ Cerrar popup "Cambia tu contraseña que no es segura"

### PACIENTES/HISTORIAS (sección principal)

**Barra superior:**
- Configuración  (Base Datos Externa, Formulario Pacientes, Importar, Epicrisis, Resolución 202, Fusión Pacientes, Formatos de Historia, Variables Discretas, etc.)
- Encuestas  (Resolución 0256, Encuesta Atención, Encuesta Satisfacción)
- Otros  (Anexos Técnicos 1/2/3/9/10, FURIPS, FURTRAN, SOAT, Importar Historias, Solicitud Materiales)
- Reportes
- Toma de Estudios/Muestras

**Sidebar izquierdo (con paciente cargado):**
1. **Pacientes** — Formulario completo:
   - DATOS PERSONALES: Tipo Doc, Núm Documento, Nombres, Apellidos, Fecha Nac, Sexo, RH, Estado Civil, Dirección, Teléfono, Email, Ocupación, etc.
   - DATOS GENERALES: EMPRESA CLIENTE, EPS/ASEGURADORA, AFP, ARL, REGIMEN, etc.
   - DATOS ADICIONALES (sección colapsable)
   - DATOS DE HISTORIA (sección oculta)

2. **Historia Clínica** ⭐⭐⭐ (3 subpestañas):
   - Visión Clinica General: Alertas Clínicas, Alergias, Antecedentes (Familiares, Personales, Farmacológicos), Exposición a Riesgos, Evaluación y Plan de Tratamiento, Preocupaciones de Salud
   - IA Insights (placeholder)
   - Abrir Formato de Historia → **10 FORMATOS**:
     1. CERTIFICADO DE ASISTENCIA V.2
     2. CONSENTIMIENTO CARTA COMPROMISO REHAB INTEGRAL
     3. CONSENTIMIENTO INFORMADO REHAB INTEGRAL
     4. EVOLUCIÓN TERAPIAS V.2
     5. FORMATO DE ASISTENCIAS CONSULTAS ESPECIALES
     6. HISTORIA CLÍNICA DE FISIOTERAPIA V.2
     7. INFORME DE TERAPIA V.2
     8. NOTA DE EVOLUCIÓN, NO RIPS
     9. RECOMENDACIONES
     10. TEST ARTICULAR

3. **Admisiones del Paciente** — iframe (ingresos/egresos)
4. **Recaudos del Paciente** — iframe (pagos)
5. **Agenda de Citas** — Grid con citas del paciente (Pendientes/Cumplidas/Incumplidas/Todas)

**PANEL LATERAL DERECHO (en Historia Clínica):**
```
[Visualizar Seleccionado] [Resumir Seleccionado] [Epicrisis]
Búsqueda Avanzada (filtros por fechas, formatos, ingresos hospitalarios)
[Seleccionar Todo/Ninguno]
Tabla de documentos (checkboxes):
  Columnas: FECHA INICIO | COD. RIESGO/ALERGIA | DESC. RIESGO/ALERGIA | ESTADO | FECHA INACTIVACION | TRATAMIENTO
[Cerrar] [Imprimir]
```

**Botones del formulario:** Nuevo (), Listado (), Guardar (), Escanear (), Opciones Paciente (), Firma, Huella, Validar, Buscar Autorización

### AGENDA CITAS (sección independiente)

**Flujo:** Menú → Agenda Citas → Seleccionar "SANDRA PATRICIA POLANIA - TERAPEUTA FÍSICA"
- Calendario semanal (MES/SEMANA/3 DÍAS/2 DÍAS/DÍA)
- Estados: CUMPLIDAS, INCUMPLIDAS, PENDIENTES (CONFIRMADA, EN SALA, TELESALUD), PRIORITARIAS, BLOQUEOS
- Botones: Solicitudes Pendientes [3], Cuadro de Turnos, Reportes, Buscar Disponibilidad, Ver Agenda en TV

**Click en cita → Popup "Detalle Solicitud" (3 tabs):**
- **Datos Solicitud:** IDENTIFICACIÓN, NOMBRES, EDAD, TELÉFONO, EMAIL, EMPRESA CLIENTE, SERVICIO, No. AUTORIZACIÓN, PROFESIONAL, QUIEN ASIGNO, PUNTO ATENCIÓN, FECHA SOLICITUD, OBSERVACIONES
- **Historial de Citas:** Tabla FECHA | PROFESIONAL | PUNTO ATENCIÓN | SERVICIO | # AUTORIZACIÓN | ESTADO | USUARIO | OBSERVACIONES
- **Solicitudes Pendientes**

🔑 **EL SINIESTRO SE EXTRAE AQUÍ:** Campo OBSERVACIONES → `"NO. SINIESTRO503401505"`


## 🔵 ARL POSITIVA (positivacuida.positiva.gov.co)

**Login:** CAS → Usuario=1075209386MR / Clave=Rilo2026*
**Usuario:** MARIA GREIDY RODRIGUEZ RAMIREZ (PROVEEDOR RHI)

### Menú lateral:
```
Traslados
Consulta autorizaciones
Servicios de salud
Rehabilitación
  ├── Consultar caso RHI ⭐
  ├── Cargue agenda proveedor
  ├── Bandeja de entrada
  └── Reporte transacciones RHI
Reporte transacciones
Consulta integral ⭐⭐⭐
Programa extra
Cambiar contraseña
Cerrar sesión
```

### CONSULTA INTEGRAL (la fuente principal de datos)

**Buscador:** Tipo Identificación + Número Identificación + Número Solicitud + Checkbox "Todas Las Solicitudes"

**Al buscar paciente → 6 PESTAÑAS:**

1. **DATOS ASEGURADO:**
   Tipo Identificación, Número, Nombre, Fecha Nacimiento, Departamento, Ciudad, Zona, Localidad, Barrio, Dirección, Correo, Teléfonos (Fijo Particular, Fijo Laboral, Celular Particular, Celular Laboral), Tutelas (tabla)

2. **SINIESTROS ⭐⭐⭐:**
   Tabla: Documento Asegurado | **Siniestro** | **Fecha Siniestro** | Tipo Evento | Indicador Tipo Accidente | Tipo de accidente | **% PCL** | Estado | Calificación Origen | **Diagnóstico** | Clasificación de Gravedad | Acciones
   - Links: número de siniestro, "Consultar" (origen), diagnóstico, botón 
   - Ej Juan Carlos Duran: 503463870 (02/03/2026, AT, Severo), 503476658 (08/04/2026, AT, Alta Inmediata)

3. **REHABILITACIÓN INTEGRAL ⭐⭐⭐:**
   Tabla: Asegurado | Id Ingreso | Fecha Ingreso | No. Siniestro | Fecha Siniestro | Proveedor Asignado | **Diagnóstico (CIE10)** | Calificación origen | Estado | Acciones
   - Ej: S611 HERIDA DE DEDO(S) DE LA MANO, CON DAÑO DE LA(S) UÑA(S), Proveedor=RILO SAS, Estado=Cerrada

4. **GESTIÓN AUTORIZACIONES** ⭐ (12 columnas):
   Tabla: Número Siniestro | Código Diagnóstico | Cod. Procedimiento | Número Aut/Neg | Fecha Aut/Neg | Fecha Solicitud | Proveedor Solicitante | Proveedor Autorizado | Tipo Solicitud | Estado Solicitud | Rol Autorizador | Usuario Autorizador
   Tipos de solicitud: Atencion Inicial Urgencia, Traslado No Urgente/Urgente, Riesgo Biologico, Posurgencia, Servicio Electivo

5. **EVOLUCIONES** ⭐ (7 columnas + botón "Registrar evolución"):
   Tabla: Fecha Evolución | Usuario | Empresa | Siniestro | Requiere Incapacidad | Incapacidad | Especialidad Médica
   Especialidades (20+): CONSULTA PRIMERA VEZ POR TERAPIA OCUPACIONAL, MEDICINA LABORAL, MED FISICA Y RHB, INTERCONSULTA POR FISIOTERAPIA, etc.

6. **BITACORAS** ⭐ (2 subpestañas, 10+ columnas):
   - Bitacoras solicitudes: Tipo Solicitud | Fecha Bitácora | Solicitud | Relación Laboral | Siniestro | Asunto | Razón Social | Usuario Sistema | Observaciones | Usuario
   - Bitacoras asegurado
   Tipos de solicitud RHI: RHI - Confirmación de Cita, RHI - Gestión Órtesis Prótesis, RHI - Valoración Inicial, RHI - Valoración de Concepto, RHI - Plan de Readaptación, RHI - Finalizar Descarga Actividades, Rehabilitación Integral

### CONSULTAR CASO RHI (Rehabilitación → submenú)

**Buscador:** Tipo Documento + Número Documento + Nro. Matrícula + [Buscar] [Limpiar]

**Tabla MATRICULAS:**
Columnas: No Matrícula | Fecha Matrícula | **No Siniestro** | **Fecha Siniestro** | **Diagnóstico** | Calificación Origen | Acciones
(Sin datos sin buscar paciente)

---

## 🔄 FLUJO REAL DE SANDRA (ACTUALIZADO Mayo 2026)

```
0. [NUEVO] 8:30 PM → Sistema revisa Gmail → Correo de Medifolios con agenda de mañana
   → Extrae citas, marca pacientes NUEVOS 🆕
## 🔄 FLUJO REAL DE SANDRA (CONFIRMADO Mayo 2026)

```
1. CITA CON PACIENTE ← PRIMERO (sin cita no hay flujo)
   → Sandra atiende, conversa, toma notas en crudo
   → A VECES la conversación ya revela TODA la info de ciertos formatos
   → En ese caso: solo toca VERIFICAR en portales, no extraer desde cero

2. NOTAS CRUDAS → ORGANIZAR (pre-procesamiento)
   → Sandra guarda notas en carpeta Windows
   → Sistema puede ayudar a organizar y estructurar datos
   → Detectar qué campos faltan vs qué ya está completo

3. Medifolios → Agenda Citas → Selecciona "Sandra"
   → Click en cita del paciente → POPUP Detalle Solicitud
   → Extrae: NO. SINIESTRO de Observaciones

4. Positiva → Consulta integral → Busca por CC del paciente
   → Pestaña SINIESTROS: Confirma siniestro, fecha, diagnóstico, %PCL
   → Pestaña REHAB INTEGRAL: Diagnóstico CIE10, proveedor, estado, fechas
   → Pestaña DATOS ASEGURADO: Nombre, dirección, tel, email

5. Medifolios → Pacientes → Busca paciente (CC)
   → DATOS PERSONALES: nombres, dirección, tel
   → DATOS GENERALES: EPS, AFP, ARL, Empresa
   → Historia Clínica → Visión Clinica: antecedentes, alergias
   → Historia Clínica → Abrir Formato: seleccionar formato y visualizar

6. FUSIÓN + VALIDACIÓN → GENERAR FORMATO
   → Datos crudos de Sandra + datos de portales → fusión
   → Validación semántica (custody.py)
   → Generación DOCX + PDF/A

7. Audio de cita (OPCIONAL) → Transcripción → Datos cualitativos
```

⚠️ **IMPORTANTE**: No se puede probar el flujo completo sin una cita real. 
### Dashboard Next.js
`/root/fisioterapia/dashboard/` — 6 páginas (Home, Pacientes, Formatos, Chat, Archivos, Subir Audio) + componentes. Build verificado ✅.
**Chat IA real v8**: `chat_handler.py` con DeepSeek v4 vía OpenCode Go. ⚠️ **MODELO DE RAZONAMIENTO**: necesita max_tokens=16000 y timeout=300s (ver `rilo-despliegue/references/deepseek-v4-reasoning.md`).**Multi-archivo**: detecta CC y lee TODOS los formatos del paciente (hasta 9+, 15K chars).**Persistencia**: localStorage (50 msgs, botón Limpiar). **Endpoint diagnóstico**: GET /api/workspace.

### Módulos nuevos (Mayo 2026)

| Módulo | Función |
|--------|---------|
| `chat_handler.py` v7 🆕 | Motor de chat con LLM real (DeepSeek v4, razonamiento). ⚠️ max_tokens=16000, timeout=300s. Inyecta lista de archivos del workspace SIEMPRE (caché 5min). Busca docs (nombre parcial), lee 60 párrafos + 5 tablas. Completa formatos, verifica portales |
| `puente_docker.py` 🆕 | Bridge WSL→Docker: docker exec para disparar extracciones browser desde el dashboard |
| `email_reader.py` 🆕 | Lector IMAP Gmail: parsea correos de agenda Medifolios, extrae citas |
| `notificador.py` 🆕 | Telegram + dashboard: check 8:30 PM, recordatorios 1 día/1h antes |
| `dashboard/app/archivos/` 🆕 | Página explorador de archivos (carpeta de trabajo de Sandra) |

---

## 📊 CRUCE FORMATOS ↔ FUENTES

| Formato | Medifolios | Positiva | Audio |
|---------|-----------|----------|-------|
| 1. Análisis Exigencias | Prog. RHI (Hª Clínica) | Siniestro, Diagnóstico, Empresa, NIT, Fechas, Incapacidades | Metodología, Materiales, Peligros, Concepto, Recomendaciones |
| 2. Carta Medidas | Datos paciente | Siniestro, Diagnóstico | Recomendaciones |
| 3. Carta Recomendaciones | Datos paciente | Siniestro, Tipo, Segmento, Concepto integral | Recomendaciones, Tareas |
| 4. Cierre Caso | Hª Clínica completa | Rehab Integral (estado, fechas) | Logros, Obstáculos |
| 5. Citación Empresas | Datos paciente + empresa | Empresa, Contacto, Cargo | Tipo estudio, Objetivo |
| 6. Prueba Trabajo | Datos paciente | Siniestro, Fechas | Tareas críticas, Observación |
| 7. Valoración Desempeño | Hª Clínica + Datos personales | TODAS las pestañas | Historia ocupacional, Adaptaciones |

# Flujo Completo v2 — MAPA DEFINITIVO (7 pasadas, 27/27 secciones)

## 📁 Componentes del sistema (13 módulos backend)

| Módulo | Función |
|--------|---------|
| `json_validator.py` | ① Schemas por formato (required/recommended/optional/defaults) |
| `format_selector.py` | ② Selecciona formatos según estado (NUEVO/SEGUIMIENTO/CIERRE/PRUEBA) |
| `fusionador.py` | ③ Fusión 3 fuentes + **reconciliación siniestro** (compara Medifolios vs Positiva) |
| `custody.py` 🆕 | Validación semántica (11 patrones), cadena custodia, versionado, huella portales, modo degradado |
| `correction_loop.py` | ⑤⑥⑦ Loop corrección: interpreta rechazos de Sandra en lenguaje natural |
| `browser_session.py` | ⑧ Manejo sesión expirada: detecta login, re-autentica, guarda progreso |
| `extractor_medifolios.py` 🆕 | Sub-flujo A: 11 pasos guiados (login → Agenda → siniestro → Pacientes → Hª Clínica) |
| `extractor_positiva.py` 🆕 | Sub-flujo B: 12 pasos guiados (login → Consulta integral → 6 pestañas → Consultar RHI) |
| `pdf_archivo.py` 🆕 | PDF/A-2b (ISO 19005) para archivo legal de largo plazo |
| `verificar_backup.py` 🆕 | Restauración + verificación mensual de backup |
| `orquestador.py` | Script principal: --fusionar → --validar → --generar |
| `doc_generator.py` | Genera 7 formatos .docx + PDF con LibreOffice |
| `crear_plantillas.py` | Utilidad de plantillas |

### Dashboard Next.js
`/root/fisioterapia/dashboard/` — 5 páginas (Home, Pacientes, Formatos, Chat, Subir Audio) + 3 componentes (Sidebar, ConfianzaBadge, ReconciliacionAlert). Build verificado ✅.

### Cron jobs
- `75bd86a3daf1` — Verificación mensual de backup (día 1, 3 AM). Reporta a Telegram.

---

## 🛡️ CAPA DE CONFIABILIDAD (v3 — Mayo 2026)

### 🆕 PROTOCOLO DE VERIFICACIÓN CON MARCAS

Cada dato usado en un formato DEBE tener marca de estado de verificación:

| Marca | Significado | Ejemplo |
|-------|-------------|---------|
| ✅ | VERIFICADO — confirmado en ambos portales | `✅ Siniestro 503395736` |
| ⚠️ | PENDIENTE — falta verificar en portal | `⚠️ Cédula 12.130.558 — pendiente Medifolios` |
| ❌ | DISCREPANCIA — paciente dijo algo diferente al portal | `❌ Dirección: paciente dijo Calle 123, portal dice Calle 456` |
| 👤 | DATO DEL PACIENTE — solo fuente oral, no verificable | `👤 "Me duele al agacharme"` |

### 🆕 Puente Docker→WSL para verificación automática

El módulo `puente_docker.py` permite que el Dashboard dispare extracciones de portales:

```python
# Desde WSL
from backend.puente_docker import extraer_desde_wsl, obtener_datos_verificados

# Verificar si ya hay datos extraídos
datos = obtener_datos_verificados("12130558")

# Si no hay, disparar extracción browser (docker exec, 2-5 min)
resultado = extraer_desde_wsl("12130558")
```

Endpoints:
- `GET /api/verificar/{cc}` — consulta datos ya extraídos
- `POST /api/verificar/{cc}/extraer` — dispara extracción YA

Integrado al chat: cuando Sandra pide verificar, el `chat_handler` auto-detecta la CC e inyecta datos verificados al LLM con marcas ✅/⚠️.

### CRUCE DE SINIESTRO OBLIGATORIO

El siniestro viene de DOS fuentes y DEBEN COINCIDIR:
- Medifolios (Agenda Citas → Observaciones → "NO. SINIESTRO...")
- ARL Positiva (Consulta integral → SINIESTROS)
- Si no coinciden → 🚨 ALERTA
- Prevalece POSITIVA (fuente oficial ARL)

Cada extracción del portal pasa por estas capas de seguridad antes de llegar al documento:

### 1. Huella digital de portales (`backend/custody.py → verificar_huella()`)
Antes de extraer, se calcula un hash de la estructura de la página (selectores clave + textos esperados). Si la huella cambió → alerta en Telegram: "⚠️ El portal X cambió su estructura, verificar manualmente".

### 2. Validación semántica (`backend/custody.py → validar_semantica()`)
Cada campo extraído se valida contra patrones clínicos:
- Siniestro: 6-12 dígitos
- Fecha evento: DD/MM/AAAA, año ≥ 2020
- Diagnóstico: empieza con código CIE-10 (letra + 2-3 dígitos)
- Edad: 1-120 años
- NIT empresa: 8-12 dígitos
- Teléfono: 7-15 dígitos
Si un campo no pasa, se marca como sospechoso (confianza < 50).

### 3. Extracción en paralelo con reconciliación (`backend/fusionador.py`)
El siniestro se extrae de DOS fuentes:
- Medifolios (Agenda Citas → Observaciones)
- Positiva (Consulta integral → SINIESTROS)
Si NO coinciden → alerta: "⚠️ DISCREPANCIA". Se usa el de Positiva (fuente oficial).

### 4. Modo degradado (`backend/custody.py → modo_degradado()`)
Si la extracción falla parcialmente, el sistema NUNCA se bloquea. Los campos fallidos se marcan [VERIFICAR] y Sandra los completa manualmente en el dashboard. Screenshots guardados como evidencia.

### 5. Cadena de custodia (`backend/custody.py → Custodia`)
Cada campo rastrea su origen: fuente (medifolios/positiva/audio/manual_sandra), timestamp de extracción, screenshot, confianza, y si fue corregido por Sandra. El reporte de custodia se adjunta al documento aprobado.

### 6. PDF/A para archivo legal (`backend/pdf_archivo.py`)
Documentos APROBADOS → conversión automática a PDF/A-2b (ISO 19005). Formato usado por notarías y juzgados en Colombia. Garantiza legibilidad a 10+ años.

### 7. Backup mensual verificado (cron job `75bd86a3daf1`)
El día 1 de cada mes a las 3 AM: restaura el último backup, verifica que todos los .docx/.pdf/.json abren correctamente, y envía reporte a Sandra por Telegram.
- Extracción browser real con paciente de prueba (23 pasos totales)
- Prueba integral end-to-end (extraer → fusionar → validar → generar → Telegram → corregir)
- Probar Deepgram con audio real de una cita

## ✅ COMPLETADO (17 Mayo 2026)
- 7 pasadas de exploración: Medifolios 18/18 + Positiva 9/9 secciones
- Dashboard Next.js funcional (`/root/fisioterapia/dashboard/`)
- Módulo custody.py: validación semántica, custodia, versionado, huella, modo degradado
- Skill flujo-audio con Deepgram, diarización, filtrado, prompt clínico
- 10 formatos de Medifolios identificados
- ✅ Chat v4 (18 Mayo): workspace SIEMPRE visible para Tomy + localStorage persistencia

## 🔌 Verificación desde Dashboard (Docker-WSL bridge)

El Dashboard de Sandra puede disparar extracciones de portales vía `puente_docker.py`:
- `GET /api/verificar/{cc}` — busca datos ya extraídos de storage/data/
- `POST /api/verificar/{cc}/extraer` — dispara `docker exec` para ejecutar orquestador.py
- Si ya hay datos → se inyectan al chat con marcas ✅/⚠️/❌
- Si no → el chat sugiere extraer o deriva a Tomy Telegram

⚠️ Requiere Docker corriendo. Contenedor configurable: `DOCKER_CONTAINER=hermes-a34da917`.

## ⚠️ CC colombiana: limpiar formato antiguo

\"12'130.558\" → `re.sub(r\"[.' ]\", \"\", cc)` → \"12130558\". Siempre limpiar antes de buscar.

## ⚠️ PITFALL DE EXPLORACIÓN
El usuario (hijo/a de Sandra, técnico) espera exploración EXHAUSTIVA. Si dice "ve más allá", "itera", "haz 4-5-6 pasada", es FRUSTRACIÓN: no se han descubierto elementos importantes. **NUNCA conformarse con 1-2 pasadas.** Seguir el orden de prioridad: menús laterales → dropdowns → tabs → secciones ocultas → iframes → paneles laterales. Usar JS masivo (`browser_console`) para volcar estructura completa. Ver `references/browser-exploration-methodology.md` para técnicas detalladas.
