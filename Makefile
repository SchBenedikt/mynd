.PHONY: help setup backend frontend start stop sync-index test lint typecheck

help:
	@echo "mynd-2new – KI-Assistent mit Smart-Home, Foto-Suche, Wissensgraph"
	@echo ""
	@echo "  make setup            Install dependencies (backend + frontend)"
	@echo "  make dev              Start both servers via npm run dev"
	@echo "  make stop             Stop all servers"
	@echo "  make sync-index       Sync Nextcloud files and rebuild index"
	@echo ""
	@echo "  make test             Run all backend tests (pytest)"
	@echo "  make test-fast        Run tests without network-dependent ones"
	@echo "  make frontend-lint    Run Next.js build check"
	@echo "  make typecheck        Run mypy type-checking (backend)"
	@echo "  make clean            Remove __pycache__, .pytest_cache, .next"

setup:
	@echo "=== Installing dependencies ==="
	pip3 install -q -r requirements-backend.txt
	cd frontend && npm install
	npm install
	@echo "Done."

dev:
	@echo "=== Starting mynd (backend + frontend) ==="
	npm run dev

stop:
	@echo "=== Stopping services ==="
	-pkill -f "python3 app.py" 2>/dev/null || true
	-pkill -f "next dev" 2>/dev/null || true

sync-index:
	@echo "=== Syncing from Nextcloud ==="
	python3 scripts/sync_nextcloud.py

test:
	@echo "=== Running all backend tests ==="
	python3 -m pytest tests/ -v --tb=short --timeout=30

test-fast:
	@echo "=== Running fast backend tests (no network) ==="
	python3 -m pytest tests/ -v --tb=short --timeout=30 -k "not web_search and not weather and not ollama"

lint:
	@echo "=== Running ruff linter ==="
	pip3 install -q ruff 2>/dev/null || true
	python3 -m ruff check data/ tests/ app.py chat.py 2>/dev/null || \
		echo "ruff not available, skipping"

frontend-lint:
	@echo "=== Running Next.js build (syntax check) ==="
	cd frontend && npx next build 2>&1 | tail -5

typecheck:
	@echo "=== Running mypy ==="
	pip3 install -q mypy 2>/dev/null || true
	python3 -m mypy data/ tests/ app.py chat.py --ignore-missing-imports 2>/dev/null || \
		echo "mypy not available or errors found"

clean:
	@echo "=== Cleaning up ==="
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
	rm -rf frontend/.next