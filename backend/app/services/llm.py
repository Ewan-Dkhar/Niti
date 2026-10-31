"""LLM providers for structured policy extraction.

Mock mode is the default until API keys are supplied. It is a deterministic
heuristic extractor over the real document text, not fabricated sample data.
"""

from __future__ import annotations

import logging
import re
from typing import Protocol

from app.core.config import Settings, get_settings
from app.prompts.extraction import SYSTEM_PROMPT, build_user_prompt
from app.schemas import PolicyExtraction
from app.services.audit import LIST_FIELDS, SCALAR_FIELDS
from app.services.chunker import chunk_markdown

logger = logging.getLogger(__name__)

ANTHROPIC_DEFAULT_MODEL = "claude-3-5-sonnet-latest"
OPENAI_DEFAULT_MODEL = "gpt-4o"
GROQ_DEFAULT_EXTRACTION_MODEL = "openai/gpt-oss-120b"
GROQ_FALLBACK_MODELS = ("openai/gpt-oss-120b", "qwen/qwen3.8-27b", "llama-3.3-70b-versatile")

AUTHORITY_RE = re.compile(
    r"(?im)^\s*(?:ministry|department|government of india|भारत सरकार|मंत्रालय|विभाग)"
    r"[^\n]{0,140}$"
)
GAZETTE_RE = re.compile(
    r"\b(?:S\.?\s*O\.?\s*\d+(?:\s*\([A-Za-z]+\))?|No\.\s*[A-Z0-9][A-Z0-9./-]{2,}"
    r"|का\.आ\.\s*\d+(?:\s*\([^)]+\))?)",
    re.IGNORECASE,
)
DATE_RE = re.compile(
    r"\b(?:\d{1,2}[\s./-]+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May"
    r"|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?"
    r"|Dec(?:ember)?|जनवरी|फरवरी|मार्च|अप्रैल|मई|जून|जुलाई|अगस्त|सितंबर|अक्टूबर"
    r"|नवंबर|दिसंबर)[\s,./-]+\d{4}|\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)
SCHEME_NAME_RE = re.compile(
    r"(scheme|act|rules|policy|bill|yojana|अधिनियम|योजना|नीति|नियम)",
    re.IGNORECASE,
)
CITATION_PREFIX_RE = re.compile(r"(?m)^\[[^\]]+\]\s*")

FIELD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "target_beneficiaries": (
        "beneficiar",
        "eligible",
        "vendors",
        "workers",
        "students",
        "msme",
        "households",
        "women",
        "farmers",
        "pensioners",
        "employees",
    ),
    "mandatory_eligibility": (
        "eligible",
        "must",
        "shall",
        "required",
        "income",
        "certificate",
        "age",
        "limit",
        "qualif",
    ),
    "disqualifications": (
        "not eligible",
        "excluded",
        "disqualif",
        "shall not",
        "ineligible",
    ),
    "direct_benefits": (
        "benefit",
        "subsidy",
        "credit",
        "waiver",
        "grant",
        "interest",
        "rupees",
        "₹",
    ),
    "penalty_or_deadlines": (
        "penalty",
        "deadline",
        "before",
        "within",
        "renew",
        "late fee",
        "last date",
        "expire",
    ),
    "required_documents": (
        "document",
        "aadhaar",
        "ration card",
        "certificate",
        "proof",
        "bank account",
        "pan card",
    ),
}

MAX_RULES_PER_FIELD = 6
MAX_SNIPPET_CHARS = 320


class ExtractionError(RuntimeError):
    """Structured extraction could not be completed."""


class ExtractionProvider(Protocol):
    def extract(
        self,
        *,
        document_text: str,
        target_language: str,
        correction_guidance: str | None = None,
    ) -> PolicyExtraction: ...


def _clean(text: str) -> str:
    text = re.sub(r"<!--.*?-->", " ", text)
    text = text.replace("|", " ")
    return re.sub(r"\s+", " ", text).strip(" -")


