"""PDF ingestion and layout-aware parsing.

Docling is the primary parser (dual-column gazettes, tables). When it is
disabled or fails, the module falls back to pypdf text extraction so local
development and tests do not require the full Docling model stack.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
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


class _TransientFetchError(IngestionError):
    """A retryable network or upstream failure."""


RETRYABLE_STATUS = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class ParsedDocument:
    source_url: str
    markdown: str
    page_count: int
    parser: str
    fetched_at: datetime
    markdown_path: Path | None = None
    from_cache: bool = False


def validate_document_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise IngestionError("document_url must be a valid http(s) URL")
    return url


async def _download_pdf(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_bytes: int,
) -> tuple[bytes, str]:
    try:
        async with client.stream("GET", url) as response:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in RETRYABLE_STATUS:
                    raise _TransientFetchError(f"upstream returned HTTP {status}") from exc
                raise IngestionError(f"Failed to fetch document: {exc}") from exc

            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise IngestionError(
                        f"PDF exceeds the {max_bytes // (1024 * 1024)} MB size limit"
                    )
                chunks.append(chunk)
            return b"".join(chunks), response.headers.get("content-type", "unknown")
    except httpx.RequestError as exc:
        raise _TransientFetchError(f"network error: {exc}") from exc


async def fetch_pdf(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float = 30.0,
    max_bytes: int = MAX_PDF_BYTES,
    retries: int = 2,
    backoff_sec: float = 0.75,
) -> bytes:
    """Download a PDF with retries, size limits, and content sniffing.

    Only transient failures (network errors, 429, and 5xx) are retried; a 404 or
    an HTML login wall fails immediately so the caller can fall back to cache.
    """
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

    last_error: _TransientFetchError | None = None
    try:
        for attempt in range(retries + 1):
            try:
                data, content_type = await _download_pdf(client, url, max_bytes=max_bytes)
            except _TransientFetchError as exc:
                last_error = exc
                if attempt < retries:
                    logger.warning(
                        "Fetch attempt %d/%d for %s failed (%s); retrying",
                        attempt + 1,
                        retries + 1,
                        url,
                        exc,
                    )
                    await asyncio.sleep(backoff_sec * (2**attempt))
                    continue
                break

            if PDF_MAGIC not in data[:1024]:
                raise UnsupportedDocumentError(f"Expected a PDF, got content-type {content_type!r}")
            return data
    finally:
        if owns_client:
            await client.aclose()

    raise IngestionError(
        f"Failed to fetch document after {retries + 1} attempts: {last_error}"
    ) from last_error


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


def cache_key(document_url: str) -> str:
    return hashlib.sha256(document_url.strip().encode("utf-8")).hexdigest()[:32]


def cache_path(document_url: str, *, data_dir: str | Path = "data") -> Path:
    return Path(data_dir) / "cache" / f"{cache_key(document_url)}.json"


def write_document_cache(
    parsed: ParsedDocument,
    *,
    data_dir: str | Path = "data",
) -> Path:
    """Store the parsed result so an unreachable source can still be explained."""
    destination = cache_path(parsed.source_url, data_dir=data_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_url": parsed.source_url,
        "markdown": parsed.markdown,
        "page_count": parsed.page_count,
        "parser": parsed.parser,
        "fetched_at": parsed.fetched_at.isoformat(),
    }
    destination.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return destination


def read_document_cache(
    document_url: str,
    *,
    data_dir: str | Path = "data",
) -> ParsedDocument | None:
    source = cache_path(document_url, data_dir=data_dir)
    if not source.exists():
        return None
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        return ParsedDocument(
            source_url=payload["source_url"],
            markdown=payload["markdown"],
            page_count=int(payload["page_count"]),
            parser=str(payload["parser"]),
            fetched_at=datetime.fromisoformat(payload["fetched_at"]),
            from_cache=True,
        )
    except (OSError, ValueError, KeyError, TypeError):
        logger.warning("Ignoring unreadable document cache at %s", source)
        return None


def _with_markdown_path(
    parsed: ParsedDocument, *, task_id: str, data_dir: str | Path
) -> ParsedDocument:
    path = persist_markdown(task_id, parsed, data_dir=data_dir)
    return ParsedDocument(
        source_url=parsed.source_url,
        markdown=parsed.markdown,
        page_count=parsed.page_count,
        parser=parsed.parser,
        fetched_at=parsed.fetched_at,
        markdown_path=path,
        from_cache=parsed.from_cache,
    )


async def parse_document(
    document_url: str,
    *,
    task_id: str,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
) -> ParsedDocument:
    """Fetch and parse a PDF, falling back to a cached copy when needed."""
    settings = settings or get_settings()

    if settings.offline_mode:
        cached = read_document_cache(document_url, data_dir=settings.data_dir)
        if cached is None:
            raise IngestionError("Offline mode is on and this document has no cache entry yet")
        logger.info("Serving %s from cache (offline mode)", document_url)
        return await asyncio.to_thread(
            _with_markdown_path, cached, task_id=task_id, data_dir=settings.data_dir
        )

    try:
        data = await fetch_pdf(document_url, client=client)
    except IngestionError as exc:
        cached = read_document_cache(document_url, data_dir=settings.data_dir)
        if cached is None:
            raise
        logger.warning("Live fetch failed (%s); serving cached copy of %s", exc, document_url)
        return await asyncio.to_thread(
            _with_markdown_path, cached, task_id=task_id, data_dir=settings.data_dir
        )

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
    await asyncio.to_thread(write_document_cache, parsed, data_dir=settings.data_dir)
    return await asyncio.to_thread(
        _with_markdown_path, parsed, task_id=task_id, data_dir=settings.data_dir
    )
