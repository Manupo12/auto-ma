#!/bin/bash
# RILO SAS — Arranque de servicios
# Ejecutar: bash start.sh

echo "=== RILO SAS ==="
echo ""

# Backend
echo "Iniciando backend en puerto 8000..."
cd /home/sandra/rilo-backend
python3 -m uvicorn backend.server:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"
sleep 3

# Dashboard
echo "Iniciando dashboard en puerto 3000..."
cd /home/sandra/rilo-backend/dashboard
npx next dev -p 3000 --turbo &
DASHBOARD_PID=$!
echo "  Dashboard PID: $DASHBOARD_PID"
sleep 5

echo ""
echo "=== LISTO ==="
echo "Backend:  http://localhost:8000"
echo "Dashboard: http://localhost:3000"
echo ""
echo "Pagina principal (Mi Dia): http://localhost:3000/hoy"
echo "Chat con Tomy:            http://localhost:3000/chat"
echo "Subir audio:              http://localhost:3000/subir-audio"
echo ""
echo "Para detener: kill $BACKEND_PID $DASHBOARD_PID"
echo ""
echo "Procesa tu audio de 1 hora en http://localhost:3000/chat —"
echo "adjunta el audio, pone la cedula, y Tomy hace el resto."
echo "Tarda 15-25 minutos. Te avisa en el mismo chat cuando termine."
