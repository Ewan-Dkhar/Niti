"""Contract tests for Pydantic schemas.

These lock the shape of data exchanged between the API and the LangGraph
pipeline before any extraction logic is written.
"""

import pytest
from pydantic import ValidationError

from app.schemas import (
    AnalyzeRequest,
    AuditResult,
    CitizenProfile,
    LanguageCode,
    PolicyExtraction,
    TaskStatus,
    VoicePayload,
)


def test_policy_extraction_accepts_valid_payload(policy_extraction_payload: dict) -> None:
    policy = PolicyExtraction.model_validate(policy_extraction_payload)

    assert policy.policy_name.startswith("Street Vendors")
    assert policy.issuing_authority == "Ministry of Housing and Urban Affairs"
    assert policy.citation_source_map["direct_benefits[0]"] == "page 3, clause 6.2"


def test_policy_extraction_optional_fields_default_to_none(
    policy_extraction_payload: dict,
) -> None:
    payload = {
        key: value
        for key, value in policy_extraction_payload.items()
        if key not in {"gazette_or_order_no", "effective_date"}
    }

    policy = PolicyExtraction.model_validate(payload)

    assert policy.gazette_or_order_no is None
    assert policy.effective_date is None


def test_policy_extraction_requires_core_fields(policy_extraction_payload: dict) -> None:
    payload = dict(policy_extraction_payload)
    del payload["policy_name"]

    with pytest.raises(ValidationError):
        PolicyExtraction.model_validate(payload)


def test_policy_extraction_rejects_non_mapping_citations(policy_extraction_payload: dict) -> None:
    payload = dict(policy_extraction_payload)
    payload["citation_source_map"] = ["page 1"]

    with pytest.raises(ValidationError):
        PolicyExtraction.model_validate(payload)


def test_audit_result_accepts_valid_payload(audit_result_payload: dict) -> None:
    audit = AuditResult.model_validate(audit_result_payload)

    assert audit.is_grounded is True
    assert audit.confidence_score == pytest.approx(0.92)


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_audit_result_rejects_out_of_range_confidence(
    audit_result_payload: dict, confidence: float
) -> None:
    payload = dict(audit_result_payload)
    payload["confidence_score"] = confidence

    with pytest.raises(ValidationError):
        AuditResult.model_validate(payload)


@pytest.mark.parametrize(
    "language_code",
    ["hi-IN", "ta-IN", "bn-IN", "te-IN", "en-IN"],
)
def test_voice_payload_accepts_supported_languages(language_code: LanguageCode) -> None:
    payload = VoicePayload(
        language_code=language_code,
        plain_text_script="नमस्ते, यह एक परीक्षण है।",
        duration_estimate_sec=60,
    )

    assert payload.language_code == language_code
    assert payload.audio_base64 is None


def test_voice_payload_rejects_unsupported_language() -> None:
    with pytest.raises(ValidationError):
        VoicePayload(
            language_code="fr-FR",
            plain_text_script="Bonjour",
            duration_estimate_sec=60,
        )


def test_voice_payload_rejects_negative_duration() -> None:
    with pytest.raises(ValidationError):
        VoicePayload(
            language_code="hi-IN",
            plain_text_script="नमस्ते",
            duration_estimate_sec=-1,
        )


@pytest.mark.parametrize(
    "language_code",
    ["hi-IN", "ta-IN", "bn-IN", "te-IN", "en-IN"],
)
def test_analyze_request_accepts_supported_languages(language_code: LanguageCode) -> None:
    request = AnalyzeRequest(
        document_url="https://egazette.gov.in/sample.pdf",
        target_language=language_code,
    )

    assert request.target_language == language_code


@pytest.mark.parametrize(
    "document_url",
    ["not-a-url", "ftp://egazette.gov.in/sample.pdf", "https://", ""],
)
def test_analyze_request_rejects_invalid_urls(document_url: str) -> None:
    with pytest.raises(ValidationError):
        AnalyzeRequest(document_url=document_url, target_language="hi-IN")


def test_analyze_request_defaults_to_hindi() -> None:
    request = AnalyzeRequest(document_url="https://egazette.gov.in/sample.pdf")

    assert request.target_language == "hi-IN"


def test_citizen_profile_rejects_negative_income() -> None:
    with pytest.raises(ValidationError):
        CitizenProfile(income=-1, occupation="street_vendor", state="Delhi")


def test_task_status_values_are_stable() -> None:
    assert {status.value for status in TaskStatus} == {"processing", "completed", "failed"}
