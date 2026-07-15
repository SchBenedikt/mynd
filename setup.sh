#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

command -v uv >/dev/null 2>&1 || { echo "uv is required: https://docs.astral.sh/uv/" >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "Node.js 22+ and npm are required." >&2; exit 1; }

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example. Review it before enabling integrations."
fi

echo "Installing locked backend dependencies..."
uv sync --locked --extra dev

echo "Installing locked frontend and process-runner dependencies..."
npm ci --ignore-scripts
npm ci --prefix frontend

mkdir -p data/workspace data/generated data/browser_screenshots logs

echo "Setup complete. Start MYND with ./start.sh or make dev."
