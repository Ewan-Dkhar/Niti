"""Grounding audit node and retry routing."""

from app.agent.state import AgentState
from app.services.audit import audit_extraction

MAX_AUDIT_RETRIES = 2


def audit_verification_node(state: AgentState) -> dict:
    report = audit_extraction(
        state.get("extracted_data", {}),
        state.get("parsed_markdown", ""),
    )
    retry_count = state.get("audit_retry_count", 0)
    if not report.is_grounded:
        retry_count += 1

    return {
        "audit_report": report.model_dump(),
        "audit_retry_count": retry_count,
    }


def route_audit(state: AgentState) -> str:
    report = state.get("audit_report", {})
    if report.get("is_grounded") or state.get("audit_retry_count", 0) >= MAX_AUDIT_RETRIES:
        return "simplify_vernacular"
    return "re_extract"
