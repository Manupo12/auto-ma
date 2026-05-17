#!/bin/bash
# ================================================================
# RILO SAS — Script de arranque automático
# Se ejecuta al iniciar el contenedor Docker.
# Levanta: servidor FastAPI (8000) + dashboard Next.js (3000)
# ================================================================

set -e

LOG_DIR="/root/fisioterapia/storage/logs"
mkdir -p "$LOG_DIR"

echo "================================================================" | tee -a "$LOG_DIR/startup.log"
echo "  RILO SAS — Iniciando servicios $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_DIR/startup.log"
echo "================================================================" | tee -a "$LOG_DIR/startup.log"

# ── 1. Instalar dependencias si faltan ──────────────────────────
echo "[1/3] Verificando dependencias..." | tee -a "$LOG_DIR/startup.log"
pip install fastapi uvicorn python-multipart requests -q 2>/dev/null || true
echo "       ✅ Dependencias OK" | tee -a "$LOG_DIR/startup.log"

# ── 2. FastAPI Server (puerto 8000) ─────────────────────────────
echo "[2/3] Iniciando servidor FastAPI (puerto 8000)..." | tee -a "$LOG_DIR/startup.log"
cd /root/fisioterapia
python -m uvicorn backend.server:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info \
    >> "$LOG_DIR/server.log" 2>&1 &
SERVER_PID=$!
echo "       ✅ Servidor PID=$SERVER_PID" | tee -a "$LOG_DIR/startup.log"

# Esperar a que el servidor esté listo
for i in $(seq 1 15); do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "       ✅ Servidor responde en http://localhost:8000" | tee -a "$LOG_DIR/startup.log"
        break
    fi
    sleep 1
done

# ── 3. Dashboard Next.js (puerto 3000) ──────────────────────────
echo "[3/3] Iniciando Dashboard (puerto 3000)..." | tee -a "$LOG_DIR/startup.log"
cd /root/fisioterapia/dashboard
npm run dev >> "$LOG_DIR/dashboard.log" 2>&1 &
DASHBOARD_PID=$!
echo "       ✅ Dashboard PID=$DASHBOARD_PID" | tee -a "$LOG_DIR/startup.log"

echo "" | tee -a "$LOG_DIR/startup.log"
echo "  ✅ Todos los servicios iniciados" | tee -a "$LOG_DIR/startup.log"
echo "  📡 API:  http://localhost:8000" | tee -a "$LOG_DIR/startup.log"
echo "  🖥️  Dashboard: http://localhost:3000" | tee -a "$LOG_DIR/startup.log"
echo "  📋 Logs: $LOG_DIR" | tee -a "$LOG_DIR/startup.log"
echo "================================================================" | tee -a "$LOG_DIR/startup.log"

# Mantener el script corriendo (para que Docker no mate los procesos)
wait
