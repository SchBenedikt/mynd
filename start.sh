#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [ ! -x .venv/bin/python ] || [ ! -d node_modules ] || [ ! -d frontend/node_modules ]; then
    echo "Dependencies are missing. Run ./setup.sh first." >&2
    exit 1
fi

if [ ! -f .env ]; then
    echo ".env is missing. Run ./setup.sh first." >&2
    exit 1
fi

echo "Backend: http://127.0.0.1:5001"
echo "Frontend: http://127.0.0.1:3000"
exec uv run npm run dev
