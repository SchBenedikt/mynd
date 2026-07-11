#!/usr/bin/env bash
set -euo pipefail

echo "================================================"
echo "  Nextcloud LightRAG Setup"
echo "================================================"
echo ""

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# 1. Create .env if not exists
if [ ! -f .env ]; then
    echo "[1/6] Creating .env from .env.example..."
    cp .env.example .env
    echo "  ⚠️  IMPORTANT: Edit .env with your Nextcloud credentials!"
    echo "     nano .env"
else
    echo "[1/6] .env already exists."
fi

# 2. Load .env
source .env 2>/dev/null || true

# 3. Install Python dependencies
echo "[2/6] Installing Python dependencies..."
pip3 install --quiet -r scripts/requirements.txt 2>/dev/null || pip install --quiet -r scripts/requirements.txt

# 4. Install Docling for PDF parsing (best quality)
echo "[3/6] Installing Docling for PDF parsing..."
pip3 install --quiet docling 2>/dev/null || pip install --quiet docling 2>/dev/null || echo "  ⚠️  Docling install failed - PDFs will use basic parsing"

# 5. Create directories
echo "[4/6] Creating directories..."
mkdir -p data/ollama data/qdrant data/lightrag data/openwebui parsed_docs data/synced_docs logs

# 6. Start Docker services
echo "[5/6] Starting Docker services..."
docker compose up -d --build
echo "  Waiting for Ollama to start..."
sleep 15

# Wait for Ollama health
for i in $(seq 1 30); do
    if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "  ✅ Ollama is ready"
        break
    fi
    sleep 2
done

# 7. Pull models
echo "[6/6] Pulling models..."
LLM_MODEL="${LLM_MODEL:-qwen2.5:7b}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-nomic-embed-text}"

echo "  Pulling LLM: $LLM_MODEL (this may take a while)..."
docker compose exec -T ollama ollama pull "$LLM_MODEL"

echo "  Pulling embedding: $EMBEDDING_MODEL..."
docker compose exec -T ollama ollama pull "$EMBEDDING_MODEL"

echo ""
echo "================================================"
echo "  Setup Complete!"
echo "================================================"
echo ""
echo "  Services:"
echo "    Open WebUI:   http://localhost:3000"
echo "    LightRAG API: http://localhost:9621"
echo "    Ollama API:   http://localhost:11434"
echo "    Qdrant:       http://localhost:6333"
echo ""
echo "  Commands:"
echo "    make sync         - Sync files from Nextcloud"
echo "    make ingest       - Ingest into LightRAG"
echo "    make full         - Full sync + ingest"
echo "    make pipeline     - Continuous pipeline"
echo "    make query q=...  - Query your data"
echo ""
echo "  Next step: Edit .env with your Nextcloud URL, username, and password"
echo "    nano .env"
echo "================================================"