.PHONY: help setup dev stop sync-index test lint frontend-lint frontend-audit typecheck security clean check

help:
	@echo "MYND – local-first AI workspace"
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
	./setup.sh
	@echo "Done."

dev:
	@echo "=== Starting mynd (backend + frontend) ==="
	uv run npm run dev

stop:
	@echo "=== Stopping services ==="
	-pkill -f "python3 app.py" 2>/dev/null || true
	-pkill -f "next dev" 2>/dev/null || true

sync-index:
	@echo "=== Syncing from Nextcloud ==="
	uv run python scripts/sync_nextcloud.py

test:
	@echo "=== Running all backend tests ==="
	uv run pytest tests/ -v --tb=short --timeout=30

test-fast:
	@echo "=== Running fast backend tests (no network) ==="
	uv run pytest tests/ -v --tb=short --timeout=30 -k "not web_search and not weather and not ollama"

lint:
	@echo "=== Running ruff linter ==="
	uv run ruff check app/ app.py core/ data/plugins/ tests/

frontend-lint:
	@echo "=== Running frontend lint ==="
	cd frontend && npm run lint

frontend-audit:
	@echo "=== Auditing frontend dependencies ==="
	cd frontend && npm audit --audit-level=moderate

security:
	@echo "=== Running fail-closed security checks ==="
	uv run bandit -r app/ core/ data/plugins/ -ll -q
	uv run pip-audit --local --skip-editable
	cd frontend && npm audit --audit-level=moderate

typecheck:
	@echo "=== Running mypy ==="
	uv run mypy --follow-imports=skip core/vault.py core/sandbox.py app/session_store.py app/audit.py

check: test lint typecheck security frontend-lint
	cd frontend && npm run build

clean:
	@echo "=== Cleaning up ==="
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
	rm -rf frontend/.next
