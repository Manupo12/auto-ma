#!/bin/bash
# ================================================================
# Script de arranque para WSL — Se ejecuta al iniciar WSL
# Guardar en: C:\Users\sandra\start-rilo.sh
# O agregar al .bashrc de WSL
# ================================================================

echo "🔍 Buscando contenedor RILO..."
CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep 'hermes-' | head -1)

if [ -z "$CONTAINER" ]; then
    echo "❌ No se encontró contenedor Hermes corriendo"
    echo "   Inicia Hermes Agent primero"
    exit 1
fi

echo "✅ Contenedor: $CONTAINER"
echo "🚀 Iniciando servicios RILO SAS..."

# Ejecutar el script de arranque dentro del contenedor
sudo docker exec -d "$CONTAINER" bash /root/fisioterapia/start.sh

echo "⏳ Esperando servicios..."
sleep 5

# Verificar que el servidor responde
if sudo docker exec "$CONTAINER" curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "✅ Servidor FastAPI: OK (puerto 8000)"
else
    echo "⚠️  Servidor FastAPI: No responde aún (esperando...)"
fi

echo ""
echo "══════════════════════════════════════════"
echo "  RILO SAS — Servicios iniciados"
echo "  📡 API:  http://localhost:8000"
echo "  🖥️  Dashboard: http://localhost:3000"
echo "══════════════════════════════════════════"
echo ""
echo "Para detener: sudo docker exec $CONTAINER pkill -f uvicorn"
