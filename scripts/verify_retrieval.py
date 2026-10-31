"""Manual Phase 4 verification: parse, chunk, index, and retrieve.

Usage:
    uv run python scripts/verify_retrieval.py <pdf-url> "<query>"
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from qdrant_client import QdrantClient  # noqa: E402

from app.services.chunker import chunk_markdown  # noqa: E402
from app.services.parser import parse_document  # noqa: E402
from app.services.vectorstore import HybridVectorStore  # noqa: E402


async def main(url: str, query: str) -> int:
    parsed = await parse_document(url, task_id="retrieval-verify")
    chunks = chunk_markdown(parsed.markdown, document_id="live-doc")
    store = HybridVectorStore(QdrantClient(":memory:"), collection_name="verify")
    indexed = store.index_chunks(chunks)
    hits = store.search(query, limit=3)

    print(f"parser: {parsed.parser}; pages: {parsed.page_count}")
    print(f"chunks: {len(chunks)}; indexed: {indexed}")
    print(f"query: {query}")
    for rank, hit in enumerate(hits, start=1):
        print(f"\n[{rank}] score={hit.score:.4f} page={hit.page}")
        print(f"citation: {hit.citation}")
        print(f"text: {hit.text[:300]}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(sys.argv[1], sys.argv[2])))
