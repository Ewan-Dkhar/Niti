"""Tests for grounded rule extraction and provider selection."""

import pytest

from app.agent.nodes.extract import extract_rules_node, select_context
from app.core.config import Settings
from app.services.llm import (
    AnthropicExtractionProvider,
    MockExtractionProvider,
    OpenAIExtractionProvider,
    get_extraction_provider,
    heuristic_extract,
)

SAMPLE_MARKDOWN = """<!-- page 1 -->
# Street Vendors (Protection of Livelihood and Regulation of Street Vending) Scheme

Ministry of Housing and Urban Affairs
S.O. 1234(E) dated 29 May 2026

## Eligibility

1. A street vendor must hold a valid certificate of vending.
2. Annual household income must be below INR 3,00,000.

## Benefits

The scheme provides an interest subsidy on working capital loans up to INR 50,000.

## Documents

Applicants must submit Aadhaar Card, Ration Card and Bank Account details.

<!-- page 2 -->
## Deadlines

Vending certificates must be renewed before 31 March 2027.
"""


def test_heuristic_extract_populates_grounded_fields() -> None:
    policy = heuristic_extract(SAMPLE_MARKDOWN)

    assert "Street Vendors" in policy.policy_name
    assert policy.issuing_authority == "Ministry of Housing and Urban Affairs"
    assert policy.gazette_or_order_no == "S.O. 1234(E)"
    assert policy.effective_date is not None
    assert "29 May 2026" in policy.effective_date
    assert any("certificate" in rule for rule in policy.mandatory_eligibility)
    assert any("subsidy" in rule for rule in policy.direct_benefits)
    assert any("Aadhaar" in rule for rule in policy.required_documents)
    assert any("31 March 2027" in rule for rule in policy.penalty_or_deadlines)


def test_heuristic_extract_records_citations() -> None:
    policy = heuristic_extract(SAMPLE_MARKDOWN)

    assert policy.citation_source_map
    assert "mandatory_eligibility[0]" in policy.citation_source_map
    assert "page 1" in policy.citation_source_map["mandatory_eligibility[0]"]


def test_heuristic_extract_returns_empty_lists_without_evidence() -> None:
    policy = heuristic_extract("Notice.")

    assert policy.policy_name == "Untitled Policy"
    assert policy.mandatory_eligibility == []
    assert policy.direct_benefits == []
    assert policy.required_documents == []


def test_select_context_prioritizes_rule_chunks() -> None:
    context = select_context(SAMPLE_MARKDOWN, document_id="doc1")

    assert context
    assert any(chunk.chunk_type == "section" for chunk in context)
    assert any("Aadhaar" in chunk.text for chunk in context)


def test_extract_rules_node_returns_validated_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.agent.nodes.extract.get_extraction_provider",
        lambda: MockExtractionProvider(),
    )

    result = extract_rules_node(
        {
            "task_id": "task-1",
            "target_language": "hi-IN",
            "parsed_markdown": SAMPLE_MARKDOWN,
        }
    )

    extracted = result["extracted_data"]
    assert extracted["policy_name"].startswith("Street Vendors")
    assert extracted["citation_source_map"]
    assert result["retrieved_context"]


def test_extract_rules_node_requires_markdown() -> None:
    try:
        extract_rules_node({"task_id": "task-1", "target_language": "hi-IN"})
    except ValueError as exc:
        assert "parsed_markdown" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_provider_factory_defaults_to_mock() -> None:
    provider = get_extraction_provider(Settings(use_mock_llm=True))

    assert isinstance(provider, MockExtractionProvider)


def test_provider_factory_selects_anthropic_by_key() -> None:
    provider = get_extraction_provider(
        Settings(
            use_mock_llm=False,
            extraction_provider="auto",
            anthropic_api_key="test-key",
        )
    )

    assert isinstance(provider, AnthropicExtractionProvider)


def test_provider_factory_selects_openai_by_key() -> None:
    provider = get_extraction_provider(
        Settings(
            use_mock_llm=False,
            extraction_provider="auto",
            openai_api_key="test-key",
        )
    )

    assert isinstance(provider, OpenAIExtractionProvider)
