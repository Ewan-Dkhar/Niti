"""Grounding audit node and retry routing (real checks land in Phase 7)."""

from app.agent.state import AgentState

MAX_AUDIT_RETRIES = 2


def audit_verification_node(state: AgentState) -> dict:
    """Placeholder: Phase 7 cross-checks claims against source chunks."""
    return {
        "audit_report": {
            "is_grounded": True,
            "unsupported_claims": [],
            "confidence_score": 1.0,
            "correction_guidance": None,
        },
        "audit_retry_count": state.get("audit_retry_count", 0),
    }


def route_audit(state: AgentState) -> str:
    report = state.get("audit_report", {})
    if report.get("is_grounded") or state.get("audit_retry_count", 0) >= MAX_AUDIT_RETRIES:
        return "simplify_vernacular"
    return "re_extract"
