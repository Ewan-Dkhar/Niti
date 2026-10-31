"""Graph entry node: fetch and parse the source document."""

from app.agent.state import AgentState
from app.services.parser import parse_document


async def parse_document_node(state: AgentState) -> dict:
    if state.get("parsed_markdown"):
        return {}

    parsed = await parse_document(
        state["raw_document_url"],
        task_id=state["task_id"],
    )
    return {
        "parsed_markdown": parsed.markdown,
        "parser": parsed.parser,
        "page_count": parsed.page_count,
        "markdown_path": str(parsed.markdown_path) if parsed.markdown_path else None,
    }
