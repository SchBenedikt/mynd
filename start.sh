#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "================================================"
echo "  MYND - Start Script"
echo "================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

# 1. Check .env
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  No .env found. Creating from .env.example...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}⚠️  Edit .env with your Nextcloud credentials before use.${NC}"
fi

# 2. Install backend dependencies
echo -e "${CYAN}📦 Installing backend dependencies...${NC}"
pip3 install -q -r requirements-backend.txt 2>/dev/null || pip install -q -r requirements-backend.txt

# 3. Install frontend dependencies
echo -e "${CYAN}📦 Installing frontend dependencies...${NC}"
cd frontend
npm install --silent 2>/dev/null || npm install
cd ..

echo ""
echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""
echo -e "${CYAN}Starting services...${NC}"
echo ""
echo -e "  ${GREEN}Backend API:${NC}  http://localhost:5001"
echo -e "  ${GREEN}Frontend:${NC}    http://localhost:3000"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Start backend in background
python3 app.py &
BACKEND_PID=$!

# Start frontend
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# Trap to clean up on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# Wait for both
wait
