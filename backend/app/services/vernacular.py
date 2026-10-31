"""Vernacular script generation providers."""

from __future__ import annotations

import json
import logging
from typing import Protocol

from app.core.config import Settings, get_settings
from app.prompts.vernacular import SYSTEM_PROMPT, build_user_prompt
from app.schemas import PolicyExtraction

logger = logging.getLogger(__name__)

GROQ_DEFAULT_MODEL = "openai/gpt-oss-120b"
GROQ_FALLBACK_MODELS = ("openai/gpt-oss-120b", "qwen/qwen3.8-27b", "llama-3.3-70b-versatile")

TEMPLATES: dict[str, dict[str, str]] = {
    "hi-IN": {
        "greeting": "नमस्ते।",
        "intro": "यह जानकारी {policy_name} के बारे में है, जिसे {authority} ने जारी किया है।",
        "benefits": "इसका सीधा लाभ: {benefits}",
        "eligibility": "पात्रता के लिए: {eligibility}",
        "documents": "ज़रूरी कागज़ात: {documents}",
        "deadline": "आखिरी तारीख और अगला कदम: {deadline}",
        "action": "अपने नज़दीकी सरकारी कार्यालय या ऑनलाइन पोर्टल पर जानकारी जाँचें।",
        "fallback": "इस दस्तावेज़ में यह जानकारी नहीं दी गई है।",
    },
    "ta-IN": {
        "greeting": "வணக்கம்.",
        "intro": "இந்தத் தகவல் {policy_name} பற்றியது; இதை {authority} வெளியிட்டது.",
        "benefits": "நேரடி பயன்: {benefits}",
        "eligibility": "தகுதி: {eligibility}",
        "documents": "தேவையான ஆவணங்கள்: {documents}",
        "deadline": "கடைசி தேதி மற்றும் அடுத்த படி: {deadline}",
        "action": "அருகிலுள்ள அரசு அலுவலகம் அல்லது ஆன்லைன் போர்ட்டலில் சரிபார்க்கவும்.",
        "fallback": "இந்த ஆவணத்தில் இந்தத் தகவல் இல்லை.",
    },
    "bn-IN": {
        "greeting": "নমস্কার।",
        "intro": "এই তথ্যটি {policy_name} সম্পর্কে, যা {authority} জারি করেছে।",
        "benefits": "সরাসরি সুবিধা: {benefits}",
        "eligibility": "যোগ্যতা: {eligibility}",
        "documents": "প্রয়োজনীয় নথি: {documents}",
        "deadline": "শেষ তারিখ এবং পরবর্তী পদক্ষেপ: {deadline}",
        "action": "নিকটস্থ সরকারি অফিস বা অনলাইন পোর্টালে যাচাই করুন।",
        "fallback": "এই নথিতে এই তথ্য দেওয়া নেই।",
    },
    "te-IN": {
        "greeting": "నమస్కారం.",
        "intro": "ఈ సమాచారం {policy_name} గురించి; దీనిని {authority} జారీ చేసింది.",
        "benefits": "నేరుగా ప్రయోజనం: {benefits}",
        "eligibility": "అర్హత: {eligibility}",
        "documents": "అవసరమైన పత్రాలు: {documents}",
        "deadline": "చివరి తేదీ మరియు తదుపరి చర్య: {deadline}",
        "action": "సమీప ప్రభుత్వ కార్యాలయం లేదా ఆన్‌లైన్ పోర్టల్‌లో నిర్ధారించుకోండి.",
        "fallback": "ఈ పత్రంలో ఈ సమాచారం లేదు.",
    },
    "en-IN": {
        "greeting": "Hello.",
        "intro": "This is about {policy_name}, issued by {authority}.",
        "benefits": "The direct benefit is: {benefits}",
        "eligibility": "To qualify: {eligibility}",
        "documents": "Documents you need: {documents}",
        "deadline": "The deadline and next step: {deadline}",
        "action": "Check your nearest government office or the online portal.",
        "fallback": "This is not stated in the document.",
    },
}


class SimplificationError(RuntimeError):
    """The script could not be generated."""


class SimplificationProvider(Protocol):
    def simplify(self, policy: PolicyExtraction, language_code: str) -> str: ...


def _join(items: list[str], fallback: str) -> str:
    if not items:
        return fallback
    return "; ".join(item.rstrip(".") for item in items[:4]) + "."


class MockSimplificationProvider:
    """Localized template script built only from extracted facts."""

    def simplify(self, policy: PolicyExtraction, language_code: str) -> str:
        template = TEMPLATES.get(language_code, TEMPLATES["en-IN"])
        fallback = template["fallback"]
        policy_name = policy.policy_name or fallback
        authority = (
            policy.issuing_authority
            if policy.issuing_authority
            and policy.issuing_authority.lower() != "not stated in document"
            else fallback
        )

        parts = [
            template["greeting"],
            template["intro"].format(policy_name=policy_name, authority=authority),
            template["benefits"].format(benefits=_join(policy.direct_benefits, fallback)),
            template["eligibility"].format(
                eligibility=_join(
                    [*policy.target_beneficiaries, *policy.mandatory_eligibility],
                    fallback,
                )
            ),
            template["documents"].format(documents=_join(policy.required_documents, fallback)),
            template["deadline"].format(deadline=_join(policy.penalty_or_deadlines, fallback)),
            template["action"],
        ]
        return " ".join(parts)


class GroqSimplificationProvider:
    def __init__(self, api_key: str, model: str = GROQ_DEFAULT_MODEL) -> None:
        self.api_key = api_key
        self.model = model

    def simplify(self, policy: PolicyExtraction, language_code: str) -> str:
        from groq import Groq, NotFoundError

        client = Groq(api_key=self.api_key)
        models_to_try = [self.model]
        for fallback in GROQ_FALLBACK_MODELS:
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        last_error: Exception | None = None
        for model in models_to_try:
            try:
                extra_kwargs = {}
                if "gpt-oss" in model:
                    extra_kwargs["reasoning_format"] = "hidden"

                response = client.chat.completions.create(
                    model=model,
                    temperature=0.3,
                    max_tokens=900,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": build_user_prompt(
                                json.dumps(policy.model_dump(), ensure_ascii=False),
                                language_code,
                            ),
                        },
                    ],
                    **extra_kwargs,
                )
                content = response.choices[0].message.content
                if not content or not content.strip():
                    raise SimplificationError("Groq returned an empty script")
                return content.strip()
            except NotFoundError as exc:
                logger.warning("Groq model %s not available, attempting fallback: %s", model, exc)
                last_error = exc
                continue
            except Exception as exc:
                if isinstance(exc, SimplificationError):
                    raise
                raise SimplificationError(f"Groq simplification failed: {exc}") from exc

        raise SimplificationError(f"Groq simplification failed across models: {last_error}")


def get_simplification_provider(
    settings: Settings | None = None,
) -> SimplificationProvider:
    settings = settings or get_settings()
    if settings.use_mock_llm or not settings.groq_api_key:
        return MockSimplificationProvider()
    return GroqSimplificationProvider(
        api_key=settings.groq_api_key,
        model=settings.simplification_model or GROQ_DEFAULT_MODEL,
    )
