"""LangGraph node functions — one per phase of the abstract flow."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.agent.prompts import (
    ASSESSMENT_GENERATION_PROMPT,
    GREETING_PROMPT,
    REFINEMENT_PROMPT,
    SYSTEM_PROMPT,
    TOPIC_REASONING_PROMPT,
)
from src.agent.state import AgentState
from src.config import settings
from src.services.vector_search import search_chunks, search_chunks_by_los

llm = ChatOpenAI(
    model=settings.OPENAI_MODEL,
    api_key=settings.OPENAI_API_KEY,
    temperature=0.3,
)

# ---------------------------------------------------------------------------
# A) Router — decides which handler should run next
# ---------------------------------------------------------------------------

ROUTE_SYSTEM = """\
You are a routing classifier for a teacher assessment assistant.
Given the conversation history, the current session state, and the latest
user message, classify the user intent into EXACTLY ONE of these categories:

- greeting        : casual greeting or session start
- topic_input     : teacher describes a topic, subject area, or student need
- selection       : teacher selects specific LOs / topics from a suggestion list
- approval        : teacher approves / is satisfied with retrieved content
- rejection       : teacher rejects content or asks for changes / refinement
- generate        : teacher explicitly asks to generate the assessment
- other           : anything that doesn't fit above

Respond with ONLY the category name (one word, lowercase).
"""


async def route_input(state: AgentState) -> dict:
    """Classify the latest user message and decide the next node."""
    session = state["session"]
    current_state = session.get("state", "greeting")
    messages = state["messages"]

    # Build a small classification prompt
    last_user = ""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            last_user = m.content
            break

    classification_messages = [
        SystemMessage(content=ROUTE_SYSTEM),
        HumanMessage(
            content=(
                f"Current session state: {current_state}\n"
                f"User message: {last_user}"
            )
        ),
    ]

    response = await llm.ainvoke(classification_messages)
    intent = response.content.strip().lower().split()[0]

    # Map intent → next node based on current flow position
    if current_state == "greeting":
        return {**state, "session": {**session, "_next": "handle_greeting"}}

    if intent in ("greeting",) and current_state == "greeting":
        return {**state, "session": {**session, "_next": "handle_greeting"}}

    if intent == "topic_input" or current_state == "topic_identification":
        return {**state, "session": {**session, "_next": "reason_topics"}}

    if intent == "selection" or current_state == "domain_reasoning":
        return {**state, "session": {**session, "_next": "handle_selection"}}

    if intent == "generate" or current_state == "assessment_generation":
        return {**state, "session": {**session, "_next": "generate_assessment"}}

    if intent == "rejection" and current_state in (
        "review_refinement", "content_retrieval",
    ):
        return {**state, "session": {**session, "_next": "handle_refinement"}}

    if intent == "approval" and current_state in (
        "review_refinement", "content_retrieval",
    ):
        return {**state, "session": {**session, "_next": "generate_assessment"}}

    if current_state == "topic_selection":
        return {**state, "session": {**session, "_next": "retrieve_content"}}

    if current_state == "content_retrieval":
        return {**state, "session": {**session, "_next": "retrieve_content"}}

    if current_state == "review_refinement":
        return {**state, "session": {**session, "_next": "handle_refinement"}}

    # Fallback: stay in current node context
    node_map = {
        "greeting": "handle_greeting",
        "topic_identification": "reason_topics",
        "domain_reasoning": "reason_topics",
        "topic_selection": "handle_selection",
        "content_retrieval": "retrieve_content",
        "review_refinement": "handle_refinement",
        "assessment_generation": "generate_assessment",
        "complete": "generate_assessment",
    }
    fallback = node_map.get(current_state, "handle_greeting")
    return {**state, "session": {**session, "_next": fallback}}


# ---------------------------------------------------------------------------
# B) Phase handlers
# ---------------------------------------------------------------------------

async def handle_greeting(state: AgentState) -> dict:
    """Respond with a professional greeting."""
    session = state["session"]
    sys_msg = SystemMessage(
        content=SYSTEM_PROMPT.format(
            curriculum_context=state.get("curriculum_context", "")
        )
    )
    prompt = SystemMessage(content=GREETING_PROMPT)
    response = await llm.ainvoke([sys_msg, prompt])

    session = {
        **session,
        "state": "topic_identification",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "messages": [response],
        "session": session,
    }


async def reason_topics(state: AgentState) -> dict:
    """Reason across the curriculum to suggest relevant LOs."""
    session = state["session"]
    messages = state["messages"]

    last_user = ""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            last_user = m.content
            break

    sys_msg = SystemMessage(
        content=SYSTEM_PROMPT.format(
            curriculum_context=state.get("curriculum_context", "")
        )
    )
    reasoning_prompt = HumanMessage(
        content=TOPIC_REASONING_PROMPT.format(user_input=last_user)
    )

    response = await llm.ainvoke([sys_msg] + list(messages) + [reasoning_prompt])

    session = {
        **session,
        "state": "domain_reasoning",
        "identified_topics": [last_user],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "messages": [response],
        "session": session,
    }


async def handle_selection(state: AgentState) -> dict:
    """Parse the teacher's LO selections and transition to content retrieval."""
    session = state["session"]
    messages = state["messages"]

    last_user = ""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            last_user = m.content
            break

    # Use LLM to extract selected LO codes from teacher's message
    extraction_prompt = [
        SystemMessage(
            content=(
                "Extract the Learning Outcome codes (format: 6.5.X.X.X) "
                "from the teacher's selection message. If the teacher uses "
                "numbers (e.g., '1, 3, 5') referring to a numbered list, "
                "map them to the LO codes from the conversation context. "
                "Return a JSON array of LO code strings. "
                "If you can't identify specific codes, return the teacher's "
                "selections as descriptive strings in the array."
            )
        ),
    ] + list(messages) + [
        HumanMessage(content=f"Teacher's selection: {last_user}"),
    ]

    response = await llm.ainvoke(extraction_prompt)
    raw = response.content.strip()

    # Try to parse JSON array
    selected: list[dict] = []
    try:
        codes = json.loads(raw)
        if isinstance(codes, list):
            selected = [{"code": c} for c in codes]
    except (json.JSONDecodeError, TypeError):
        # Fallback: treat the whole message as selection
        selected = [{"description": last_user}]

    # Look up full LO details from curriculum context
    from src.database import learning_outcomes_col

    enriched: list[dict] = []
    for sel in selected:
        code = sel.get("code", "")
        if code:
            lo_doc = await learning_outcomes_col.find_one({"code": code})
            if lo_doc:
                enriched.append({
                    "code": lo_doc["code"],
                    "name": lo_doc["name"],
                    "description": lo_doc["description"],
                    "subdomain_code": lo_doc["subdomain_code"],
                    "domain_code": lo_doc["domain_code"],
                })
            else:
                enriched.append(sel)
        else:
            enriched.append(sel)

    if not enriched:
        enriched = selected

    # Retrieve relevant chunks via vector search
    lo_descriptions = [e.get("description", e.get("code", "")) for e in enriched]
    chunks = await search_chunks_by_los(lo_descriptions, top_k=8)

    # Build a summary of retrieved content for the teacher
    chunk_summaries = []
    for idx, ch in enumerate(chunks, 1):
        preview = ch.get("content", "")[:300]
        chunk_summaries.append(
            f"**Chunk {idx}** (pages {ch.get('page_start')}–{ch.get('page_end')}):\n"
            f"{preview}…"
        )
    content_text = "\n\n".join(chunk_summaries) if chunk_summaries else "No relevant content found."

    reply = AIMessage(
        content=(
            f"I've selected the following Learning Outcomes and retrieved "
            f"relevant textbook content:\n\n"
            f"**Selected LOs:**\n"
            + "\n".join(
                f"- **{e.get('code', 'N/A')}** {e.get('name', e.get('description', ''))}"
                for e in enriched
            )
            + f"\n\n**Retrieved Content Summaries:**\n\n{content_text}"
            + "\n\nPlease review the content above. You can:\n"
            "- **Approve** to proceed with assessment generation\n"
            "- **Reject** specific content with a reason for refinement\n"
            "- **Request changes** to the LO selection"
        )
    )

    session = {
        **session,
        "state": "review_refinement",
        "selected_los": enriched,
        "retrieved_chunks": chunks,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "messages": [reply],
        "session": session,
        "selected_los": enriched,
        "retrieved_chunks": chunks,
    }


