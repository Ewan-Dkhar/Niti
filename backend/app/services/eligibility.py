"""Deterministic citizen-to-policy eligibility matching.

The extractor produces prose rules. This module reads the few rule shapes that
can be checked without guessing (income ceilings/floors, occupation targeting,
explicit disqualifications, document checklists, state residency) and reports
which extracted clauses were satisfied. Anything it cannot parse is simply not
counted as a match rather than being auto-approved.
"""

from __future__ import annotations

import re

from app.schemas import CitizenProfile

INCOME_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?:annual\s+)?(?:household\s+)?income[^.\n]{0,100}?"
            r"\b(?:below|less than|under|upto|up to|not exceeding|not more than)\b"
            r"[^.\n]{0,30}?(?:INR|Rs\.?|₹)?\s*([\d][\d,]*(?:\.\d+)?(?:\s*(?:lakh|lakhs|crore|crores))?)",
            re.IGNORECASE,
        ),
        "max",
    ),
    (
        re.compile(
            r"(?:INR|Rs\.?|₹)\s*([\d][\d,]*(?:\.\d+)?(?:\s*(?:lakh|lakhs|crore|crores))?)"
            r"[^.\n]{0,30}?(?:or less|or below|and below|maximum)",
            re.IGNORECASE,
        ),
        "max",
    ),
    (
        re.compile(
            r"(?:annual\s+)?(?:household\s+)?income[^.\n]{0,100}?"
            r"\b(?:above|more than|over|at least|minimum)\b"
            r"[^.\n]{0,30}?(?:INR|Rs\.?|₹)?\s*([\d][\d,]*(?:\.\d+)?(?:\s*(?:lakh|lakhs|crore|crores))?)",
            re.IGNORECASE,
        ),
        "min",
    ),
)

STATE_PATTERNS = (
    re.compile(r"\b(?:resident|residents|domicile)\s+of\s+([A-Z][A-Za-z ]{2,30})"),
    re.compile(r"\b(?:only for|restricted to)\s+([A-Z][A-Za-z ]{2,30})"),
)

DOCUMENT_ALIASES: dict[str, tuple[str, ...]] = {
    "aadhaar": ("aadhaar", "aadhar", "uidai"),
    "ration": ("ration",),
    "bank": ("bank", "account", "passbook"),
    "pan": ("pan", "permanent account number"),
    "income": ("income", "salary", "itr"),
    "caste": ("caste", "sc", "st", "obc"),
    "domicile": ("domicile", "residence", "residential"),
    "certificate": ("certificate", "certified"),
}


def _amount(text: str) -> int:
    match = re.search(r"[\d][\d,]*(?:\.\d+)?", text)
    if match is None:
        return 0
    value = float(match.group(0).replace(",", ""))
    lowered = text.lower()
    if "crore" in lowered:
        value *= 10_000_000
    elif "lakh" in lowered:
        value *= 100_000
    return int(value)


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _citation_for(policy: dict, field: str, index: int) -> str | None:
    citations = policy.get("citation_source_map") or {}
    return citations.get(f"{field}[{index}]")


def _clause(policy: dict, field: str, index: int, text: str) -> str:
    citation = _citation_for(policy, field, index)
    return f"{text} ({citation})" if citation else text


def _occupation_tokens(occupation: str) -> set[str]:
    return {token for token in _normalize(occupation).split() if len(token) > 2}


def _occupation_match(occupation: str, text: str) -> bool:
    tokens = _occupation_tokens(occupation)
    if not tokens:
        return False
    haystack = _normalize(text)
    return all(token in haystack for token in tokens)


def _state_restriction(text: str) -> str | None:
    for pattern in STATE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return None


def _income_verdict(rule: str, income: int) -> bool | None:
    for pattern, kind in INCOME_PATTERNS:
        match = pattern.search(rule)
        if not match:
            continue
        limit = _amount(match.group(1))
        return income <= limit if kind == "max" else income >= limit
    return None


def _document_present(required: str, supplied: list[str]) -> bool:
    required_norm = _normalize(required)
    for document in supplied:
        supplied_norm = _normalize(document)
        if not supplied_norm:
            continue
        if supplied_norm in required_norm or required_norm in supplied_norm:
            return True
        for aliases in DOCUMENT_ALIASES.values():
            if any(alias in supplied_norm for alias in aliases) and any(
                alias in required_norm for alias in aliases
            ):
                return True
    return False


def evaluate_eligibility(
    policy: dict, profile: CitizenProfile
) -> tuple[bool, list[str], list[str]]:
    """Return ``(is_eligible, matched_clauses, missing_documents)``."""
    eligible = True
    matched: list[str] = []

    beneficiaries = policy.get("target_beneficiaries") or []
    for index, rule in enumerate(beneficiaries):
        if _occupation_match(profile.occupation, rule):
            matched.append(_clause(policy, "target_beneficiaries", index, rule))

    state_rules = 0
    for index, rule in enumerate(policy.get("mandatory_eligibility") or []):
        income_ok = _income_verdict(rule, profile.income)
        if income_ok is False:
            eligible = False
            continue
        if income_ok is True:
            matched.append(_clause(policy, "mandatory_eligibility", index, rule))

        restriction = _state_restriction(rule)
        if restriction:
            state_rules += 1
            if _normalize(profile.state) in _normalize(restriction):
                matched.append(_clause(policy, "mandatory_eligibility", index, rule))
            else:
                eligible = False
            continue

        if income_ok is None and _occupation_match(profile.occupation, rule):
            matched.append(_clause(policy, "mandatory_eligibility", index, rule))

    for rule in policy.get("disqualifications") or []:
        if (
            _occupation_match(profile.occupation, rule)
            or _income_verdict(rule, profile.income) is False
        ):
            eligible = False

    missing_documents: list[str] = []
    supplied = list(profile.documents or [])
    for required in policy.get("required_documents") or []:
        if not _document_present(required, supplied):
            missing_documents.append(required)

    # A state restriction that appears only in the beneficiary list still applies.
    if state_rules == 0:
        for rule in beneficiaries:
            restriction = _state_restriction(rule)
            if restriction and _normalize(profile.state) not in _normalize(restriction):
                eligible = False

    return eligible, matched, missing_documents
