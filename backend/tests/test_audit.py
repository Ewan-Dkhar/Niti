"""Tests for deterministic grounding audits."""

from app.agent.nodes.audit import audit_verification_node
from app.services.audit import audit_extraction
from app.services.llm import heuristic_extract

SOURCE = """<!-- page 1 -->
# Street Vendors Scheme

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


def test_grounded_extraction_passes() -> None:
    policy = heuristic_extract(SOURCE)

    report = audit_extraction(policy.model_dump(), SOURCE)

    assert report.is_grounded is True
    assert report.unsupported_claims == []
    assert report.confidence_score == 1.0


def test_fabricated_amount_is_flagged() -> None:
    policy = heuristic_extract(SOURCE).model_dump()
    policy["direct_benefits"].append("A cash transfer of INR 9,99,999")
    policy["citation_source_map"]["direct_benefits[1]"] = "page 1"

    report = audit_extraction(policy, SOURCE)

    assert report.is_grounded is False
    assert any("9,99,999" in claim for claim in report.unsupported_claims)
    assert report.correction_guidance is not None
    assert "Re-extract" in report.correction_guidance


def test_unsupported_claim_without_numbers_is_flagged() -> None:
    policy = heuristic_extract(SOURCE).model_dump()
    policy["disqualifications"].append("Applicants owning a luxury car are excluded")
    policy["citation_source_map"]["disqualifications[0]"] = "page 1"

    report = audit_extraction(policy, SOURCE)

    assert report.is_grounded is False
    assert any("luxury car" in claim for claim in report.unsupported_claims)


def test_missing_citation_is_flagged() -> None:
    policy = heuristic_extract(SOURCE).model_dump()
    policy["citation_source_map"] = {}

    report = audit_extraction(policy, SOURCE)

    assert report.is_grounded is False
    assert any("missing citation" in claim for claim in report.unsupported_claims)


def test_audit_node_increments_retry_on_failure() -> None:
    policy = heuristic_extract(SOURCE).model_dump()
    policy["direct_benefits"].append("A cash transfer of INR 9,99,999")

    result = audit_verification_node(
        {
            "parsed_markdown": SOURCE,
            "extracted_data": policy,
            "audit_retry_count": 0,
        }
    )

    assert result["audit_retry_count"] == 1
    assert result["audit_report"]["is_grounded"] is False


def test_audit_node_preserves_retry_count_when_grounded() -> None:
    policy = heuristic_extract(SOURCE).model_dump()

    result = audit_verification_node(
        {
            "parsed_markdown": SOURCE,
            "extracted_data": policy,
            "audit_retry_count": 1,
        }
    )

    assert result["audit_retry_count"] == 1
    assert result["audit_report"]["is_grounded"] is True
