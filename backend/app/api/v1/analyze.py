"""Analysis submission endpoint."""

import logging

from fastapi import APIRouter, BackgroundTasks, status

from app.agent.graph import run_analysis
from app.schemas import (
    AnalysisResult,
    AnalyzeRequest,
    AnalyzeResponse,
    AuditResult,
    PolicyExtraction,
    TaskStatus,
    VoicePayload,
)
from app.store import task_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


async def _process_document(task_id: str) -> None:
    """Run the LangGraph pipeline for a submitted document."""
    record = task_store.get(task_id)
    if record is None:
        logger.warning("Task %s disappeared before processing", task_id)
        return

    try:
        final_state = await run_analysis(
            {
                "task_id": task_id,
                "raw_document_url": record.document_url,
                "target_language": record.target_language,
            }
        )
    except Exception as exc:
        logger.exception("Analysis pipeline failed for task %s", task_id)
        record.status = TaskStatus.failed
        record.error = str(exc)
        return

    record.parsed_markdown_path = final_state.get("markdown_path")
    record.parser = final_state.get("parser")
    record.page_count = final_state.get("page_count")
    record.extracted_data = final_state.get("extracted_data")
    record.audit_report = final_state.get("audit_report")
    record.simplified_script = final_state.get("simplified_script")
    record.audio_output_url = final_state.get("audio_output_url")

    extracted_data = record.extracted_data or {}
    audit_report = record.audit_report or {}
    if not extracted_data or not audit_report:
        record.status = TaskStatus.failed
        record.error = "Pipeline finished without a grounded extraction"
        return

    voice_payload = final_state.get("voice_payload") or None
    record.result = AnalysisResult(
        policy_data=PolicyExtraction.model_validate(extracted_data),
        audit_status=AuditResult.model_validate(audit_report),
        voice_payload=VoicePayload.model_validate(voice_payload) if voice_payload else None,
        audio_url=record.audio_output_url or None,
    )
    record.status = TaskStatus.completed
    logger.info(
        "Graph finished for task %s (parser=%s, pages=%s)",
        task_id,
        record.parser,
        record.page_count,
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
