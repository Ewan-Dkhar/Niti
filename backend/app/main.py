"""Niti API entrypoint.

Run locally:
    uv run uvicorn app.main:app --reload --app-dir backend
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__

app = FastAPI(
    title="Niti API",
    version=__version__,
    description="Clear policy. Real rights. In your language.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Liveness probe used by Phase 0 smoke tests."""
    return {"status": "ok", "service": "niti-api", "version": __version__}