def _snippet(text: str, limit: int = MAX_SNIPPET_CHARS) -> str:
    text = _clean(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _find_policy_name(lines: list[str]) -> str:
    candidates: list[tuple[bool, str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("<!--"):
            continue
        is_heading = stripped.startswith("#")
        text = _clean(stripped.lstrip("#").strip())
        if text and len(text) <= 180:
            candidates.append((is_heading, text))

    for is_heading, candidate in candidates:
        if is_heading and len(candidate) >= 4:
            return candidate

    for _, candidate in candidates:
        if (
            2 <= len(candidate.split()) <= 20
            and len(candidate) <= 120
            and not AUTHORITY_RE.match(candidate)
        ):
            return candidate

    for _, candidate in candidates:
        if (
            SCHEME_NAME_RE.search(candidate)
            and 4 <= len(candidate) <= 120
            and len(candidate.split()) >= 3
            and not re.match(r"^(the|a|an)\b", candidate, re.IGNORECASE)
        ):
            return candidate

    return "Untitled Policy"


def _find_authority(text: str) -> str:
    match = AUTHORITY_RE.search(text)
    if match:
        return _snippet(match.group(0), 180)
    return "Not stated in document"


def heuristic_extract(document_text: str) -> PolicyExtraction:
    """Deterministic extraction used when no LLM key is configured.

    It only returns sentences and values that appear in the document.
    """
    document_text = CITATION_PREFIX_RE.sub("", document_text)
    chunks = chunk_markdown(document_text, document_id="extract")
    clauses = [chunk for chunk in chunks if chunk.chunk_type == "clause"] or chunks

    values: dict[str, list[str]] = {field: [] for field in FIELD_KEYWORDS}
    citations: dict[str, str] = {}

    for field, keywords in FIELD_KEYWORDS.items():
        seen: set[str] = set()
        for chunk in clauses:
            text = _snippet(chunk.text)
            lowered = text.lower()
            if not text or not any(keyword in lowered for keyword in keywords):
                continue
            if text in seen:
                continue
            seen.add(text)
            values[field].append(text)
            citations[f"{field}[{len(values[field]) - 1}]"] = chunk.citation
            if len(values[field]) >= MAX_RULES_PER_FIELD:
                break

    lines = document_text.splitlines()
    policy_name = _find_policy_name(lines)
    authority = _find_authority(document_text)
    gazette = GAZETTE_RE.search(document_text)
    date = DATE_RE.search(document_text)

    for field, needle in (
        ("policy_name", policy_name),
        ("issuing_authority", authority),
        ("gazette_or_order_no", gazette.group(0) if gazette else None),
        ("effective_date", date.group(0) if date else None),
    ):
        if not needle:
            continue
        normalized_needle = re.sub(r"\s+", " ", needle.lower())
        for chunk in chunks:
            normalized_text = re.sub(r"\s+", " ", chunk.text.lower())
            if normalized_needle in normalized_text:
                citations[field] = chunk.citation
                break
        else:
            if field == "policy_name" and chunks:
                citations[field] = chunks[0].citation

    return PolicyExtraction(
        policy_name=policy_name,
        issuing_authority=authority,
        gazette_or_order_no=gazette.group(0) if gazette else None,
        effective_date=date.group(0) if date else None,
        target_beneficiaries=values["target_beneficiaries"],
        mandatory_eligibility=values["mandatory_eligibility"],
        disqualifications=values["disqualifications"],
        direct_benefits=values["direct_benefits"],
        penalty_or_deadlines=values["penalty_or_deadlines"],
        required_documents=values["required_documents"],
        citation_source_map=citations,
    )


class MockExtractionProvider:
    def extract(
        self,
        *,
        document_text: str,
        target_language: str,
        correction_guidance: str | None = None,
    ) -> PolicyExtraction:
        return heuristic_extract(document_text)


class AnthropicExtractionProvider:
    def __init__(self, api_key: str, model: str = ANTHROPIC_DEFAULT_MODEL) -> None:
        self.api_key = api_key
        self.model = model

    def extract(
        self,
        *,
        document_text: str,
        target_language: str,
        correction_guidance: str | None = None,
    ) -> PolicyExtraction:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": build_user_prompt(
                        document_text, target_language, correction_guidance
                    ),
                }
            ],
            tools=[
                {
                    "name": "policy_extraction",
                    "description": "Return the grounded PolicyExtraction object.",
                    "input_schema": PolicyExtraction.model_json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": "policy_extraction"},
        )

        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                return normalize_citations(PolicyExtraction.model_validate(block.input))

        raise ExtractionError("Anthropic response did not include structured output")


class OpenAIExtractionProvider:
    def __init__(self, api_key: str, model: str = OPENAI_DEFAULT_MODEL) -> None:
        self.api_key = api_key
        self.model = model

    def extract(
        self,
        *,
        document_text: str,
        target_language: str,
        correction_guidance: str | None = None,
    ) -> PolicyExtraction:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        parse = getattr(client.chat.completions, "parse", None)
        if parse is None:
            parse = client.beta.chat.completions.parse

        completion = parse(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_user_prompt(
                        document_text, target_language, correction_guidance
                    ),
                },
            ],
            response_format=PolicyExtraction,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise ExtractionError("OpenAI response did not include structured output")
        return normalize_citations(parsed)


