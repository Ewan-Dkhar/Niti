"""Tests for vernacular script generation."""

import pytest

from app.agent.nodes.simplify import simplify_vernacular_node
from app.core.config import Settings
from app.schemas import PolicyExtraction
from app.services.vernacular import (
    GroqSimplificationProvider,
    MockSimplificationProvider,
    get_simplification_provider,
)

SAMPLE_POLICY = PolicyExtraction(
    policy_name="Street Vendors Scheme",
    issuing_authority="Ministry of Housing and Urban Affairs",
    gazette_or_order_no="S.O. 1234(E)",
    effective_date="29 May 2026",
    target_beneficiaries=["street vendors"],
    mandatory_eligibility=["annual household income below INR 3,00,000"],
    disqualifications=["permanent shop owners"],
    direct_benefits=["interest subsidy up to INR 50,000"],
    penalty_or_deadlines=["renew before 31 March 2027"],
    required_documents=["Aadhaar Card", "Ration Card"],
    citation_source_map={"mandatory_eligibility[0]": "page 1, clause 2"},
)


@pytest.mark.parametrize("language", ["hi-IN", "ta-IN", "bn-IN", "te-IN", "en-IN"])
def test_mock_provider_builds_script_in_each_language(language: str) -> None:
    script = MockSimplificationProvider().simplify(SAMPLE_POLICY, language)

    assert script
    assert "Street Vendors Scheme" in script
    assert "INR 50,000" in script


def test_simplify_node_returns_voice_payload() -> None:
    result = simplify_vernacular_node(
        {
            "target_language": "hi-IN",
            "extracted_data": SAMPLE_POLICY.model_dump(),
        }
    )

    assert result["simplified_script"]
    payload = result["voice_payload"]
    assert payload["language_code"] == "hi-IN"
    assert payload["duration_estimate_sec"] >= 10
    assert payload["plain_text_script"] == result["simplified_script"]


def test_simplify_node_handles_empty_extraction() -> None:
    result = simplify_vernacular_node({"target_language": "ta-IN", "extracted_data": {}})

    assert result["simplified_script"] == ""
    assert result["voice_payload"] == {}


def test_factory_defaults_to_mock_without_groq_key() -> None:
    provider = get_simplification_provider(Settings(use_mock_llm=True))

    assert isinstance(provider, MockSimplificationProvider)


def test_factory_uses_groq_with_key() -> None:
    provider = get_simplification_provider(Settings(use_mock_llm=False, groq_api_key="test-key"))

    assert isinstance(provider, GroqSimplificationProvider)
