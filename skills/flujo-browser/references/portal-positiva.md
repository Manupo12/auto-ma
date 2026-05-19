# ARL Positiva — Mapa completo de extracción

## URL y credenciales
- URL login: https://positivacuida.positiva.gov.co/cas/login?service=https://positivacuida.positiva.gov.co/web/j_spring_cas_security_check
- User: 1075209386MR
- Pass: Rilo2026*

## Flujo de login
1. Navegar a la URL (CAS Spring Security)
2. Campo "Usuario" → 1075209386MR
3. Campo "Clave" → Rilo2026*
4. Botón "Ingresar"
5. Dashboard: "Bienvenido" + "MARIA GREIDY RODRIGUEZ RAMIREZ PROVEEDOR RHI"

## Menú lateral (después de login)
```
Traslados
Consulta autorizaciones
Servicios de salud
Rehabilitación              ← click abre submenú
  ├── Consultar caso rhi    ⭐
  ├── Cargue agenda proveedor
  ├── Bandeja de entrada
  └── Reporte transacciones rhi
Reporte transacciones
Consulta integral            ⭐ (la más rica en datos)
Programa extra
Cambiar contraseña
Cerrar sesión
```

## Secciones para extracción

### 1. CONSULTA INTEGRAL ⭐ (fuente principal de datos del paciente)
**Ruta:** Menú → Consulta integral

**Buscador:**
- Tipo de Identificación: combobox (default: Cédula de ciudadanía)
- Número Identificación: textbox → poner cédula
- Número Solicitud: textbox (opcional)
- Checkbox "Todas Las Solicitudes"
- Botón "Buscar"

**Resultados: 6 PESTAÑAS con TODOS los datos:**

#### Tab 1: DATOS ASEGURADO
- Tipo y Número Identificación, Nombre, Fecha Nacimiento
- Departamento, Ciudad, Zona, Localidad, Barrio
- Dirección, Correo Electrónico
- Teléfono Fijo Particular/Laboral, Celular Particular/Laboral
- Sección Tutelas (tabla aparte)

#### Tab 2: SINIESTROS ⭐
Tabla con columnas:
| Documento | Siniestro | Fecha Siniestro | Tipo Evento | Indicador | % PCL | Estado | Calif. Origen | Diagnóstico | Gravedad | Acciones |
|-----------|-----------|-----------------|-------------|-----------|-------|--------|---------------|-------------|----------|----------|

Ejemplo (Juan Carlos Duran):
- 1193143688 | **503463870** | 02/03/2026 | AT | Propios del Trabajo | Sin determinar | CALIFICADO | Consultar | Severo | 
- 1193143688 | **503476658** | 08/04/2026 | AT | Propios del Trabajo | 0 | CALIFICADO | Consultar | Alta Inmediata | 

Campos extraíbles:
- `siniestro.id_siniestro` ← columna "Siniestro"
- `siniestro.fecha_evento` ← columna "Fecha Siniestro"
- `siniestro.diagnosticos` ← columna "Diagnóstico" (link "Consultar" para detalle)
- `siniestro.tipo` ← columna "Tipo Evento" (AT = Accidente de Trabajo)
- `siniestro.pcl_porcentaje` ← columna "% PCL"
- Botón "" al final de cada fila → probablemente abre detalle completo

#### Tab 3: REHABILITACIÓN INTEGRAL ⭐
Tabla con columnas:
| Asegurado | Id Ingreso | Fecha Ingreso | No. Siniestro | Fecha Siniestro | Proveedor Asignado | Diagnóstico | Calif. Origen | Estado | Acciones |

Ejemplo (Juan Carlos Duran):
- CC. 1193143688 JUAN CARLOS DURAN NARVAEZ | 48685733 | 03/03/2026 | 503463870 | 02/03/2026 | REHABILITACION INTEGRAL LABORAL Y OCUPACIONAL SAS | **S611 HERIDA DE DEDO(S) DE LA MANO, CON DAÑO DE LA(S) UÑA(S)** | PROFESIONAL | Cerrada

Campos extraíbles:
- `siniestro.diagnosticos` (código CIE10 + descripción) ← columna "Diagnóstico"
- `rehabilitacion.proveedor` ← columna "Proveedor Asignado"
- `rehabilitacion.estado` ← columna "Estado" (Cerrada, Activa, etc.)
- `rehabilitacion.calificacion_origen` ← columna "Calificación origen"
- `rehabilitacion.fecha_ingreso` ← columna "Fecha Ingreso"

#### Tab 4: GESTIÓN AUTORIZACIONES
(Por explorar — probablemente autorizaciones de servicios)

#### Tab 5: EVOLUCIONES
(Por explorar — historial médico/valoraciones)

#### Tab 6: BITACORAS
(Por explorar — seguimiento del caso)

### 2. CONSULTAR CASO RHI
**Ruta:** Menú → Rehabilitación (click) → Consultar caso rhi

**Buscador:**
- Tipo de Documento: combobox
- Número de Documento: textbox (cédula)
- Nro. de Matricula: textbox (opcional)
- Botón "Buscar" / "Limpiar"

**Tabla MATRICULAS:**
Columnas: No Matrícula | Fecha Matrícula | No Siniestro | Fecha Siniestro | Diagnóstico | Calificación Origen | Acciones

(Vacía hasta buscar un paciente)

## Notas
- La sesión expira rápido (~5-10 min) → verificar antes de cada acción
- La página vuelve al buscador después de inactividad
- El botón "Buscar" se deshabilita después de buscar → usar "Limpiar" para nueva búsqueda
- Los números de siniestro son clickeables pero no abren detalle visible (posiblemente popup bloqueado o abre en nueva ventana)
- Tener a mano tanto cédula como número de siniestro para búsquedas cruzadas
