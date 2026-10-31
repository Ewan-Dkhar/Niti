.PHONY: sync dev-backend dev-frontend test lint fmt verify-ingest verify-retrieval clean

sync:
	uv sync

dev-backend:
	uv run uvicorn app.main:app --reload --app-dir backend --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	uv run pytest

lint:
	uv run ruff check backend

fmt:
	uv run ruff format backend scripts

verify-ingest:
	uv run python scripts/verify_ingestion.py "$(URL)"

verify-retrieval:
	uv run python scripts/verify_retrieval.py "$(URL)" "$(QUERY)"

clean:
	rm -rf .venv .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
