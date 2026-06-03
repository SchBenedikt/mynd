#!/usr/bin/env bash
set -euo pipefail

# Deploy script for production using docker-compose.prod.yml
# If .env.prod exists it will be used, otherwise compose runs without it

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.prod.yml"
ENV_FILE="$ROOT_DIR/.env.prod"

echo "Deploying MYND..."

if [ -f "$ENV_FILE" ]; then
  echo "Using environment file: $ENV_FILE"
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build
else
  echo "No .env.prod found — running with compose defaults."
  echo "If you want to provide secrets, create .env.prod or use your secret manager."
  docker compose -f "$COMPOSE_FILE" up -d --build
fi

echo "Deployment command finished. Check logs with: docker compose -f $COMPOSE_FILE logs -f backend"
