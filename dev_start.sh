#!/bin/bash
# Start Nexus3D Vault dev stack
set -e

cd /home/local/nexus3d/backend

# Ensure data dirs exist
mkdir -p _data/files _data/thumbs

export VAULT_DB_URL=sqlite:///./dev.sqlite
export VAULT_DATA_DIR=./_data/files
export VAULT_THUMB_DIR=./_data/thumbs
export VAULT_API_KEY=devkey

# Kill any existing
pkill -f "uvicorn app.main" 2>/dev/null || true
sleep 0.5

.venv/bin/python -m uvicorn app.main:app --port 8000 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to be ready
for i in $(seq 1 15); do
    if curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        echo "Backend ready"
        break
    fi
    sleep 1
done

cd /home/local/nexus3d/frontend
pkill -f "next dev" 2>/dev/null || true
sleep 0.5

pnpm dev &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

echo ""
echo "Backend : http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo ""
echo "PIDs: backend=$BACKEND_PID frontend=$FRONTEND_PID"

wait
