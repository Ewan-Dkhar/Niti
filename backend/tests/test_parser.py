"""Tests for PDF ingestion, parsing, and persistence."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fpdf import FPDF

from app.core.config import Settings
from app.services.parser import (
    IngestionError,
    ParsedDocument,
    UnsupportedDocumentError,
    fetch_pdf,
    parse_document,
    parse_pdf_bytes,
    parse_with_pypdf,
    persist_markdown,
    read_document_cache,
    validate_document_url,
    write_document_cache,
)


def make_pdf(text: str = "Eligibility: annual income below INR 300000") -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.cell(0, 10, text)
    return bytes(pdf.output())


@pytest.mark.parametrize(
    "url",
    ["not-a-url", "ftp://example.gov.in/a.pdf", "https://", ""],
)
def test_validate_document_url_rejects_bad_urls(url: str) -> None:
    with pytest.raises(IngestionError):
        validate_document_url(url)


def test_fetch_pdf_accepts_pdf_response() -> None:
    pdf_bytes = make_pdf()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
        )

    transport = httpx.MockTransport(handler)

    async def run() -> bytes:
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_pdf("https://example.gov.in/a.pdf", client=client)

    assert asyncio.run(run()) == pdf_bytes


def test_fetch_pdf_rejects_html_response() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"<html>not a pdf</html>",
            headers={"content-type": "text/html"},
        )
    )

    async def run() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            await fetch_pdf("https://example.gov.in/a.pdf", client=client)

    with pytest.raises(UnsupportedDocumentError):
        asyncio.run(run())


def test_fetch_pdf_enforces_size_limit() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"%PDF-" + b"x" * 100,
            headers={"content-type": "application/pdf"},
        )
    )

    async def run() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            await fetch_pdf("https://example.gov.in/a.pdf", client=client, max_bytes=10)

    with pytest.raises(IngestionError, match="size limit"):
        asyncio.run(run())


def test_fetch_pdf_retries_transient_failures() -> None:
    calls = {"count": 0}
    pdf_bytes = make_pdf("Retried")

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(503, text="try later")
        return httpx.Response(200, content=pdf_bytes)

    async def run() -> bytes:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_pdf(
                "https://example.gov.in/a.pdf", client=client, retries=1, backoff_sec=0
            )

    assert asyncio.run(run()) == pdf_bytes
    assert calls["count"] == 2


def test_fetch_pdf_does_not_retry_client_errors() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(404, text="missing")

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await fetch_pdf("https://example.gov.in/a.pdf", client=client, retries=2, backoff_sec=0)

    with pytest.raises(IngestionError):
        asyncio.run(run())
    assert calls["count"] == 1


def test_pypdf_extracts_text_and_page_count() -> None:
    markdown, page_count = parse_with_pypdf(make_pdf("Hello Niti"))

    assert page_count == 1
    assert "Hello Niti" in markdown
    assert "<!-- page 1 -->" in markdown


def test_parse_pdf_bytes_uses_pypdf_when_docling_disabled() -> None:
    markdown, page_count, parser = parse_pdf_bytes(make_pdf("Fallback text"), use_docling=False)

    assert parser == "pypdf"
    assert page_count == 1
    assert "Fallback text" in markdown


def test_persist_markdown_writes_header_and_body(tmp_path: Path) -> None:
    parsed = ParsedDocument(
        source_url="https://example.gov.in/a.pdf",
        markdown="# Policy\n\nBody text",
        page_count=2,
        parser="pypdf",
        fetched_at=datetime.now(UTC),
    )

    path = persist_markdown("abc123", parsed, data_dir=tmp_path)

    assert path == tmp_path / "parsed" / "abc123.md"
    content = path.read_text(encoding="utf-8")
    assert "<!-- source: https://example.gov.in/a.pdf -->" in content
    assert "<!-- parser: pypdf -->" in content
    assert "Body text" in content


def test_parse_document_fetches_parses_and_persists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pdf_bytes = make_pdf("Live policy text")

    async def fake_fetch(url: str, **kwargs: object) -> bytes:
        return pdf_bytes

    monkeypatch.setattr("app.services.parser.fetch_pdf", fake_fetch)
    settings = Settings(data_dir=str(tmp_path), use_docling=False)

    async def run() -> ParsedDocument:
        return await parse_document(
            "https://example.gov.in/a.pdf", task_id="task1", settings=settings
        )

    parsed = asyncio.run(run())

    assert parsed.parser == "pypdf"
    assert parsed.page_count == 1
    assert "Live policy text" in parsed.markdown
    assert parsed.markdown_path is not None
    assert parsed.markdown_path.exists()


def test_document_cache_roundtrip(tmp_path: Path) -> None:
    parsed = ParsedDocument(
        source_url="https://example.gov.in/cached.pdf",
        markdown="# Cached policy\n\nBody",
        page_count=3,
        parser="pypdf",
        fetched_at=datetime.now(UTC),
    )

    write_document_cache(parsed, data_dir=tmp_path)
    restored = read_document_cache("https://example.gov.in/cached.pdf", data_dir=tmp_path)

    assert restored is not None
    assert restored.markdown == parsed.markdown
    assert restored.page_count == 3
    assert restored.from_cache is True


def test_parse_document_falls_back_to_cache_when_source_is_down(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = Settings(data_dir=str(tmp_path), use_docling=False)
    cached = ParsedDocument(
        source_url="https://example.gov.in/offline.pdf",
        markdown="# Offline policy\n\nStill readable",
        page_count=1,
        parser="pypdf",
        fetched_at=datetime.now(UTC),
    )
    write_document_cache(cached, data_dir=settings.data_dir)

    async def failing_fetch(url: str, **kwargs: object) -> bytes:
        raise IngestionError("network down")

    monkeypatch.setattr("app.services.parser.fetch_pdf", failing_fetch)

    async def run() -> ParsedDocument:
        return await parse_document(
            "https://example.gov.in/offline.pdf", task_id="offline-task", settings=settings
        )

    parsed = asyncio.run(run())

    assert parsed.from_cache is True
    assert "Still readable" in parsed.markdown
    assert parsed.markdown_path is not None
    assert parsed.markdown_path.exists()


def test_offline_mode_requires_a_cache_entry(tmp_path: Path) -> None:
    settings = Settings(data_dir=str(tmp_path), offline_mode=True)

    async def run() -> ParsedDocument:
        return await parse_document(
            "https://example.gov.in/never-cached.pdf", task_id="offline", settings=settings
        )

    with pytest.raises(IngestionError, match="no cache entry"):
        asyncio.run(run())
