"""Shared LangGraph state for the Niti analysis pipeline."""

from typing import TypedDict


class AgentState(TypedDict, total=False):
    task_id: str
    raw_document_url: str
    target_language: str

    # Ingestion
    parsed_markdown: str
    parser: str
    page_count: int
    markdown_path: str | None
    from_cache: bool

    # Extraction + audit
    retrieved_context: list[str]
    extracted_data: dict
    audit_report: dict
    audit_retry_count: int

    # Localization + voice
    simplified_script: str
    voice_payload: dict
    audio_output_url: str
