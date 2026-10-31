"""Deterministic grounding checks for extracted policy rules.

The audit compares every extracted claim against the parsed source text:
numeric anchors (amounts, percentages, dates) must appear verbatim, content
words must overlap substantially, and every claim must carry a citation.
"""

from __future__ import annotations

import re

from app.schemas import AuditResult

NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
DATE_RE = re.compile(
    r"\b(?:\d{1,2}[\s./-]+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May"
    r"|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?"
    r"|Dec(?:ember)?|जनवरी|फरवरी|मार्च|अप्रैल|मई|जून|जुलाई|अगस्त|सितंबर|अक्टूबर"
    r"|नवंबर|दिसंबर)[\s,./-]+\d{4}|\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)
CONTENT_TOKEN_RE = re.compile(
    r"[a-zA-Z\u0900-\u097F\u0980-\u09FF\u0B80-\u0BFF\u0C00-\u0C7F\u0D00-\u0D7F]{3,}"
)
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "shall",
    "must",
    "will",
    "under",
    "into",
    "apply",
    "applicable",
    "such",
    "any",
    "all",
    "not",
    "are",
    "was",
    "were",
}

LIST_FIELDS = (
    "target_beneficiaries",
    "mandatory_eligibility",
    "disqualifications",
    "direct_benefits",
    "penalty_or_deadlines",
    "required_documents",
)
SCALAR_FIELDS = (
    "policy_name",
    "issuing_authority",
    "gazette_or_order_no",
    "effective_date",
)

MIN_TOKEN_SUPPORT = 0.5
NON_CLAIM_VALUES = {"not stated in document", "untitled policy"}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _numbers(text: str) -> set[str]:
    return {match.replace(",", "") for match in NUMBER_RE.findall(text)}


def _content_tokens(text: str) -> set[str]:
    return {
        token.lower() for token in CONTENT_TOKEN_RE.findall(text) if token.lower() not in STOPWORDS
    }


def _numeric_anchors_supported(claim: str, source: str) -> bool:
    source_numbers = _numbers(source)
    for number in _numbers(claim):
        if number not in source_numbers:
            return False
    return True


def _dates_supported(claim: str, source: str) -> bool:
    source_norm = _normalize(source)
    for date in DATE_RE.findall(claim):
        if _normalize(date) not in source_norm:
            return False
    return True


def _claim_supported(claim: str, source: str) -> bool:
    if not claim.strip():
        return False
    if not _numeric_anchors_supported(claim, source):
        return False
    if not _dates_supported(claim, source):
        return False

    claim_tokens = _content_tokens(claim)
    if not claim_tokens:
        return True
    source_tokens = _content_tokens(source)
    support = len(claim_tokens & source_tokens) / len(claim_tokens)
    return support >= MIN_TOKEN_SUPPORT


def audit_extraction(extracted_data: dict, source_text: str) -> AuditResult:
    """Return an AuditResult for a PolicyExtraction-shaped dict."""
    claims: list[tuple[str, str]] = []

    for field in SCALAR_FIELDS:
        value = extracted_data.get(field)
        if isinstance(value, str) and value.strip():
            if _normalize(value) in NON_CLAIM_VALUES:
                continue
            claims.append((field, value))

    for field in LIST_FIELDS:
        values = extracted_data.get(field) or []
        if not isinstance(values, list):
            continue
        for index, value in enumerate(values):
            if isinstance(value, str) and value.strip():
                claims.append((f"{field}[{index}]", value))

    citations = extracted_data.get("citation_source_map") or {}
    unsupported: list[str] = []
    supported = 0

    for label, claim in claims:
        if not _claim_supported(claim, source_text):
            unsupported.append(f"{label}: {claim}")
            continue
        if not citations.get(label):
            unsupported.append(f"missing citation for {label}")
            continue
        supported += 1

    total = len(claims)
    confidence = supported / total if total else 1.0
    guidance = None
    if unsupported:
        preview = "; ".join(unsupported[:5])
        guidance = (
            "Re-extract using only the source document. Remove or correct these "
            f"unsupported claims and add citations: {preview}"
        )

    return AuditResult(
        is_grounded=not unsupported,
        unsupported_claims=unsupported,
        confidence_score=round(confidence, 4),
        correction_guidance=guidance,
    )
