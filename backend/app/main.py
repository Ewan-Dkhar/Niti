"""Niti API entrypoint.

Run locally:
    uv run uvicorn app.main:app --reload --app-dir backend
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.services.tts import media_dir

settings = get_settings()

app = FastAPI(
    title="Niti API",
    version=__version__,
    description="Clear policy. Real rights. In your language.",
)

ALLOWED_ORIGIN_REGEX = (
    r"^https?://("
    r"localhost"
    r"|127\.0\.0\.1"
    r"|10\.\d+\.\d+\.\d+"
    r"|192\.168\.\d+\.\d+"
    r"|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+"
    r"|[a-zA-Z0-9-]+\.onrender\.com"
    r"|[a-zA-Z0-9-]+\.vercel\.app"
    r")(:\d+)?$"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_private_network=True,
)

app.include_router(api_router)

# Synthesized voice notes are written here by the pipeline.
app.mount("/media", StaticFiles(directory=media_dir(settings)), name="media")


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Liveness probe used by Phase 0 smoke tests."""
    return {"status": "ok", "service": "niti-api", "version": __version__}
