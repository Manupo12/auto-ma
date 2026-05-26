#!/bin/bash
# RILO SAS — Arranque persistente
# Ejecutar: bash start.sh

set -e
cd "$(dirname "$0")"

# Instalar dependencias de sistema (playwright)
echo "=== Verificando Playwright ==="
python3 -m playwright install chromium 2>/dev/null || true

# Matar solo procesos propios en los puertos
echo "=== RILO SAS ==="
echo "Limpiando puertos..."
fuser -k 8000/tcp 2>/dev/null || true
fuser -k 3000/tcp 2>/dev/null || true
sleep 2

# Backend
echo "Iniciando backend :8000..."
cd /home/sandra/rilo-backend
nohup python3 -m uvicorn backend.server:app --host 0.0.0.0 --port 8000 > /tmp/rilo_backend.log 2>&1 &
echo "  Backend PID: $!"

# Dashboard — verificar si necesita build
echo "Iniciando dashboard :3000..."
cd /home/sandra/rilo-backend/dashboard
DASHBOARD_DIR=$(pwd)
if [ ! -d "$DASHBOARD_DIR/.next" ]; then
    echo "  .next/ no existe. Ejecutando npm run build..."
    npm run build
elif [ -n "$(find "$DASHBOARD_DIR" -name '*.tsx' -newer "$DASHBOARD_DIR/.next" -print -quit 2>/dev/null)" ]; then
    echo "  .tsx mas nuevos que .next/. Reconstruyendo..."
    npm run build
fi
nohup npx next start -p 3000 > /tmp/rilo_dashboard.log 2>&1 &
echo "  Dashboard PID: $!"

# Health check con reintentos
echo ""
echo "=== VERIFICANDO ==="
for i in $(seq 1 10); do
    if curl -s --max-time 3 http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "  Backend OK (intento $i)"
        break
    fi
    [ "$i" -eq 10 ] && echo "  Backend NO respondio tras 10 intentos"
    sleep 2
done

for i in $(seq 1 15); do
    HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:3000 2>/dev/null)
    if [ "$HTTP" = "200" ] || [ "$HTTP" = "304" ]; then
        echo "  Dashboard OK (HTTP $HTTP, intento $i)"
        break
    fi
    [ "$i" -eq 15 ] && echo "  Dashboard NO respondio tras 15 intentos (HTTP $HTTP)"
    sleep 2
done

echo ""
echo "=== LISTO ==="
echo "Chat:      http://localhost:3000/chat"
echo "Mi Dia:    http://localhost:3000/hoy"
echo "Formatos:  http://localhost:3000/formatos"
