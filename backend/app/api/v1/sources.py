"""Live government source discovery endpoint."""

from fastapi import APIRouter, Query
from starlette.concurrency import run_in_threadpool

from app.schemas import SourcesResponse
from app.services.sources import collect_sources

router = APIRouter(tags=["sources"])


@router.get(
    "/sources",
    response_model=SourcesResponse,
    summary="Browse live myScheme schemes and PIB releases",
)
async def list_sources(
    q: str = Query("", description="Optional keyword, e.g. farmer or pension"),
    limit: int = Query(10, ge=1, le=50, description="Maximum items per source"),
) -> SourcesResponse:
    items, errors = await run_in_threadpool(collect_sources, q, limit=limit)
    return SourcesResponse(query=q, items=items, errors=errors)
