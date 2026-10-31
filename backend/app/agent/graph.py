"""LangGraph state machine for policy analysis."""

from langgraph.graph import END, StateGraph

from app.agent.nodes.audit import audit_verification_node, route_audit
from app.agent.nodes.extract import extract_rules_node
from app.agent.nodes.parse import parse_document_node
from app.agent.nodes.simplify import simplify_vernacular_node
from app.agent.nodes.voice import synthesize_voice_node
from app.agent.state import AgentState

workflow = StateGraph(AgentState)

workflow.add_node("parse_document", parse_document_node)
workflow.add_node("extract_rules", extract_rules_node)
workflow.add_node("audit_verification", audit_verification_node)
workflow.add_node("simplify_vernacular", simplify_vernacular_node)
workflow.add_node("synthesize_voice", synthesize_voice_node)

workflow.set_entry_point("parse_document")
workflow.add_edge("parse_document", "extract_rules")
workflow.add_edge("extract_rules", "audit_verification")
workflow.add_conditional_edges(
    "audit_verification",
    route_audit,
    {
        "simplify_vernacular": "simplify_vernacular",
        "re_extract": "extract_rules",
    },
)
workflow.add_edge("simplify_vernacular", "synthesize_voice")
workflow.add_edge("synthesize_voice", END)

analysis_graph = workflow.compile()


async def run_analysis(initial_state: AgentState) -> AgentState:
    """Run the graph and return the merged final state."""
    return await analysis_graph.ainvoke(initial_state)
