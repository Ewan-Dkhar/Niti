"""Version 1 API router."""

from fastapi import APIRouter

from app.api.v1 import analyze, results, verify

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(analyze.router)
api_router.include_router(results.router)
api_router.include_router(verify.router)