def normalize_citations(extraction: PolicyExtraction) -> PolicyExtraction:
    """Normalize extracted citations to canonical field and field[index] keys."""
    raw = dict(extraction.citation_source_map)
    normalized: dict[str, str] = {}

    for field in SCALAR_FIELDS:
        val = getattr(extraction, field, None)
        if not val or val.lower() in ("not stated in document", "untitled policy"):
            continue
        if field in raw:
            normalized[field] = raw[field]
        elif val in raw:
            normalized[field] = raw[val]
        else:
            for k, v in raw.items():
                if k.lower() in field.lower() or field.lower() in k.lower():
                    normalized[field] = v
                    break

    for field in LIST_FIELDS:
        items = getattr(extraction, field, []) or []
        for i, item in enumerate(items):
            canonical = f"{field}[{i}]"
            if canonical in raw:
                normalized[canonical] = raw[canonical]
                continue
            candidates = [
                f"{field}[{i + 1}]",
                f"{field}.{i}",
                f"{field}.{i + 1}",
                f"{field}_{i}",
                f"{field}_{i + 1}",
                f"{field}-{i}",
                f"{field}-{i + 1}",
            ]
            matched = False
            for c in candidates:
                if c in raw:
                    normalized[canonical] = raw[c]
                    matched = True
                    break
            if matched:
                continue
            if field in raw:
                normalized[canonical] = raw[field]
                continue
            if item in raw:
                normalized[canonical] = raw[item]
                continue
            for k, v in raw.items():
                if (k.lower() in item.lower() or item.lower() in k.lower()) and len(k) > 4:
                    normalized[canonical] = v
                    break

    for k, v in raw.items():
        if k not in normalized:
            normalized[k] = v

    return extraction.model_copy(update={"citation_source_map": normalized})


class GroqExtractionProvider:
    def __init__(self, api_key: str, model: str = GROQ_DEFAULT_EXTRACTION_MODEL) -> None:
        self.api_key = api_key
        self.model = model

    def extract(
        self,
        *,
        document_text: str,
        target_language: str,
        correction_guidance: str | None = None,
    ) -> PolicyExtraction:
        from groq import Groq, NotFoundError

        client = Groq(api_key=self.api_key)
        models_to_try = [self.model]
        for fallback in GROQ_FALLBACK_MODELS:
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "policy_extraction",
                    "description": "Return the grounded PolicyExtraction object.",
                    "parameters": PolicyExtraction.model_json_schema(),
                },
            }
        ]

        last_error: Exception | None = None
        for model in models_to_try:
            try:
                extra_kwargs = {}
                if "gpt-oss" in model:
                    extra_kwargs["reasoning_format"] = "hidden"

                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": build_user_prompt(
                                document_text, target_language, correction_guidance
                            ),
                        },
                    ],
                    tools=tools,
                    tool_choice={"type": "function", "function": {"name": "policy_extraction"}},
                    max_tokens=4096,
                    **extra_kwargs,
                )

                choice = response.choices[0].message
                if choice.tool_calls:
                    arguments = choice.tool_calls[0].function.arguments
                    extraction = PolicyExtraction.model_validate_json(arguments)
                    return normalize_citations(extraction)

                if choice.content:
                    extraction = PolicyExtraction.model_validate_json(choice.content)
                    return normalize_citations(extraction)

                raise ExtractionError("Groq response did not include structured output")
            except NotFoundError as exc:
                logger.warning("Groq model %s not available, attempting fallback: %s", model, exc)
                last_error = exc
                continue
            except Exception as exc:
                if isinstance(exc, ExtractionError):
                    raise
                raise ExtractionError(f"Groq extraction failed: {exc}") from exc

        raise ExtractionError(f"Groq extraction failed across models: {last_error}")


def get_extraction_provider(settings: Settings | None = None) -> ExtractionProvider:
    settings = settings or get_settings()
    choice = settings.extraction_provider.lower()

    if settings.use_mock_llm or choice == "mock":
        return MockExtractionProvider()

    if choice == "anthropic" or (choice == "auto" and settings.anthropic_api_key):
        if not settings.anthropic_api_key:
            raise ExtractionError("EXTRACTION_PROVIDER=anthropic requires ANTHROPIC_API_KEY")
        return AnthropicExtractionProvider(
            api_key=settings.anthropic_api_key,
            model=settings.extraction_model or ANTHROPIC_DEFAULT_MODEL,
        )

    if choice == "openai" or (choice == "auto" and settings.openai_api_key):
        if not settings.openai_api_key:
            raise ExtractionError("EXTRACTION_PROVIDER=openai requires OPENAI_API_KEY")
        return OpenAIExtractionProvider(
            api_key=settings.openai_api_key,
            model=settings.extraction_model or OPENAI_DEFAULT_MODEL,
        )

    if choice == "groq" or (choice == "auto" and settings.groq_api_key):
        if not settings.groq_api_key:
            raise ExtractionError("EXTRACTION_PROVIDER=groq requires GROQ_API_KEY")
        return GroqExtractionProvider(
            api_key=settings.groq_api_key,
            model=settings.extraction_model or GROQ_DEFAULT_EXTRACTION_MODEL,
        )

    if choice != "auto":
        raise ExtractionError(
            f"Unknown extraction provider '{settings.extraction_provider}'. "
            "Supported providers: auto, anthropic, openai, groq, mock."
        )

    return MockExtractionProvider()
