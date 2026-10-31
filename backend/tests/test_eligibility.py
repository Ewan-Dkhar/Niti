"""Tests for deterministic citizen eligibility matching."""

from app.schemas import CitizenProfile
from app.services.eligibility import evaluate_eligibility

POLICY = {
    "policy_name": "Street Vendors Scheme",
    "issuing_authority": "Ministry of Housing and Urban Affairs",
    "gazette_or_order_no": "S.O. 1234(E)",
    "effective_date": "29 May 2026",
    "target_beneficiaries": ["Street vendors in urban local bodies"],
    "mandatory_eligibility": [
        "Annual household income must be below INR 3,00,000.",
        "Applicants must be a resident of Delhi.",
    ],
    "disqualifications": ["Permanent shop owners are excluded."],
    "direct_benefits": ["Interest subsidy up to INR 50,000."],
    "penalty_or_deadlines": ["Renew before 31 March 2027."],
    "required_documents": ["Aadhaar Card", "Ration Card", "Bank Account details"],
    "citation_source_map": {
        "target_beneficiaries[0]": "page 1, clause 2",
        "mandatory_eligibility[0]": "page 1, clause 3",
        "mandatory_eligibility[1]": "page 1, clause 4",
        "disqualifications[0]": "page 2, clause 5",
        "required_documents[0]": "page 2, clause 6",
        "required_documents[1]": "page 2, clause 6",
        "required_documents[2]": "page 2, clause 6",
    },
}


def profile(**overrides: object) -> CitizenProfile:
    payload: dict = {
        "income": 180_000,
        "occupation": "street_vendor",
        "state": "Delhi",
        "documents": ["Aadhaar Card", "Ration Card", "Bank passbook"],
    }
    payload.update(overrides)
    return CitizenProfile(**payload)


def test_matching_profile_is_eligible_with_cited_clauses() -> None:
    eligible, matched, missing = evaluate_eligibility(POLICY, profile())

    assert eligible is True
    assert missing == []
    assert any("page 1, clause 2" in clause for clause in matched)
    assert any("page 1, clause 3" in clause for clause in matched)


def test_income_above_ceiling_is_ineligible() -> None:
    eligible, _, _ = evaluate_eligibility(POLICY, profile(income=500_000))

    assert eligible is False


def test_income_ceiling_accepts_lakh_notation() -> None:
    policy = dict(POLICY)
    policy["mandatory_eligibility"] = ["Income must be below 3 lakh per year."]

    assert evaluate_eligibility(policy, profile(income=280_000))[0] is True
    assert evaluate_eligibility(policy, profile(income=310_000))[0] is False


def test_disqualified_occupation_is_ineligible() -> None:
    eligible, _, _ = evaluate_eligibility(POLICY, profile(occupation="permanent_shop_owner"))

    assert eligible is False


def test_state_restriction_is_enforced() -> None:
    eligible, _, _ = evaluate_eligibility(POLICY, profile(state="Maharashtra"))

    assert eligible is False


def test_missing_documents_are_listed_but_do_not_block_eligibility() -> None:
    eligible, _, missing = evaluate_eligibility(POLICY, profile(documents=[]))

    assert eligible is True
    assert missing == ["Aadhaar Card", "Ration Card", "Bank Account details"]


def test_document_aliases_match_bank_passbook() -> None:
    _, _, missing = evaluate_eligibility(
        POLICY, profile(documents=["Aadhaar", "Ration", "Bank passbook"])
    )

    assert missing == []


def test_unparseable_rules_do_not_auto_approve_or_reject() -> None:
    policy = dict(POLICY)
    policy["mandatory_eligibility"] = ["The applicant should be of good character."]

    eligible, matched, _ = evaluate_eligibility(policy, profile())

    assert eligible is True
    assert matched == ["Street vendors in urban local bodies (page 1, clause 2)"]
