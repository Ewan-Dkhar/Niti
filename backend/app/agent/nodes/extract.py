"""Rule extraction node: retrieve grounded context and call the LLM."""

import logging

from app.agent.state import AgentState
from app.services.chunker import Chunk, chunk_markdown
from app.services.llm import get_extraction_provider

logger = logging.getLogger(__name__)

CONTEXT_KEYWORDS: tuple[str, ...] = (
    "eligible",
    "eligibility",
    "benefit",
    "subsidy",
    "income",
    "document",
    "aadhaar",
    "deadline",
    "penalty",
    "certificate",
    "subsidy",
    "credit",
    "rupees",
    "scheme",
)

MAX_CONTEXT_CHARS = 18_000
MAX_CONTEXT_CHUNKS = 24


def select_context(
    markdown: str,
    *,
    document_id: str,
    max_chars: int = MAX_CONTEXT_CHARS,
    max_chunks: int = MAX_CONTEXT_CHUNKS,
) -> list[Chunk]:
    """Pick the chunks most likely to contain extractable rules."""
    chunks = chunk_markdown(markdown, document_id=document_id)

    def relevance(chunk: Chunk) -> int:
        lowered = chunk.text.lower()
        score = sum(1 for keyword in CONTEXT_KEYWORDS if keyword in lowered)
        if chunk.chunk_type == "section":
            score += 2
        if chunk.section_index == 0:
            score += 1
        return score

    ranked = sorted(
        chunks,
        key=lambda chunk: (
            -relevance(chunk),
            chunk.section_index,
            chunk.clause_index or 0,
        ),
    )

    selected: list[Chunk] = []
    total_chars = 0
    for chunk in ranked:
        if len(selected) >= max_chunks:
            break
        if total_chars + len(chunk.text) > max_chars:
            continue
        selected.append(chunk)
        total_chars += len(chunk.text)

    selected.sort(key=lambda chunk: (chunk.section_index, chunk.clause_index or 0))
    return selected


def extract_rules_node(state: AgentState) -> dict:
    markdown = state.get("parsed_markdown", "").strip()
    if not markdown:
        raise ValueError("extract_rules_node requires parsed_markdown")

    context = select_context(markdown, document_id=state.get("task_id", "document"))
    context_text = "\n\n".join(f"[{chunk.citation}] {chunk.text}" for chunk in context)

    provider = get_extraction_provider()
    extraction = provider.extract(
        document_text=context_text,
        target_language=state.get("target_language", "hi-IN"),
    )

    logger.info(
        "Extracted policy '%s' from %d context chunks",
        extraction.policy_name,
        len(context),
    )

    return {
        "retrieved_context": [f"[{chunk.citation}] {chunk.text}" for chunk in context],
        "extracted_data": extraction.model_dump(),
    }
