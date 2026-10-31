"""Analysis submission endpoint."""

import logging

from fastapi import APIRouter, BackgroundTasks, status

from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.store import task_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


def _process_document_stub(task_id: str) -> None:
    """Placeholder for the Phase 5 LangGraph pipeline.

    The task intentionally stays in ``processing`` until the graph exists.
    """
    logger.info("analysis pipeline not implemented yet (task_id=%s)", task_id)


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a policy document for analysis",
)
async def analyze(request: AnalyzeRequest, background_tasks: BackgroundTasks) -> AnalyzeResponse:
    record = task_store.create(request.document_url, request.target_language)
    background_tasks.add_task(_process_document_stub, record.task_id)
    return AnalyzeResponse(status="processing", task_id=record.task_id)
