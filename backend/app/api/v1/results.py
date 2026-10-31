"""Analysis result polling endpoint."""

from fastapi import APIRouter, HTTPException, status

from app.schemas import ResultResponse
from app.store import task_store

router = APIRouter(tags=["analysis"])


@router.get(
    "/results/{task_id}",
    response_model=ResultResponse,
    summary="Fetch the status and result of an analysis task",
)
async def get_result(task_id: str) -> ResultResponse:
    record = task_store.get(task_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown task_id: {task_id}",
        )

    return ResultResponse(
        task_id=record.task_id,
        status=record.status,
        result=record.result,
        error=record.error,
    )
