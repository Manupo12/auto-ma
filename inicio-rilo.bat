@echo off
REM ================================================================
REM RILO SAS — Arranque automático para Windows (Task Scheduler)
REM Guardar en: shell:startup o ejecutar al iniciar sesión
REM ================================================================
REM 
REM OPCIÓN 1: Poner este archivo en la carpeta de inicio de Windows
REM   1. Presiona Win+R
REM   2. Escribe: shell:startup
REM   3. Copia este archivo ahí
REM   4. Cada vez que enciendas el PC, los servicios arrancan solos
REM
REM OPCIÓN 2: Usar Task Scheduler para ejecutar al iniciar Windows
REM   1. Abre Task Scheduler (taskschd.msc)
REM   2. Crear tarea básica → Al iniciar sesión
REM   3. Acción: Iniciar programa → este archivo .bat
REM ================================================================

echo ================================================================
echo   RILO SAS — Iniciando servicios
echo   %DATE% %TIME%
echo ================================================================

REM Iniciar WSL y ejecutar el script de arranque
wsl -e bash -c "sudo docker exec -d \$(sudo docker ps --format '{{.Names}}' | grep hermes- | head -1) bash /root/fisioterapia/start.sh"

echo.
echo Esperando servicios...
timeout /t 8 /nobreak > nul

echo.
echo ================================================================
echo   RILO SAS — Listo
echo   Dashboard: http://localhost:3000
echo   API:       http://localhost:8000
echo ================================================================
echo.
echo Para detener los servicios, cierra esta ventana o ejecuta:
echo   wsl -e bash -c "sudo docker exec CONTAINER_ID pkill -f uvicorn"
echo.
pause
