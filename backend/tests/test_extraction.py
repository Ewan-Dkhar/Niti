"""Tests for grounded rule extraction and provider selection."""

import pytest

from app.agent.nodes.extract import extract_rules_node, select_context
from app.core.config import Settings
from app.services.llm import (
    AnthropicExtractionProvider,
    ExtractionError,
    GroqExtractionProvider,
    MockExtractionProvider,
    OpenAIExtractionProvider,
    get_extraction_provider,
    heuristic_extract,
    normalize_citations,
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


def test_provider_factory_selects_groq_by_key() -> None:
    provider = get_extraction_provider(
        Settings(
            use_mock_llm=False,
            extraction_provider="auto",
            groq_api_key="test-key",
        )
    )

    assert isinstance(provider, GroqExtractionProvider)


def test_provider_factory_selects_groq_explicitly() -> None:
    provider = get_extraction_provider(
        Settings(
            use_mock_llm=False,
            extraction_provider="groq",
            groq_api_key="test-key",
        )
    )

    assert isinstance(provider, GroqExtractionProvider)


def test_provider_factory_raises_when_groq_key_missing() -> None:
    with pytest.raises(ExtractionError, match="EXTRACTION_PROVIDER=groq requires GROQ_API_KEY"):
        get_extraction_provider(
            Settings(
                use_mock_llm=False,
                extraction_provider="groq",
                groq_api_key=None,
            )
        )


def test_provider_factory_raises_for_unknown_provider() -> None:
    with pytest.raises(ExtractionError, match="Unknown extraction provider"):
        get_extraction_provider(
            Settings(
                use_mock_llm=False,
                extraction_provider="unsupported_provider",
            )
        )


def test_normalize_citations_canonicalizes_keys() -> None:
    from app.schemas import PolicyExtraction

    policy = PolicyExtraction(
        policy_name="Scheme A",
        issuing_authority="Ministry B",
        gazette_or_order_no=None,
        effective_date=None,
        target_beneficiaries=["Urban workers"],
        mandatory_eligibility=["Income below 3 lakh", "Age above 18"],
        disqualifications=[],
        direct_benefits=["Subsidy of 10000"],
        penalty_or_deadlines=[],
        required_documents=["Aadhaar"],
        citation_source_map={
            "policy_name": "Page 1",
            "issuing_authority": "Page 1",
            "target_beneficiaries.1": "Page 1, Clause 1",
            "mandatory_eligibility_1": "Page 1, Clause 2",
            "mandatory_eligibility[2]": "Page 1, Clause 3",
            "direct_benefits.1": "Page 2, Clause 4",
            "Aadhaar": "Page 2, Clause 5",
        },
    )

    normalized = normalize_citations(policy)
    citations = normalized.citation_source_map
    assert citations["policy_name"] == "Page 1"
    assert citations["issuing_authority"] == "Page 1"
    assert citations["target_beneficiaries[0]"] == "Page 1, Clause 1"
    assert citations["mandatory_eligibility[0]"] == "Page 1, Clause 2"
    assert citations["mandatory_eligibility[1]"] == "Page 1, Clause 3"
    assert citations["direct_benefits[0]"] == "Page 2, Clause 4"
    assert citations["required_documents[0]"] == "Page 2, Clause 5"


def test_groq_extraction_provider_parses_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    import json
    from types import SimpleNamespace

    extracted_payload = {
        "policy_name": "Test Groq Policy",
        "issuing_authority": "Ministry of Tests",
        "gazette_or_order_no": "123",
        "effective_date": "2026-01-01",
        "target_beneficiaries": ["Citizens"],
        "mandatory_eligibility": ["Must be eligible"],
        "disqualifications": [],
        "direct_benefits": ["Grant of 5000"],
        "penalty_or_deadlines": [],
        "required_documents": ["ID card"],
        "citation_source_map": {
            "policy_name": "Page 1",
            "issuing_authority": "Page 1",
            "target_beneficiaries[0]": "Page 1",
            "mandatory_eligibility[0]": "Page 1",
            "direct_benefits[0]": "Page 1",
            "required_documents[0]": "Page 1",
        },
    }

    mock_tool_call = SimpleNamespace(
        function=SimpleNamespace(arguments=json.dumps(extracted_payload))
    )
    mock_choice = SimpleNamespace(
        message=SimpleNamespace(tool_calls=[mock_tool_call], content=None)
    )
    mock_response = SimpleNamespace(choices=[mock_choice])

    class MockCompletions:
        def create(self, *args: object, **kwargs: object) -> object:
            return mock_response

    class MockGroqClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.chat = SimpleNamespace(completions=MockCompletions())

    monkeypatch.setattr("groq.Groq", MockGroqClient)

    provider = GroqExtractionProvider(api_key="test-key")
    result = provider.extract(document_text="Sample text", target_language="en-IN")

    assert result.policy_name == "Test Groq Policy"
    assert result.issuing_authority == "Ministry of Tests"
    assert result.target_beneficiaries == ["Citizens"]
    assert result.citation_source_map["target_beneficiaries[0]"] == "Page 1"
