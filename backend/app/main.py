"""Niti API entrypoint.

Run locally:
    uv run uvicorn app.main:app --reload --app-dir backend
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Niti API",
    version=__version__,
    description="Clear policy. Real rights. In your language.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Liveness probe used by Phase 0 smoke tests."""
    return {"status": "ok", "service": "niti-api", "version": __version__}
