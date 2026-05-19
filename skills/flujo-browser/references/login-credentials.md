# Credenciales de portales — confirmadas funcionales

## Medifolios
- **URL:** https://www.server0medifolios.net/
- **Usuario:** 55162801-2
- **Contraseña:** 55162801-2
- **Login verificado:** ✅ 2026-05-16
- **Dashboard post-login:**
  - "Bienvenido, Sandra" + "REHABILITACIÓN INTEGRAL LABORAL Y OCUPACIONAL RILO SAS"
  - Secciones: Proyectos SCRUM, Tareas (To Do / In Progress / Completed), Calendario, Alertas Pacientes, Tickets
  - ⚠️ Popup "Cambia tu contraseña que no es segura" — cerrar con botón Close, no bloquea
  - Formulario: campos "USUARIO" y "CONTRASEÑA", botón "Ingresar"
  - Sin CAPTCHA

## ARL Positiva
- **URL:** https://positivacuida.positiva.gov.co/cas/login?service=https://positivacuida.positiva.gov.co/web/j_spring_cas_security_check
- **Usuario:** 1075209386MR
- **Contraseña:** Rilo2026*
- **Login verificado:** ✅ 2026-05-16
- **Dashboard post-login:**
  - "Bienvenido" + "MARIA GREIDY RODRIGUEZ RAMIREZ PROVEEDOR RHI"
  - Menú: Traslados, Consulta autorizaciones, Servicios de salud, Rehabilitación, Reporte transacciones, Consulta integral, Programa extra, Cambiar contraseña, Cerrar sesión
  - Formulario: campos "Usuario" y "Clave", botón "Ingresar"
  - Sin CAPTCHA
  - Versión: 1.0.3-SNAPSHOT

## Notas de sesión
- Ambas sesiones usan CAS/Spring Security — el redirect post-login es automático
- Tiempo de sesión estimado: ~15 minutos antes de expiry (no confirmado, asumido)
- Para re-autenticación: usar los mismos selectores de campos (e2/e3 para Medifolios, e3/e4 para Positiva)
- Los refs de elementos pueden cambiar entre sesiones — siempre verificar con snapshot primero
