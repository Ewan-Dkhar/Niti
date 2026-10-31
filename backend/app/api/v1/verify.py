"""Citizen eligibility verification endpoint (implemented in Phase 10)."""

from fastapi import APIRouter, HTTPException, status

from app.schemas import VerifyCitizenRequest, VerifyCitizenResponse

router = APIRouter(tags=["eligibility"])


@router.post(
    "/verify-citizen",
    response_model=VerifyCitizenResponse,
    summary="Check a citizen profile against an analyzed policy",
)
async def verify_citizen(request: VerifyCitizenRequest) -> VerifyCitizenResponse:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Citizen verification is implemented in Phase 10.",
    )
