"""Pydantic data contracts shared across the API and agent pipeline."""

from enum import StrEnum
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

LanguageCode = Literal["hi-IN", "ta-IN", "bn-IN", "te-IN", "en-IN"]


class PolicyExtraction(BaseModel):
    """Structured citizen-rights data extracted from a policy document."""

    policy_name: str = Field(description="Official name of the policy, bill, or scheme")
    issuing_authority: str = Field(description="Ministry, Department, or Municipal body")
    gazette_or_order_no: str | None = Field(
        default=None, description="Official circular or notification reference number"
    )
    effective_date: str | None = Field(
        default=None, description="Date from which the notification takes effect"
    )
    target_beneficiaries: list[str] = Field(description="Demographics eligible for the policy")
    mandatory_eligibility: list[str] = Field(
        description="Specific positive qualification requirements"
    )
    disqualifications: list[str] = Field(
        description="Exclusions or negative disqualification criteria"
    )
    direct_benefits: list[str] = Field(
        description="Subsidies, credit limits, rights granted, or fee waivers"
    )
    penalty_or_deadlines: list[str] = Field(
        description="Compliance deadlines, late fees, or legal obligations"
    )
    required_documents: list[str] = Field(description="Official KYC or supporting documents needed")
    citation_source_map: dict[str, str] = Field(
        description="Mapping of each rule to exact page and clause number"
    )


class AuditResult(BaseModel):
    """Grounding verdict produced by the hallucination audit node."""

    is_grounded: bool
    unsupported_claims: list[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
    correction_guidance: str | None = None


class VoicePayload(BaseModel):
    """Localized script and optional synthesized audio."""

    language_code: LanguageCode = Field(description="Target Indian language locale")
    plain_text_script: str = Field(description="Conversational 60-second script in target script")
    audio_base64: str | None = None
    duration_estimate_sec: int = Field(ge=0)


class TaskStatus(StrEnum):
    processing = "processing"
    completed = "completed"
    failed = "failed"


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "document_url": "https://egazette.gov.in/sample.pdf",
                    "target_language": "hi-IN",
                }
            ]
        }
    )

    document_url: str = Field(description="Public URL of a government PDF circular or gazette")
    target_language: LanguageCode = Field(
        default="hi-IN", description="Target language for the voice explainer"
    )

    @field_validator("document_url")
    @classmethod
    def validate_document_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("document_url must be a valid http(s) URL")
        return value


class AnalyzeResponse(BaseModel):
    status: Literal["processing"]
    task_id: str


class AnalysisResult(BaseModel):
    policy_data: PolicyExtraction
    audit_status: AuditResult
    voice_payload: VoicePayload | None = None
    audio_url: str | None = None
    audio_is_mock: bool = Field(
        default=False,
        description="True when local placeholder audio was produced instead of a real TTS call",
    )
    from_cache: bool = Field(
        default=False,
        description="True when the source was unreachable and a cached parse was used",
    )


class ResultResponse(BaseModel):
    task_id: str
    status: TaskStatus
    result: AnalysisResult | None = None
    error: str | None = None


class CitizenProfile(BaseModel):
    income: int = Field(ge=0, description="Annual household income in INR")
    occupation: str = Field(description="Occupation, e.g. street_vendor")
    state: str = Field(description="Indian state or union territory")
    documents: list[str] = Field(
        default_factory=list,
        description="Documents the citizen already holds, e.g. ['Aadhaar Card']",
    )


class VerifyCitizenRequest(BaseModel):
    policy_id: str
    citizen_profile: CitizenProfile


class VerifyCitizenResponse(BaseModel):
    is_eligible: bool
    matched_clauses: list[str]
    missing_documents: list[str]


class SourceItem(BaseModel):
    """One normalized item from a live government feed."""

    source: Literal["myscheme", "pib"]
    title: str
    url: str
    summary: str | None = None
    published_at: str | None = None


class SourcesResponse(BaseModel):
    query: str = ""
    items: list[SourceItem] = Field(default_factory=list)
    errors: list[str] = Field(
        default_factory=list, description="Per-source failures; other sources still returned"
    )
