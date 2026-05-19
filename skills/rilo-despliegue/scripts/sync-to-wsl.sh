#!/bin/bash
# sync-to-wsl.sh — Copia cambios de Docker a WSL para Sandra
# Ejecutar en WSL: bash sync-to-wsl.sh

CONTAINER="${1:-hermes-a34da917}"
WSL_BACKEND="$HOME/rilo-backend/backend"
WSL_DASHBOARD="$HOME/rilo-dashboard"

echo "🔄 Sincronizando backend desde contenedor '$CONTAINER'..."
sudo docker cp "$CONTAINER:/root/fisioterapia/backend/." "$WSL_BACKEND/"
sudo chown -R "$USER:$USER" "$WSL_BACKEND"

echo "🔄 Sincronizando dashboard..."
sudo docker cp "$CONTAINER:/root/fisioterapia/dashboard/." "$WSL_DASHBOARD/"
sudo chown -R "$USER:$USER" "$WSL_DASHBOARD"

echo "✅ Sincronización completa."
echo "   Backend:  $WSL_BACKEND"
echo "   Dashboard: $WSL_DASHBOARD"
echo ""
echo "📌 Si los servicios están corriendo con --reload, se actualizan solos."
echo "   Si no, reinícialos."
