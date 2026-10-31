"""Analysis submission endpoint."""

import logging

from fastapi import APIRouter, BackgroundTasks, status

from app.schemas import AnalyzeRequest, AnalyzeResponse, TaskStatus
from app.services.parser import parse_document
from app.store import task_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


async def _process_document(task_id: str) -> None:
    """Fetch and parse the document.

    Phase 5 replaces the trailing stub with the LangGraph extraction pipeline.
    """
    record = task_store.get(task_id)
    if record is None:
        logger.warning("Task %s disappeared before processing", task_id)
        return

    try:
        parsed = await parse_document(record.document_url, task_id=task_id)
    except Exception as exc:
        logger.exception("Document ingestion failed for task %s", task_id)
        record.status = TaskStatus.failed
        record.error = str(exc)
        return

    record.parsed_markdown_path = str(parsed.markdown_path) if parsed.markdown_path else None
    record.parser = parsed.parser
    record.page_count = parsed.page_count
    logger.info(
        "Parsed task %s with %s (%d pages)",
        task_id,
        parsed.parser,
        parsed.page_count,
    )


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a policy document for analysis",
)
async def analyze(request: AnalyzeRequest, background_tasks: BackgroundTasks) -> AnalyzeResponse:
    record = task_store.create(request.document_url, request.target_language)
    background_tasks.add_task(_process_document, record.task_id)
    return AnalyzeResponse(status="processing", task_id=record.task_id)
