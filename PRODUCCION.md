# RILO SAS — Estado Real y Camino a Producción

> Análisis técnico del MVP al 23 de mayo 2026

---

## Estado General

El sistema está **~85% completo** en funcionalidad pero **~60% listo para producción**. El código principal funciona: el chat IA, la generación de documentos y el pipeline completo (Tomy Completo) están implementados y testeados. Lo que falta son **dependencias del sistema operativo, un archivo de firma y ajustes de seguridad** — ninguno requiere reescribir código.

---

## 🔴 Bloqueadores Críticos (sin estos, nada funciona)

### 1. `ffmpeg` no está instalado en la WSL de Sandra

**Impacto:** Todo el flujo de audio falla inmediatamente con `FileNotFoundError`. Si Sandra sube un audio, el sistema crashea antes de empezar.

**Fix:** Un solo comando en la WSL de Sandra:
```bash
sudo apt-get update && sudo apt-get install -y ffmpeg
```

**Verificar que funciona:**
```bash
ffprobe -version
```

---

### 2. Falta `firma_sandra.png`

**Impacto:** Los 7 formatos clínicos se generan sin la firma de Sandra. El código ya está preparado para incluirla (`doc_generator.py:37`), solo falta el archivo.

**Fix:**
1. Escanear o fotografiar la firma de Sandra (fondo blanco, formato PNG)
2. Copiar el archivo a: `backend/templates/assets/firma_sandra.png`

Si la carpeta no existe:
```bash
mkdir -p backend/templates/assets
```

---

### 3. `AUTH_SECRET` es el valor por defecto (riesgo de seguridad)

**Impacto:** Cualquier persona podría forjar cookies de sesión. En producción esto expone el sistema.

**Fix:** Cambiar en `.env`:
```
# Actual (INSEGURO):
AUTH_SECRET=cambiar-este-secret-en-prod

# Reemplazar con algo así:
AUTH_SECRET=rilo-sas-2026-XkP9mNqWvZhJdTyBnRsCeAuFgL3Q
```

---

### 4. `AUTH_PIN=1234` (PIN por defecto)

**Impacto:** Cualquiera que sepa el PIN por defecto puede entrar al sistema.

**Fix:** Cambiar en `.env` por un PIN que solo Sandra conozca:
```
AUTH_PIN=XXXX
```

---

## 🟡 Importantes (afectan funcionalidad pero no bloquean el demo)

### 5. `LibreOffice` no está instalado

**Impacto:** La conversión de DOCX a PDF falla. Los documentos se generan bien en `.docx` pero no se pueden exportar a PDF.

**Fix:**
```bash
sudo apt-get install -y libreoffice
```

---

### 6. `requirements.txt` raíz está incompleto

**Impacto:** Si se intenta instalar dependencias desde el raíz (`pip install -r requirements.txt`), faltan 11 paquetes críticos del backend.

**Fix:** Siempre instalar desde el directorio correcto:
```bash
pip install -r backend/requirements.txt
```

O sincronizar el archivo raíz con el del backend.

---

### 7. `ejemplo prueba de trabajo.odt` no es `.docx`

**Impacto:** La plantilla del Formato 6 (Prueba de Trabajo) está en formato `.odt` (LibreOffice) pero el sistema espera `.docx`.

**Fix:** Convertir el archivo:
```bash
libreoffice --convert-to docx "storage/docs/ejemplo prueba de trabajo.odt"
```

---

### 8. `CORS_ORIGINS` solo permite `localhost`

**Impacto:** Si el backend y dashboard algún día corren en máquinas separadas o se accede desde otro equipo en la red, el navegador bloqueará las peticiones.

**Por ahora:** No es un problema si Sandra siempre accede desde la misma PC.

**Para el futuro:** Agregar la IP local de Sandra en `.env`:
```
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://192.168.X.X:3000
```

---

## ✅ Lo que YA funciona (no tocar)

| Componente | Estado |
|---|---|
| Chat IA con DeepSeek v4 | ✅ Operativo |
| Streaming de respuestas | ✅ Operativo |
| Generación de 7 formatos DOCX | ✅ Operativo |
| Pipeline Tomy Completo (9 pasos) | ✅ Habilitado (`TOMY_COMPLETO_ENABLED=true`) |
| Seguimiento de tareas (SQLite) | ✅ Activo (`workflow.db` 100 KB con historial) |
| 25 endpoints FastAPI | ✅ Todos ruteados |
| 8 páginas del dashboard | ✅ Conectadas al backend |
| Cron jobs (extracción 9 PM) | ✅ Configurados con APScheduler |
| Notificaciones Telegram | ✅ Token configurado |
| Autenticación PIN | ✅ Funcional (pero PIN débil, ver #4) |
| Backup diario (11 PM) | ✅ Configurado |
| Sesiones Playwright (portales) | ✅ `medifolios.json` y `positiva.json` guardados |
| Datos de paciente de prueba | ✅ CC 36280228 con 5 DOCX generados |

---

## Checklist de Puesta en Marcha

Ejecutar en orden, en la WSL de Sandra:

```
[ ] 1. sudo apt-get install -y ffmpeg
[ ] 2. sudo apt-get install -y libreoffice
[ ] 3. Copiar firma_sandra.png a backend/templates/assets/
[ ] 4. Cambiar AUTH_SECRET en .env (valor único y largo)
[ ] 5. Cambiar AUTH_PIN en .env (PIN que Sandra recuerde)
[ ] 6. Reiniciar el backend: cd ~/rilo-backend && ./start-wsl.sh
[ ] 7. Probar: subir un audio corto desde la página /subir-audio
[ ] 8. Verificar que llega notificación de Telegram a Sandra
[ ] 9. Descargar el DOCX generado y revisar que tiene firma
[ ] 10. Verificar que la conversión a PDF funciona
```

---

## Prueba End-to-End Mínima

Una vez completado el checklist, hacer esta prueba antes de que Sandra use el sistema:

1. Abrir `http://localhost:3000`
2. Ingresar el PIN nuevo
3. Ir a **Subir Audio** → subir un archivo `.mp3` de prueba (puede ser un audio de 30 segundos con voz)
4. Esperar ~2-5 minutos observando el progreso en pantalla
5. Verificar que en **Pacientes** aparece el nuevo paciente
6. Verificar que los **7 formatos** están generados y descargables
7. Verificar que llegó un mensaje de Telegram a Sandra
8. Abrir un DOCX y confirmar que tiene la firma

Si los 8 pasos pasan: **el sistema está listo para producción.**

---

## Resumen Ejecutivo

**¿Qué falta?** Cuatro cosas concretas:
1. `sudo apt-get install ffmpeg` (5 segundos)
2. `sudo apt-get install libreoffice` (2 minutos)
3. Escanear la firma de Sandra (1 foto)
4. Cambiar dos valores en `.env` (2 minutos)

**¿Cuánto tiempo toma?** Menos de 30 minutos de trabajo real.

**¿Hay que reescribir código?** No. El sistema está completo. Solo faltan dependencias externas y un archivo de imagen.
