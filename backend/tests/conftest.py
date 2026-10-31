"""Shared pytest fixtures."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.services.parser import ParsedDocument


@pytest.fixture
def policy_extraction_payload() -> dict:
    return {
        "policy_name": (
            "Street Vendors (Protection of Livelihood and Regulation of Street Vending) Scheme"
        ),
        "issuing_authority": "Ministry of Housing and Urban Affairs",
        "gazette_or_order_no": "S.O. 1234(E)",
        "effective_date": "2026-04-01",
        "target_beneficiaries": ["street vendors", "urban poor households"],
        "mandatory_eligibility": [
            "valid certificate of vending",
            "annual household income below INR 3,00,000",
        ],
        "disqualifications": ["permanent shop owners"],
        "direct_benefits": ["interest subsidy on working capital loans up to INR 50,000"],
        "penalty_or_deadlines": ["renew vending certificate before 31 March 2027"],
        "required_documents": ["Aadhaar Card", "Ration Card", "Bank Account details"],
        "citation_source_map": {
            "mandatory_eligibility[0]": "page 2, clause 4.1",
            "direct_benefits[0]": "page 3, clause 6.2",
        },
    }


@pytest.fixture
def audit_result_payload() -> dict:
    return {
        "is_grounded": True,
        "unsupported_claims": [],
        "confidence_score": 0.92,
        "correction_guidance": None,
    }


@pytest.fixture(autouse=True)
def stub_document_parser(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep API tests offline by replacing the real PDF parser."""
    markdown_path = tmp_path / "parsed.md"
    markdown_path.write_text("# Stub policy\n\nParsed body.", encoding="utf-8")

    async def fake_parse(document_url: str, *, task_id: str, **kwargs: object) -> ParsedDocument:
        return ParsedDocument(
            source_url=document_url,
            markdown="# Stub policy\n\nParsed body.",
            page_count=1,
            parser="pypdf",
            fetched_at=datetime.now(UTC),
            markdown_path=markdown_path,
        )

    monkeypatch.setattr("app.agent.nodes.parse.parse_document", fake_parse)


@pytest.fixture(autouse=True)
def mock_env_for_unit_tests(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Ensure standard unit tests stay offline and deterministic regardless of local .env."""
    if "live" not in request.keywords:
        monkeypatch.setenv("USE_MOCK_LLM", "true")
        monkeypatch.setenv("USE_MOCK_TTS", "true")
        from app.core.config import get_settings

        get_settings.cache_clear()
