"""Agent graph state definition (TypedDict consumed by LangGraph)."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    Shared state that flows through every node in the LangGraph.

    ``messages`` uses the LangGraph ``add_messages`` reducer so that each
    node can simply *return* new messages and they are appended
    automatically.
    """

    messages: Annotated[list[BaseMessage], add_messages]

    # Serialised session from MongoDB — carried through every invocation.
    session: dict

    # Pre-loaded curriculum text injected into prompts.
    curriculum_context: str

    # Discovery / selection artefacts
    matched_los: list[dict]
    selected_los: list[dict]
    retrieved_chunks: list[dict]

    # Optional rolling AI-generated summary of the conversation (what the teacher wants)
    conversation_summary: str

    # Final assessment markdown
    assessment: str
