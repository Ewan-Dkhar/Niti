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
    validate_document_url,
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
