"""Tests for the LangGraph state machine skeleton."""

import asyncio
from datetime import UTC, datetime

import pytest

from app.agent.graph import run_analysis
from app.agent.nodes.audit import audit_verification_node, route_audit
from app.agent.state import AgentState
from app.services.parser import ParsedDocument


def test_graph_runs_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_parse(document_url: str, *, task_id: str, **kwargs: object) -> ParsedDocument:
        return ParsedDocument(
            source_url=document_url,
            markdown="## Eligibility\n\nAnnual income below INR 3,00,000.",
            page_count=1,
            parser="pypdf",
            fetched_at=datetime.now(UTC),
            markdown_path=None,
        )

    monkeypatch.setattr("app.agent.nodes.parse.parse_document", fake_parse)

    final_state = asyncio.run(
        run_analysis(
            {
                "task_id": "task-1",
                "raw_document_url": "https://example.gov.in/a.pdf",
                "target_language": "hi-IN",
            }
        )
    )

    assert final_state["parsed_markdown"].startswith("## Eligibility")
    assert final_state["parser"] == "pypdf"
    assert final_state["page_count"] == 1
    assert final_state["extracted_data"] == {}
    assert final_state["audit_report"]["is_grounded"] is True
    assert final_state["simplified_script"] == ""
    assert final_state["audio_output_url"] == ""


def test_graph_uses_preparsed_markdown_without_refetching(monkeypatch: pytest.MonkeyPatch) -> None:
    async def should_not_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("parse_document should not be called")

    monkeypatch.setattr("app.agent.nodes.parse.parse_document", should_not_run)

    final_state = asyncio.run(
        run_analysis(
            {
                "task_id": "task-2",
                "raw_document_url": "https://example.gov.in/a.pdf",
                "target_language": "ta-IN",
                "parsed_markdown": "## Benefits\n\nSubsidy of INR 50,000.",
            }
        )
    )

    assert final_state["parsed_markdown"] == "## Benefits\n\nSubsidy of INR 50,000."


def test_audit_node_preserves_retry_count() -> None:
    result = audit_verification_node({"audit_retry_count": 1})

    assert result["audit_retry_count"] == 1
    assert result["audit_report"]["is_grounded"] is True


def test_route_audit_passes_grounded_report() -> None:
    state: AgentState = {
        "audit_report": {"is_grounded": True},
        "audit_retry_count": 0,
    }

    assert route_audit(state) == "simplify_vernacular"


def test_route_audit_retries_ungrounded_report() -> None:
    state: AgentState = {
        "audit_report": {"is_grounded": False},
        "audit_retry_count": 0,
    }

    assert route_audit(state) == "re_extract"


def test_route_audit_stops_after_max_retries() -> None:
    state: AgentState = {
        "audit_report": {"is_grounded": False},
        "audit_retry_count": 2,
    }

    assert route_audit(state) == "simplify_vernacular"