async def retrieve_content(state: AgentState) -> dict:
    """Retrieve textbook chunks for the selected LOs via vector search."""
    session = state["session"]
    selected = state.get("selected_los", session.get("selected_los", []))

    lo_descriptions = [lo.get("description", lo.get("code", "")) for lo in selected]
    chunks = await search_chunks_by_los(lo_descriptions, top_k=8)

    chunk_summaries = []
    for idx, ch in enumerate(chunks, 1):
        preview = ch.get("content", "")[:300]
        chunk_summaries.append(
            f"**Chunk {idx}** (pages {ch.get('page_start')}–{ch.get('page_end')}):\n"
            f"{preview}…"
        )
    content_text = "\n\n".join(chunk_summaries) if chunk_summaries else "No relevant content found."

    reply = AIMessage(
        content=(
            f"Here is the relevant textbook content for your selected LOs:\n\n"
            f"{content_text}\n\n"
            "Please review and let me know:\n"
            "- **Approve** to generate the assessment\n"
            "- **Reject** specific content with a reason"
        )
    )

    session = {
        **session,
        "state": "review_refinement",
        "retrieved_chunks": chunks,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "messages": [reply],
        "session": session,
        "retrieved_chunks": chunks,
    }


async def handle_refinement(state: AgentState) -> dict:
    """Re-reason over the curriculum based on teacher feedback."""
    session = state["session"]
    messages = state["messages"]

    last_user = ""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            last_user = m.content
            break

    selected_summary = "\n".join(
        f"- {lo.get('code', 'N/A')}: {lo.get('name', '')} — {lo.get('description', '')}"
        for lo in session.get("selected_los", [])
    )

    sys_msg = SystemMessage(
        content=SYSTEM_PROMPT.format(
            curriculum_context=state.get("curriculum_context", "")
        )
    )
    refinement = HumanMessage(
        content=REFINEMENT_PROMPT.format(
            user_input=last_user,
            selected_los=selected_summary,
        )
    )

    response = await llm.ainvoke([sys_msg] + list(messages) + [refinement])

    session = {
        **session,
        "state": "domain_reasoning",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "messages": [response],
        "session": session,
    }


