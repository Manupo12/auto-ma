#!/bin/bash
# ================================================================
# Script de arranque para WSL — Se ejecuta al iniciar WSL
# Guardar en: C:\Users\sandra\start-rilo.sh
# O agregar al .bashrc de WSL
# ================================================================

# Validar que Docker este instalado y corriendo
if ! command -v docker > /dev/null 2>&1; then
    echo "ERROR: Docker no esta instalado en WSL."
    echo "  Instala Docker Desktop para Windows y habilita integracion WSL2."
    exit 1
fi

if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker no esta corriendo o no tiene permisos."
    echo "  Asegurate de que Docker Desktop este iniciado en Windows."
    echo "  Si ves 'permission denied', ejecuta: sudo usermod -aG docker $USER"
    exit 1
fi

echo "Buscando contenedor RILO..."
CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep 'hermes-' | head -1)

if [ -z "$CONTAINER" ]; then
    echo "No se encontro contenedor Hermes corriendo"
    echo "   Inicia Hermes Agent primero"
    exit 1
fi

echo "Contenedor: $CONTAINER"
echo "Iniciando servicios RILO SAS..."

# Ejecutar el script de arranque dentro del contenedor
sudo docker exec -d "$CONTAINER" bash /root/fisioterapia/start.sh

echo "Esperando servicios..."
sleep 5

# Verificar que el servidor responde
if sudo docker exec "$CONTAINER" curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "Servidor FastAPI: OK (puerto 8000)"
else
    echo "Servidor FastAPI: No responde aun (esperando...)"
fi

echo ""
echo "========================================"
echo "  RILO SAS — Servicios iniciados"
echo "  API:  http://localhost:8000"
echo "  Dashboard: http://localhost:3000"
echo "========================================"
echo ""
echo "Para detener: sudo docker exec $CONTAINER pkill -f uvicorn"
