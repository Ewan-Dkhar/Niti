"""Hierarchical chunking of parsed policy markdown.

Each document becomes one parent chunk per section plus child chunks per
clause. Children keep the parent id and page number so downstream extraction
can cite "section + clause + page" without re-reading the PDF.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

ChunkType = Literal["section", "clause"]

PAGE_MARKER_RE = re.compile(r"<!--\s*page\s+(\d+)\s*-->", re.IGNORECASE)
MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+([A-Z][^.!?]{3,120})$")
CLAUSE_START_RE = re.compile(r"(?m)^\s*(?:\d+(?:\.\d+)*[.)]?|\([a-zA-Z0-9]+\)|[a-zA-Z]\.)\s+")
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?।])\s+")

DEFAULT_MAX_CHARS = 1200
DEFAULT_MIN_CHARS = 20
DEFAULT_MAX_SECTION_CHARS = 6000


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    text: str
    chunk_type: ChunkType
    section_title: str
    section_index: int
    clause_index: int | None
    page: int
    parent_id: str | None
    citation: str

    @property
    def embed_text(self) -> str:
        """Text sent to the embedding model, with section context."""
        if self.chunk_type == "section":
            return self.text
        return f"{self.section_title}\n\n{self.text}"

    def payload(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "text": self.text,
            "chunk_type": self.chunk_type,
            "section_title": self.section_title,
            "section_index": self.section_index,
            "clause_index": self.clause_index,
            "page": self.page,
            "parent_id": self.parent_id,
            "citation": self.citation,
        }


@dataclass
class _Section:
    title: str
    page: int
    body_lines: list[str]


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _split_long_text(text: str, max_chars: int) -> list[str]:
    """Pack sentences into pieces no longer than ``max_chars``."""
    if len(text) <= max_chars:
        return [text]

    sentences = [part.strip() for part in SENTENCE_BOUNDARY_RE.split(text) if part.strip()]
    if not sentences:
        return [text[:max_chars]]

    pieces: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        if current and current_len + len(sentence) + 1 > max_chars:
            pieces.append(" ".join(current))
            current = []
            current_len = 0

        if len(sentence) > max_chars:
            if current:
                pieces.append(" ".join(current))
                current = []
                current_len = 0
            pieces.extend(
                sentence[start : start + max_chars] for start in range(0, len(sentence), max_chars)
            )
            continue

        current.append(sentence)
        current_len += len(sentence) + 1

    if current:
        pieces.append(" ".join(current))

    return pieces


def _is_markdown_table(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    return len(lines) >= 2 and all(line.lstrip().startswith("|") for line in lines)


def _split_table(paragraph: str, max_chars: int) -> list[str]:
    """Keep table headers attached to row groups instead of splitting blindly."""
    if len(paragraph) <= max_chars:
        return [paragraph]

    lines = [line for line in paragraph.splitlines() if line.strip()]
    if len(lines) < 3:
        return [paragraph]

    header, separator = lines[0], lines[1]
    rows = lines[2:]
    base = f"{header}\n{separator}"
    pieces: list[str] = []
    current = [base]
    current_len = len(base)

    for row in rows:
        if len(current) > 1 and current_len + len(row) + 1 > max_chars:
            pieces.append("\n".join(current))
            current = [base]
            current_len = len(base)
        current.append(row)
        current_len += len(row) + 1

    if len(current) > 1:
        pieces.append("\n".join(current))

    return pieces or [paragraph]


def _split_units(body: str, max_chars: int) -> list[str]:
    """Split section body into clause-sized units."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]

    units: list[str] = []
    for paragraph in paragraphs:
        if _is_markdown_table(paragraph):
            units.extend(_split_table(paragraph, max_chars))
            continue

        starts = [match.start() for match in CLAUSE_START_RE.finditer(paragraph)]
        if len(starts) > 1:
            pieces = [
                paragraph[start:end].strip()
                for start, end in zip(starts, [*starts[1:], len(paragraph)], strict=False)
                if paragraph[start:end].strip()
            ]
        else:
            pieces = [paragraph]

        for piece in pieces:
            units.extend(_split_long_text(piece, max_chars))

    return units


def _parse_sections(markdown: str) -> list[_Section]:
    sections: list[_Section] = []
    current = _Section(title="Preamble", page=1, body_lines=[])
    page = 1

    for raw_line in markdown.splitlines():
        marker = PAGE_MARKER_RE.search(raw_line)
        if marker:
            page = int(marker.group(1))
            continue

        line = raw_line.rstrip()
        heading = MARKDOWN_HEADING_RE.match(line)
        if not heading:
            numbered = NUMBERED_HEADING_RE.match(line.strip())
            heading_title = numbered.group(0).strip() if numbered else None
        else:
            heading_title = heading.group(2).strip()

        if heading_title:
            if current.body_lines or current.title != "Preamble":
                sections.append(current)
            current = _Section(title=heading_title, page=page, body_lines=[])
            continue

        if line.strip():
            current.body_lines.append(line)

    if current.body_lines or current.title != "Preamble":
        sections.append(current)

    return sections


def chunk_markdown(
    markdown: str,
    *,
    document_id: str = "doc",
    max_chars: int = DEFAULT_MAX_CHARS,
    min_chars: int = DEFAULT_MIN_CHARS,
    max_section_chars: int = DEFAULT_MAX_SECTION_CHARS,
) -> list[Chunk]:
    """Return section parents followed by their clause children."""
    chunks: list[Chunk] = []

    for section_index, section in enumerate(_parse_sections(markdown)):
        section_id = f"{document_id}:s{section_index}"
        section_body = "\n".join(section.body_lines).strip()
        section_text = _truncate(
            f"{section.title}\n\n{section_body}" if section_body else section.title,
            max_section_chars,
        )

        chunks.append(
            Chunk(
                chunk_id=section_id,
                document_id=document_id,
                text=section_text,
                chunk_type="section",
                section_title=section.title,
                section_index=section_index,
                clause_index=None,
                page=section.page,
                parent_id=None,
                citation=f"{section.title} (page {section.page})",
            )
        )

        units = _split_units(section_body, max_chars)
        clause_index = 0
        for unit in units:
            if len(unit) < min_chars:
                continue
            clause_id = f"{section_id}:c{clause_index}"
            chunks.append(
                Chunk(
                    chunk_id=clause_id,
                    document_id=document_id,
                    text=unit,
                    chunk_type="clause",
                    section_title=section.title,
                    section_index=section_index,
                    clause_index=clause_index,
                    page=section.page,
                    parent_id=section_id,
                    citation=f"{section.title}, clause {clause_index + 1} (page {section.page})",
                )
            )
            clause_index += 1

    return chunks