async def generate_assessment(state: AgentState) -> dict:
    """Generate the final assessment questions."""
    session = state["session"]
    messages = state["messages"]

    selected = session.get("selected_los", [])
    chunks = session.get("retrieved_chunks", [])

    selected_summary = "\n".join(
        f"- **{lo.get('code', 'N/A')}** {lo.get('name', '')} "
        f"(Domain {lo.get('domain_code', '?')}, Subdomain {lo.get('subdomain_code', '?')}): "
        f"{lo.get('description', '')}"
        for lo in selected
    )

    # Combine chunk content (limit to avoid token overflow)
    chunk_texts = []
    total_chars = 0
    for ch in chunks:
        content = ch.get("content", "")
        if total_chars + len(content) > 12000:
            break
        chunk_texts.append(content)
        total_chars += len(content)
    textbook_content = "\n\n---\n\n".join(chunk_texts) if chunk_texts else "No textbook content available."

    sys_msg = SystemMessage(
        content=SYSTEM_PROMPT.format(
            curriculum_context=state.get("curriculum_context", "")
        )
    )
    gen_prompt = HumanMessage(
        content=ASSESSMENT_GENERATION_PROMPT.format(
            selected_los=selected_summary,
            textbook_content=textbook_content,
        )
    )

    response = await llm.ainvoke([sys_msg] + list(messages[-4:]) + [gen_prompt])

    session = {
        **session,
        "state": "complete",
        "generated_assessment": response.content,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "messages": [response],
        "session": session,
        "assessment": response.content,
    }
