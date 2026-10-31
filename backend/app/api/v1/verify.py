"""Citizen eligibility verification endpoint."""

from fastapi import APIRouter, HTTPException, status

from app.schemas import TaskStatus, VerifyCitizenRequest, VerifyCitizenResponse
from app.services.eligibility import evaluate_eligibility
from app.store import task_store

router = APIRouter(tags=["eligibility"])


@router.post(
    "/verify-citizen",
    response_model=VerifyCitizenResponse,
    summary="Check a citizen profile against an analyzed policy",
)
async def verify_citizen(request: VerifyCitizenRequest) -> VerifyCitizenResponse:
    record = task_store.get(request.policy_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown policy_id: {request.policy_id}",
        )

    if record.status is TaskStatus.failed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Analysis failed: {record.error or 'unknown error'}",
        )

    if record.status is not TaskStatus.completed or record.result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis is still processing; poll /results before verifying eligibility.",
        )

    policy = record.result.policy_data.model_dump()
    is_eligible, matched_clauses, missing_documents = evaluate_eligibility(
        policy, request.citizen_profile
    )

    return VerifyCitizenResponse(
        is_eligible=is_eligible,
        matched_clauses=matched_clauses,
        missing_documents=missing_documents,
    )
