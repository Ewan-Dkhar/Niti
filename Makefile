.PHONY: sync dev-backend dev-frontend test test-live lint fmt build-frontend docker-up docker-down verify-ingest verify-retrieval verify-graph clean

sync:
	uv sync

dev-backend:
	uv run uvicorn app.main:app --reload --app-dir backend --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	uv run pytest

test-live:
	uv run pytest -m live

lint:
	uv run ruff check backend scripts

fmt:
	uv run ruff format backend scripts

build-frontend:
	cd frontend && npm run build

docker-up:
	docker compose up --build

docker-down:
	docker compose down

verify-ingest:
	uv run python scripts/verify_ingestion.py "$(URL)"

verify-retrieval:
	uv run python scripts/verify_retrieval.py "$(URL)" "$(QUERY)"

verify-graph:
	uv run python scripts/verify_graph.py "$(URL)"

clean:
	rm -rf .venv .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
