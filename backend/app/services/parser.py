"""PDF ingestion and layout-aware parsing.

Docling is the primary parser (dual-column gazettes, tables). When it is
disabled or fails, the module falls back to pypdf text extraction so local
development and tests do not require the full Docling model stack.
"""

from __future__ import annotations

import asyncio
import io
import logging
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

MAX_PDF_BYTES = 25 * 1024 * 1024
PDF_MAGIC = b"%PDF-"
# Several government hosts reject non-browser user agents with HTTP 403.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 Niti/0.1"
)


class IngestionError(RuntimeError):
    """A document could not be fetched or parsed."""


class UnsupportedDocumentError(IngestionError):
    """The fetched resource is not a supported PDF document."""


@dataclass(frozen=True)
class ParsedDocument:
    source_url: str
    markdown: str
    page_count: int
    parser: str
    fetched_at: datetime
    markdown_path: Path | None = None


def validate_document_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise IngestionError("document_url must be a valid http(s) URL")
    return url


async def fetch_pdf(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float = 30.0,
    max_bytes: int = MAX_PDF_BYTES,
) -> bytes:
    """Download a PDF with size limits and content sniffing."""
    validate_document_url(url)

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/pdf,*/*",
                "Accept-Language": "en-IN,en;q=0.9",
            },
        )

    try:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise IngestionError(
                        f"PDF exceeds the {max_bytes // (1024 * 1024)} MB size limit"
                    )
                chunks.append(chunk)
    except httpx.HTTPError as exc:
        raise IngestionError(f"Failed to fetch document: {exc}") from exc
    finally:
        if owns_client:
            await client.aclose()

    data = b"".join(chunks)
    if PDF_MAGIC not in data[:1024]:
        content_type = response.headers.get("content-type", "unknown")
        raise UnsupportedDocumentError(f"Expected a PDF, got content-type {content_type!r}")
    return data


def parse_with_pypdf(data: bytes) -> tuple[str, int]:
    """Fast text-only fallback. Keeps page markers for citations."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages: list[str] = []
    for number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        pages.append(f"<!-- page {number} -->\n{text}")
    return "\n\n".join(pages).strip(), len(reader.pages)


def parse_with_docling(data: bytes) -> tuple[str, int]:
    """Layout-aware parse preserving tables and multi-column reading order."""
    from docling.document_converter import DocumentConverter

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
        handle.write(data)
        temp_path = Path(handle.name)

    try:
        result = DocumentConverter().convert(temp_path)
        markdown = result.document.export_to_markdown()
        page_count = len(getattr(result.document, "pages", {}) or {})
    finally:
        temp_path.unlink(missing_ok=True)

    if not markdown.strip():
        raise IngestionError("Docling returned empty markdown")
    return markdown, page_count


def parse_pdf_bytes(data: bytes, *, use_docling: bool) -> tuple[str, int, str]:
    """Parse PDF bytes, falling back to pypdf when Docling is unavailable."""
    if use_docling:
        try:
            markdown, page_count = parse_with_docling(data)
            return markdown, page_count, "docling"
        except Exception:
            logger.exception("Docling parsing failed; falling back to pypdf")

    markdown, page_count = parse_with_pypdf(data)
    return markdown, page_count, "pypdf"


def persist_markdown(
    task_id: str,
    parsed: ParsedDocument,
    *,
    data_dir: str | Path = "data",
) -> Path:
    destination_dir = Path(data_dir) / "parsed"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{task_id}.md"
    header = (
        f"<!-- source: {parsed.source_url} -->\n"
        f"<!-- parser: {parsed.parser} -->\n"
        f"<!-- pages: {parsed.page_count} -->\n\n"
    )
    destination.write_text(header + parsed.markdown, encoding="utf-8")
    return destination


async def parse_document(
    document_url: str,
    *,
    task_id: str,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
) -> ParsedDocument:
    """Fetch and parse a PDF, persisting markdown for downstream phases."""
    settings = settings or get_settings()
    data = await fetch_pdf(document_url, client=client)
    markdown, page_count, parser = await asyncio.to_thread(
        parse_pdf_bytes, data, use_docling=settings.use_docling
    )

    parsed = ParsedDocument(
        source_url=document_url,
        markdown=markdown,
        page_count=page_count,
        parser=parser,
        fetched_at=datetime.now(UTC),
    )
    path = await asyncio.to_thread(persist_markdown, task_id, parsed, data_dir=settings.data_dir)
    return ParsedDocument(
        source_url=parsed.source_url,
        markdown=parsed.markdown,
        page_count=parsed.page_count,
        parser=parsed.parser,
        fetched_at=parsed.fetched_at,
        markdown_path=path,
    )
