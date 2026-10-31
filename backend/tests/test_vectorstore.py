"""Tests for hierarchical chunking and Qdrant hybrid retrieval."""

import re

from qdrant_client import QdrantClient, models

from app.services.chunker import chunk_markdown
from app.services.vectorstore import HybridVectorStore

SAMPLE_MARKDOWN = """<!-- page 1 -->
# Street Vendors Scheme

## Eligibility

1. The vendor must hold a valid certificate of vending.
2. Annual household income must be below INR 3,00,000.

## Benefits

The scheme provides an interest subsidy of INR 50,000.

<!-- page 2 -->
## Deadlines

Applications must be renewed before 31 March 2027.
"""


def test_chunker_creates_sections_and_clauses() -> None:
    chunks = chunk_markdown(SAMPLE_MARKDOWN, document_id="doc1")

    sections = [chunk for chunk in chunks if chunk.chunk_type == "section"]
    clauses = [chunk for chunk in chunks if chunk.chunk_type == "clause"]

    titles = {section.section_title for section in sections}
    assert titles >= {"Eligibility", "Benefits", "Deadlines"}
    assert len(clauses) >= 3

    eligibility = next(section for section in sections if section.section_title == "Eligibility")
    eligibility_clauses = [chunk for chunk in clauses if chunk.parent_id == eligibility.chunk_id]
    assert len(eligibility_clauses) == 2
    assert all(
        "certificate" in chunk.text or "income" in chunk.text for chunk in eligibility_clauses
    )


def test_chunker_tracks_page_numbers() -> None:
    chunks = chunk_markdown(SAMPLE_MARKDOWN, document_id="doc1")

    deadline = next(chunk for chunk in chunks if chunk.section_title == "Deadlines")

    assert deadline.page == 2
    assert "(page 2)" in deadline.citation


def test_chunker_citations_include_clause_numbers() -> None:
    chunks = chunk_markdown(SAMPLE_MARKDOWN, document_id="doc1")

    citations = [chunk.citation for chunk in chunks]

    assert any("Eligibility, clause 1 (page 1)" in citation for citation in citations)


def test_chunker_splits_long_paragraphs() -> None:
    long_sentence = "Eligible vendors must submit supporting documents to the authority. " * 40
    markdown = f"## Documents\n\n{long_sentence}"

    chunks = chunk_markdown(markdown, document_id="doc1", max_chars=200)
    clauses = [chunk for chunk in chunks if chunk.chunk_type == "clause"]

    assert len(clauses) > 1
    assert all(len(chunk.text) <= 200 for chunk in clauses)


def test_chunker_keeps_table_headers_with_rows() -> None:
    markdown = """## TABLE

| Sl. No. | Scheme | Rate |
|---|---|---|
| 1 | Employees' Provident Fund Scheme, 1952 | 0.35 |
| 2 | Employees' State Insurance Scheme | 0.005 |
"""

    chunks = chunk_markdown(markdown, document_id="doc1")
    table = next(
        chunk for chunk in chunks if chunk.chunk_type == "clause" and "Sl. No." in chunk.text
    )

    assert table.text.startswith("| Sl. No. | Scheme | Rate |")
    assert "Employees' Provident Fund Scheme" in table.text


def test_chunker_repeats_table_header_when_splitting() -> None:
    rows = "\n".join(f"| {index} | Scheme {index} | 0.35 |" for index in range(1, 40))
    markdown = f"## TABLE\n\n| Sl. No. | Scheme | Rate |\n|---|---|---|\n{rows}"

    chunks = chunk_markdown(markdown, document_id="doc1", max_chars=180)
    tables = [chunk for chunk in chunks if chunk.chunk_type == "clause"]

    assert len(tables) > 1
    assert all(chunk.text.startswith("| Sl. No. | Scheme | Rate |") for chunk in tables)


def test_chunker_handles_document_without_headings() -> None:
    chunks = chunk_markdown("A plain notification with no headings.", document_id="doc1")

    assert len(chunks) == 2
    assert chunks[0].section_title == "Preamble"
    assert chunks[0].chunk_type == "section"
    assert chunks[1].chunk_type == "clause"
    assert chunks[1].parent_id == chunks[0].chunk_id


class FakeEmbeddings:
    """Deterministic keyword embeddings so tests never download models."""

    VOCAB = ["eligibility", "income", "deadline", "penalty", "subsidy", "document"]

    def embed_dense(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.lower()
            vector = [float(lowered.count(word)) for word in self.VOCAB]
            vector.append(1.0)
            vectors.append(vector)
        return vectors

    def embed_sparse(self, texts: list[str]) -> list[models.SparseVector]:
        vectors: list[models.SparseVector] = []
        for text in texts:
            tokens = re.findall(r"[a-z0-9]+", text.lower())
            counts = {token: tokens.count(token) for token in set(tokens) if token in self.VOCAB}
            ordered = sorted(counts, key=self.VOCAB.index)
            vectors.append(
                models.SparseVector(
                    indices=[self.VOCAB.index(token) + 1 for token in ordered],
                    values=[float(counts[token]) for token in ordered],
                )
            )
        return vectors


def make_store() -> tuple[HybridVectorStore, QdrantClient]:
    client = QdrantClient(":memory:")
    store = HybridVectorStore(
        client,
        collection_name="test_chunks",
        embeddings=FakeEmbeddings(),
    )
    return store, client


def test_vectorstore_indexes_and_hybrid_searches() -> None:
    store, client = make_store()
    indexed = store.index_document(SAMPLE_MARKDOWN, document_id="doc1")

    hits = store.search("eligibility income", limit=5)

    assert indexed > 0
    assert client.count(collection_name="test_chunks").count == indexed
    assert hits
    assert any("income" in hit.text.lower() for hit in hits)


def test_vectorstore_filters_by_document_id() -> None:
    store, _ = make_store()
    store.index_document(SAMPLE_MARKDOWN, document_id="doc1")
    store.index_document(
        "## Penalty\n\nA penalty applies for late renewal.",
        document_id="doc2",
    )

    hits = store.search("penalty", document_id="doc2", limit=5)

    assert hits
    assert all(hit.payload["document_id"] == "doc2" for hit in hits)
