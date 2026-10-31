"""Shared pytest fixtures for schema tests."""

import pytest


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
