#!/usr/bin/env bash
# start.sh — launch both backend and frontend in one terminal
# Usage: bash start.sh
# Stop: Ctrl+C (kills both processes)

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# Colours
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║        FinOps AI  —  Starting        ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "❌  python3 not found. Install Python 3.10+"; exit 1
fi

# Check Node
if ! command -v node &>/dev/null; then
  echo "❌  node not found. Install Node.js 18+"; exit 1
fi

# Install Python deps if needed
if [ ! -d "$BACKEND/venv" ]; then
  echo -e "${GREEN}→ Creating Python venv…${NC}"
  python3 -m venv "$BACKEND/venv"
fi

source "$BACKEND/venv/bin/activate"
pip install -r "$BACKEND/requirements.txt" -q --disable-pip-version-check

# Install frontend deps if needed
if [ ! -d "$FRONTEND/node_modules" ]; then
  echo -e "${GREEN}→ Installing frontend dependencies…${NC}"
  cd "$FRONTEND" && npm install --silent
fi

echo ""
echo -e "${GREEN}✓ Backend  →  http://localhost:8000       (API docs: /docs)${NC}"
echo -e "${GREEN}✓ Frontend →  http://localhost:5173${NC}"
echo ""

# Run both, kill both on Ctrl+C
trap 'kill $(jobs -p) 2>/dev/null; echo ""; echo "Stopped."; exit 0' SIGINT SIGTERM

cd "$BACKEND" && uvicorn main:app --reload --port 8000 &
sleep 1
cd "$FRONTEND" && npm run dev -- --port 5173 &

wait
