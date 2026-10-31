"""Manual Phase 5 verification: run the LangGraph pipeline end to end.

Usage:
    uv run python scripts/verify_graph.py <pdf-url> [language]
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.agent.graph import run_analysis  # noqa: E402


async def main(url: str, language: str) -> int:
    final_state = await run_analysis(
        {
            "task_id": "graph-verify",
            "raw_document_url": url,
            "target_language": language,
        }
    )

    print(f"parser: {final_state.get('parser')}")
    print(f"pages: {final_state.get('page_count')}")
    print(f"extracted_data: {final_state.get('extracted_data')}")
    print(f"audit_report: {final_state.get('audit_report')}")
    print(f"simplified_script: {final_state.get('simplified_script')!r}")
    print(f"audio_output_url: {final_state.get('audio_output_url')!r}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) not in {2, 3}:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else "hi-IN")))
