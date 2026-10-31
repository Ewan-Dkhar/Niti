"""Manual Phase 3 verification: fetch and parse a live government PDF.

Usage:
    uv run python scripts/verify_ingestion.py https://example.gov.in/document.pdf
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.parser import parse_document  # noqa: E402


async def main(url: str) -> int:
    parsed = await parse_document(url, task_id="live-verify")
    print(f"parser: {parsed.parser}")
    print(f"pages: {parsed.page_count}")
    print(f"markdown_path: {parsed.markdown_path}")
    print(f"markdown_chars: {len(parsed.markdown)}")
    print("--- preview ---")
    print(parsed.markdown[:800])
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(sys.argv[1])))
