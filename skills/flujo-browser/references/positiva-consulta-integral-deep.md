# Positiva — Consulta Integral (Deep Dive)

> Descubierto en sesión 2026-05-16. Juan Carlos Duran Narvaez (CC 1193143688) usado como paciente de prueba.

## Flujo de acceso
1. Login: `1075209386MR` / `Rilo2026*`
2. Menú lateral → "Consulta integral"
3. Buscar: Tipo ID = "Cédula de ciudadanía" + Número Identificación
4. Checkbox "Todas Las Solicitudes" para ver todo
5. Botón "Buscar"

## 6 Pestañas de resultados

### 1. DATOS ASEGURADO
Campos extraíbles:
- Tipo Identificación, Número Identificación
- Nombre completo
- Fecha de Nacimiento (formato DD-MM-AAAA)
- Departamento, Ciudad/Municipio, Zona, Localidad, Barrio
- Dirección de Residencia
- Correo Electrónico
- Teléfono Fijo Particular, Teléfono Fijo Laboral
- Celular Particular, Celular Laboral
- Sección Tutelas (tabla con: Número Solicitud, No. Radicado, Accionante, Fechas, Fase)

### 2. SINIESTROS (tabla)
Columnas:
1. Documento Asegurado
2. **Siniestro** (link clickeable al detalle)
3. **Fecha Siniestro** (formato DD/MM/AAAA)
4. Tipo Evento (AT = Accidente de Trabajo)
5. Indicador Tipo Accidente
6. Tipo de accidente
7. **% PCL** (Porcentaje de Pérdida de Capacidad Laboral)
8. Estado Calificación Origen
9. **Diagnóstico** (link "Consultar" + clasificación: Severo, Alta Inmediata, etc.)
10. Clasificación de Gravedad
11. Acciones (botón )

Ejemplo Juan Carlos Duran:
- Siniestro 503463870 | 02/03/2026 | AT | Propios del Trabajo | Sin determinar | CALIFICADO | Severo
- Siniestro 503476658 | 08/04/2026 | AT | Propios del Trabajo | 0% PCL | CALIFICADO | Alta Inmediata

### 3. REHABILITACIÓN INTEGRAL (tabla)
Columnas:
1. Asegurado (CC + nombre)
2. Id Ingreso (número de matrícula RHI)
3. Fecha Ingreso (formato DD/MM/AAAA HH:MM)
4. **No. Siniestro**
5. Fecha de Siniestro
6. **Proveedor Asignado** (ej: "REHABILITACION INTEGRAL LABORAL Y OCUPACIONAL SAS")
7. **Diagnóstico** (código CIE10 + descripción, ej: "S611 HERIDA DE DEDO(S) DE LA MANO, CON DAÑO DE LA(S) UÑA(S)")
8. Calificación origen (PROFESIONAL)
9. Estado (Cerrada, Activa, etc.)
10. Acciones (botón )

Ejemplo Juan Carlos Duran:
- Id Ingreso: 48685733 | Fecha: 03/03/2026 | Siniestro: 503463870
- Proveedor: REHABILITACION INTEGRAL LABORAL Y OCUPACIONAL SAS
- CIE10: S611 HERIDA DE DEDO(S) DE LA MANO...
- Estado: Cerrada

### 4-6. Pestañas adicionales (por explorar a fondo)
- GESTIÓN AUTORIZACIONES
- EVOLUCIONES
- BITACORAS
