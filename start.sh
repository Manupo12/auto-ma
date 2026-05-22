#!/bin/bash
# RILO SAS — Arranque persistente
# Ejecutar: bash start.sh

cd "$(dirname "$0")"

# Matar procesos viejos
echo "=== RILO SAS ==="
echo "Limpiando puertos..."
fuser -k 8000/tcp 2>/dev/null
fuser -k 3000/tcp 2>/dev/null
sleep 2

# Backend
echo "Iniciando backend :8000..."
cd /home/sandra/rilo-backend
nohup python3 -m uvicorn backend.server:app --host 0.0.0.0 --port 8000 > /tmp/rilo_backend.log 2>&1 &
echo "  Backend PID: $!"

# Dashboard (produccion, mas estable que dev)
echo "Iniciando dashboard :3000..."
cd /home/sandra/rilo-backend/dashboard
nohup npx next start -p 3000 > /tmp/rilo_dashboard.log 2>&1 &
echo "  Dashboard PID: $!"

sleep 5

echo ""
echo "=== VERIFICANDO ==="
curl -s --max-time 3 http://localhost:8000/api/health && echo "  Backend OK"
curl -s -o /dev/null -w "  Dashboard: HTTP %{http_code}\n" --max-time 5 http://localhost:3000

echo ""
echo "=== LISTO ==="
echo "Chat:      http://localhost:3000/chat"
echo "Mi Dia:    http://localhost:3000/hoy"
echo "Formatos:  http://localhost:3000/formatos"
