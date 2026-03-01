"""LangGraph state-graph definition and compilation."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.agent.nodes import (
    generate_assessment,
    handle_greeting,
    handle_refinement,
    handle_selection,
    reason_topics,
    retrieve_content,
    route_input,
)
from src.agent.state import AgentState

# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

workflow = StateGraph(AgentState)

# Register nodes
workflow.add_node("route_input", route_input)
workflow.add_node("handle_greeting", handle_greeting)
workflow.add_node("reason_topics", reason_topics)
workflow.add_node("handle_selection", handle_selection)
workflow.add_node("retrieve_content", retrieve_content)
workflow.add_node("handle_refinement", handle_refinement)
workflow.add_node("generate_assessment", generate_assessment)

# Entry point is always the router
workflow.set_entry_point("route_input")


# Conditional edges from the router → handler nodes
def _pick_next(state: AgentState) -> str:
    """Return the node name chosen by ``route_input``."""
    return state["session"].get("_next", "handle_greeting")


workflow.add_conditional_edges(
    "route_input",
    _pick_next,
    {
        "handle_greeting": "handle_greeting",
        "reason_topics": "reason_topics",
        "handle_selection": "handle_selection",
        "retrieve_content": "retrieve_content",
        "handle_refinement": "handle_refinement",
        "generate_assessment": "generate_assessment",
    },
)

# Each handler terminates the turn (returns to the user)
for node in [
    "handle_greeting",
    "reason_topics",
    "handle_selection",
    "retrieve_content",
    "handle_refinement",
    "generate_assessment",
]:
    workflow.add_edge(node, END)

# Compile
graph = workflow.compile()
