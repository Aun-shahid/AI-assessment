"""LangGraph node functions — one per phase of the abstract flow."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.agent.prompts import (
    ASSESSMENT_GENERATION_PROMPT,
    GREETING_PROMPT,
    REFINEMENT_PROMPT,
    SELECTION_CONFIRMATION_PROMPT,
    SHOW_LO_LIST_PROMPT,
    SYSTEM_PROMPT,
    TOPIC_NARROWING_PROMPT,
    TOPIC_REASONING_PROMPT,
)
from src.agent.state import AgentState
from src.config import settings
from src.services.reranker import rerank_chunks
from src.services.vector_search import (
    search_chunks_by_lo_codes,
    search_chunks_per_lo,
)

llm = ChatOpenAI(
    model=settings.OPENAI_MODEL,
    api_key=settings.OPENAI_API_KEY,
    temperature=0.3,
)
logger = logging.getLogger(__name__)


def _log_node(session: dict, node: str, event: str, **details: object) -> None:
    """Emit a structured log line for graph execution."""
    session_id = session.get("session_id", "unknown")
    if details:
        logger.info(
            "[graph] session=%s node=%s event=%s details=%s",
            session_id,
            node,
            event,
            details,
        )
        return
    logger.info("[graph] session=%s node=%s event=%s", session_id, node, event)


async def _invoke_llm(prompt_messages: list, *, tag: str, session: dict):
    """Wrap LLM calls so each invocation appears in the backend logs."""
    _log_node(session, tag, "llm_start", message_count=len(prompt_messages))
    response = await llm.ainvoke(prompt_messages)
    preview = response.content.replace("\n", " ")[:160]
    _log_node(session, tag, "llm_end", preview=preview)
    return response

# ---------------------------------------------------------------------------
# A) Router — decides which handler should run next
# ---------------------------------------------------------------------------

ROUTE_SYSTEM = """\
You are a routing classifier for a teacher assessment assistant.
Given the conversation history, the current session state, and the latest
user message, classify the user intent into EXACTLY ONE of these categories:

- greeting        : pure casual greeting ("hello", "hi") with NO topic or request attached.
- topic_input     : teacher describes a topic, subject area, or asks to start a new assessment/change topics (e.g. "let's do another one", "different topic", "hello make a quiz on Game of Thrones").
- info_request    : teacher asks to see more details, a full list of LOs, or more information about specific topics/subdomains (e.g. "show me the LOs for...", "what LOs are in...", "list all...", "show me the full list")
- selection       : teacher EXPLICITLY selects specific LOs from a list, or explicitly selects a topic/subdomain when asked (e.g. "I choose 1, 3, 5", "lets make a quiz from gravity effects", "I want numbers 2 and 4")
- approval        : teacher approves / is satisfied and wants to proceed to the NEXT step (e.g. "looks good, proceed", "yes, go ahead", "confirmed")
- rejection       : teacher rejects content or asks for changes (e.g. "too hard", "not relevant", "change this")
- generate        : teacher explicitly asks to generate the assessment (e.g. "generate", "create the quiz", "make the test")
- other           : conversational banter, out-of-context remarks, complaints about being robotic, clarification questions, or anything that doesn't fit above (e.g. "are there more options?", "you are a bot", "why did you say that?")

IMPORTANT distinctions:
- "show me the LOs" or "list the topics" or "what LOs are available" = info_request (NOT selection)
- "those topics look good, show me more" or "please show me the full list" = info_request (NOT approval)
- "I choose 6.5.3.1.1 and 6.5.2.2.3" or "I'll take numbers 1, 3, 5" = selection
- "looks good, generate" or "yes, create the assessment" = approval or generate
- A message that says topics "look good" BUT ALSO asks to see a list = info_request
- A meta-request to start over like "make another quiz" = topic_input
- A purely conversational complaint like "you are a bot" or "do you have more options?" = other

Respond with ONLY the category name (one word, lowercase).
"""

SCOPE_CHECK_SYSTEM = """\
You validate whether a teacher's requested assessment topic is within the
supported curriculum scope.

Supported scope:
- Grade 6 science only
- Domains: Life Sciences, Physical Sciences, Earth and Space Sciences
- Any request clearly about fiction, entertainment, history outside the listed
    science curriculum, sports, politics, or general trivia is OUT OF SCOPE.
- Broad but still science-aligned requests like 'science quiz' or 'something on
    forces' are IN SCOPE.
- Generic meta-requests to start a new quiz (e.g., 'let's do another one', 'different topic') are IN SCOPE.
- ONLY return out_of_scope if the user explicitly names a subject that is definitely outside Grade 6 Science (like 'Game of Thrones', 'Football', 'Harry Potter').

Return EXACTLY ONE token:
- in_scope
- out_of_scope
"""

OUT_OF_SCOPE_REPLY = """\
I'm sorry, I don't have information on that topic. My knowledge is strictly focused on the provided Grade 6 Science curriculum. 

Can I help you create an assessment for a topic related to science instead? Here are the domains I cover:

- **Domain 1: Life Sciences**
    - 1.1 Structure & Function
    - 1.2 Organization
    - 1.3 Ecosystems
    - 1.4 Genetics
- **Domain 2: Physical Sciences**
    - 2.1 Matter
    - 2.2 Motion & Forces
    - 2.3 Energy
    - 2.4 Waves
    - 2.5 Electromagnetism
- **Domain 3: Earth and Space Sciences**
    - 3.1 Universe & Solar System
    - 3.2 Earth System

Just let me know what science topic you'd like to try (like gravity, cells, or chemical reactions)!
"""


async def _is_in_curriculum_scope(session: dict, current_state: str, user_message: str) -> bool:
    """Check whether the teacher's request belongs to the supported curriculum."""
    scope_messages = [
        SystemMessage(content=SCOPE_CHECK_SYSTEM),
        HumanMessage(
            content=(
                f"Current session state: {current_state}\n"
                f"Teacher request: {user_message}"
            )
        ),
    ]
    response = await _invoke_llm(scope_messages, tag="scope_check", session=session)
    verdict = response.content.strip().lower().split()[0]
    _log_node(session, "scope_check", "classified", verdict=verdict)
    return verdict == "in_scope"


async def route_input(state: AgentState) -> dict:
    """Classify the latest user message and decide the next node."""
    session = state["session"]
    current_state = session.get("state", "greeting")
    messages = state["messages"]
    _log_node(session, "route_input", "enter", current_state=current_state)

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

    response = await _invoke_llm(classification_messages, tag="route_classifier", session=session)
    intent = response.content.strip().lower().split()[0]
    _log_node(session, "route_input", "classified", intent=intent, user_message=last_user[:120])

    if intent in ("topic_input", "greeting"):
        in_scope = await _is_in_curriculum_scope(session, current_state, last_user)
        if not in_scope:
            _log_node(session, "route_input", "out_of_scope_interrupt", user_message=last_user[:120])
            return {**state, "session": {**session, "_next": "handle_out_of_scope"}}

    # ── State-based routing with intent awareness ──

    # CONVERSATIONAL FALLBACK
    if intent == "other":
        return {**state, "session": {**session, "_next": "handle_conversational_fallback"}}

    # GREETING: if user already provides a topic, skip the greeting
    if current_state == "greeting":
        if intent == "topic_input":
            return {**state, "session": {**session, "_next": "reason_topics"}}
        return {**state, "session": {**session, "_next": "handle_greeting"}}

    # TOPIC_IDENTIFICATION: waiting for user to describe a topic
    if current_state == "topic_identification":
        if intent == "selection":
            return {**state, "session": {**session, "_next": "reason_topics"}}
        return {**state, "session": {**session, "_next": "reason_topics"}}

    # DOMAIN_REASONING: LOs have been suggested; teacher may ask for more
    # info, select LOs, or provide a new topic.
    if current_state == "domain_reasoning":
        if intent == "selection":
            # Teacher is explicitly selecting LOs
            return {**state, "session": {**session, "_next": "handle_selection"}}
        if intent == "topic_input":
            return {**state, "session": {**session, "_next": "reason_topics"}}
        if intent == "info_request":
            # Teacher wants to see more details / full LO list — stay in discovery
            return {**state, "session": {**session, "_next": "show_lo_list"}}
        if intent == "approval":
            # "Yes, this is it" -> The teacher approves the suggested LO(s) implicitly
            return {**state, "session": {**session, "_next": "handle_selection"}}
        # Default: if intent is ambiguous, parse it as a selection attempt rather than repeating info
        return {**state, "session": {**session, "_next": "handle_selection"}}

    # TOPIC_SELECTION: LOs have been selected and confirmed; await explicit
    # approval before retrieving content.
    if current_state == "topic_selection":
        if intent in ("approval", "generate"):
            return {**state, "session": {**session, "_next": "retrieve_content"}}
        if intent == "topic_input":
            return {**state, "session": {**session, "_next": "reason_topics"}}
        if intent == "selection":
            # Teacher wants to modify their selection
            return {**state, "session": {**session, "_next": "handle_selection"}}
        if intent == "info_request":
            return {**state, "session": {**session, "_next": "show_lo_list"}}
        if intent == "rejection":
            return {**state, "session": {**session, "_next": "reason_topics"}}
        # Default: let teacher refine selection
        return {**state, "session": {**session, "_next": "handle_selection"}}

    # CONTENT_RETRIEVAL: content fetched, present for review
    if current_state == "content_retrieval":
        return {**state, "session": {**session, "_next": "retrieve_content"}}

    # REVIEW_REFINEMENT: teacher reviews content
    if current_state == "review_refinement":
        if intent in ("approval", "generate"):
            return {**state, "session": {**session, "_next": "generate_assessment"}}
        if intent == "topic_input":
            # Teacher wants to start over with different topics
            return {**state, "session": {**session, "_next": "reason_topics"}}
        # Default: treat as refinement feedback (rejection / change request)
        return {**state, "session": {**session, "_next": "handle_refinement"}}

    # ASSESSMENT_GENERATION / COMPLETE
    if current_state in ("assessment_generation", "complete"):
        if intent == "topic_input":
            return {**state, "session": {**session, "_next": "reason_topics"}}
        return {**state, "session": {**session, "_next": "generate_assessment"}}

    # Fallback
    return {**state, "session": {**session, "_next": "handle_greeting"}}


# ---------------------------------------------------------------------------
# B) Phase handlers
# ---------------------------------------------------------------------------

async def handle_greeting(state: AgentState) -> dict:
    """Respond with a professional greeting and ask for a topic."""
    session = state["session"]
    messages = state["messages"]
    _log_node(session, "handle_greeting", "enter", message_count=len(messages))

    sys_msg = SystemMessage(
        content=SYSTEM_PROMPT.format(
            curriculum_context=state.get("curriculum_context", "")
        )
    )
    greeting_instruction = SystemMessage(content=GREETING_PROMPT)
    response = await _invoke_llm([sys_msg, greeting_instruction] + list(messages), tag="handle_greeting", session=session)

    session = {
        **session,
        "state": "topic_identification",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "messages": [response],
        "session": session,
    }


async def handle_out_of_scope(state: AgentState) -> dict:
    """Interrupt requests that fall outside the provided curriculum."""
    session = state["session"]
    messages = state["messages"]
    _log_node(session, "handle_out_of_scope", "enter", message_count=len(messages))

    last_user = ""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            last_user = m.content
            break

    reply = AIMessage(content=OUT_OF_SCOPE_REPLY.format(user_input=last_user))
    session = {
        **session,
        "state": "topic_identification",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _log_node(session, "handle_out_of_scope", "exit", next_state=session["state"])
    return {
        "messages": [reply],
        "session": session,
    }


async def handle_conversational_fallback(state: AgentState) -> dict:
    """Handle general conversational banter or non-workflow related queries elegantly."""
    session = state["session"]
    messages = state["messages"]
    _log_node(session, "handle_conversational_fallback", "enter", message_count=len(messages))

    sys_msg = SystemMessage(
        content=(
            "You are EduAssess, an expert AI assessment assistant. The user has said something conversational, "
            "unpredictable, or slightly off-script that doesn't immediately advance the workflow. "
            "Respond intelligently, humanly, and conversationally in a helpful tone. "
            "Address their remark directly. If it makes sense, gently remind them of where you both are "
            "in the assessment creation process, but do so naturally. Do NOT output robotic templates or force "
            "repetitive lists. Be a smart AI."
        )
    )

    response = await _invoke_llm([sys_msg] + list(messages), tag="conversational_fallback", session=session)

    # State remains exactly as it was, we just answer conversationally.
    session = {
        **session,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    return {
        "messages": [response],
        "session": session,
    }


async def reason_topics(state: AgentState) -> dict:
    """Reason across the curriculum to suggest relevant LOs.

    First checks whether the teacher's input is specific enough to map to
    concrete LOs.  If it is too broad (e.g. "science quiz", "general
    review"), the node asks the teacher to narrow down to a domain or
    subdomain before suggesting anything.
    """
    session = state["session"]
    messages = state["messages"]
    _log_node(session, "reason_topics", "enter", message_count=len(messages))

    last_user = ""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            last_user = m.content
            break

    # ── Step 1: Classify topic specificity ──
    specificity_msgs = [
        SystemMessage(
            content=(
                "You are a topic-specificity classifier for a Grade 6 science "
                "curriculum. Decide whether the teacher's topic description is "
                "specific enough to identify relevant Learning Outcomes, or too "
                "broad.\n\n"
                "SPECIFIC examples (answer 'specific'):\n"
                "- 'gravity and the solar system'\n"
                "- 'Newton's laws of motion'\n"
                "- 'cell structures and plant vs animal cells'\n"
                "- 'acids and bases'\n"
                "- 'the rock cycle and minerals'\n"
                "- 'ecosystems and food webs'\n"
                "- 'motion and forces, especially friction'\n\n"
                "BROAD examples (answer 'broad'):\n"
                "- 'science quiz'\n"
                "- 'general science for 6th graders'\n"
                "- 'a quiz for my class'\n"
                "- 'everything we've covered'\n"
                "- 'life sciences' (this is an entire domain)\n"
                "- 'physical sciences'\n\n"
                "Respond with ONLY one word: 'specific' or 'broad'."
            )
        ),
        HumanMessage(content=f"Teacher's topic: {last_user}"),
    ]
    specificity_resp = await _invoke_llm(specificity_msgs, tag="topic_specificity", session=session)
    is_specific = specificity_resp.content.strip().lower().startswith("specific")
    _log_node(session, "reason_topics", "specificity_result", is_specific=is_specific)

    sys_msg = SystemMessage(
        content=SYSTEM_PROMPT.format(
            curriculum_context=state.get("curriculum_context", "")
        )
    )

    # ── Step 2a: Topic too broad → ask teacher to narrow down ──
    if not is_specific:
        narrowing_prompt = HumanMessage(
            content=TOPIC_NARROWING_PROMPT.format(user_input=last_user)
        )
        response = await _invoke_llm(
            [sys_msg] + list(messages) + [narrowing_prompt],
            tag="topic_narrowing",
            session=session,
        )

        # Stay in topic_identification — don't advance to domain_reasoning
        session = {
            **session,
            "state": "topic_identification",
            "identified_topics": [last_user],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        return {
            "messages": [response],
            "session": session,
        }

    # ── Step 2b: Topic is specific → suggest matching LOs ──
    reasoning_prompt = HumanMessage(
        content=TOPIC_REASONING_PROMPT.format(user_input=last_user)
    )

    response = await _invoke_llm([sys_msg] + list(messages) + [reasoning_prompt], tag="topic_reasoning", session=session)

    # Extract matched LO codes from the reasoning response
    extraction_msgs = [
        SystemMessage(
            content=(
                "Extract all Learning Outcome codes from the text below. "
                "Codes follow patterns like 6.5.X.X.X. "
                "Return ONLY a valid JSON array of code strings, e.g. "
                '[\"6.5.2.1.1\", \"6.5.3.1.2\"]. If no codes found, return [].'
            )
        ),
        HumanMessage(content=response.content),
    ]
    extraction_resp = await _invoke_llm(extraction_msgs, tag="lo_extraction", session=session)

    matched_los: list[dict] = []
    try:
        raw = extraction_resp.content.strip()
        # Handle markdown code blocks
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        codes = json.loads(raw)
        if isinstance(codes, list):
            from src.database import learning_outcomes_col

            for code in codes:
                lo_doc = await learning_outcomes_col.find_one({"code": str(code)})
                if lo_doc:
                    matched_los.append({
                        "code": lo_doc["code"],
                        "name": lo_doc["name"],
                        "description": lo_doc["description"],
                        "subdomain_code": lo_doc["subdomain_code"],
                        "domain_code": lo_doc["domain_code"],
                    })
    except (json.JSONDecodeError, TypeError, IndexError):
        pass

    if not matched_los:
        _log_node(session, "reason_topics", "no_matches", user_message=last_user[:120])
        reply = AIMessage(
            content=(
                "I couldn't confidently map that request to the provided curriculum. "
                "Please rephrase it using one of the supported Grade 6 science areas, "
                "such as gravity, cells, ecosystems, matter, or the solar system."
            )
        )
        session = {
            **session,
            "state": "topic_identification",
            "identified_topics": [last_user],
            "matched_los": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        return {
            "messages": [reply],
            "session": session,
            "matched_los": [],
        }

    session = {
        **session,
        "state": "domain_reasoning",
        "identified_topics": [last_user],
        "matched_los": matched_los,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "messages": [response],
        "session": session,
        "matched_los": matched_los,
    }


async def show_lo_list(state: AgentState) -> dict:
    """Show the teacher a detailed list of LOs for the requested subdomains/domains.

    This node uses the enriched curriculum data to display LOs — it does NOT
    perform content retrieval or advance the state beyond discovery.
    """
    session = state["session"]
    messages = state["messages"]
    _log_node(session, "show_lo_list", "enter", message_count=len(messages))

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
    lo_list_prompt = HumanMessage(
        content=SHOW_LO_LIST_PROMPT.format(user_input=last_user)
    )

    response = await _invoke_llm([sys_msg] + list(messages) + [lo_list_prompt], tag="show_lo_list", session=session)

    # Stay in domain_reasoning — don't advance the state
    session = {
        **session,
        "state": "domain_reasoning",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "messages": [response],
        "session": session,
    }


async def handle_selection(state: AgentState) -> dict:
    """Parse the teacher's LO selections and confirm them.

    This node ONLY identifies and confirms which LOs the teacher selected.
    It does NOT retrieve textbook content — that happens in a separate
    ``retrieve_content`` step after the teacher explicitly approves.
    """
    session = state["session"]
    messages = state["messages"]
    _log_node(session, "handle_selection", "enter", message_count=len(messages))

    last_user = ""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            last_user = m.content
            break

    matched_los = session.get("matched_los", [])
    matched_summary = "\n".join(
        f"{i+1}. [{lo.get('code', '')}] {lo.get('name', '')}"
        for i, lo in enumerate(matched_los)
    )

    # ── Step 0: Detect explicit selection vs vague approval ──
    # "go ahead", "yes", "ok" are NOT explicit selections — the user
    # never mentioned numbers, codes, or topic names.
    explicitness_msgs = [
        SystemMessage(
            content=(
                "Classify whether the teacher's message is an EXPLICIT selection "
                "of specific Learning Outcomes, or just a VAGUE approval/confirmation.\n\n"
                "EXPLICIT examples (answer 'explicit'):\n"
                "- 'I choose 1 and 3'\n"
                "- '6.5.1.1.1 please'\n"
                "- 'the first one about cells'\n"
                "- 'all of them'\n"
                "- 'just the cell structures one'\n"
                "- 'numbers 2 and 4'\n\n"
                "VAGUE examples (answer 'vague'):\n"
                "- 'go ahead'\n"
                "- 'ok'\n"
                "- 'yes'\n"
                "- 'sounds good'\n"
                "- 'that makes sense, proceed'\n"
                "- 'sure'\n"
                "- 'yeah let's do it'\n\n"
                "Respond with ONLY one word: 'explicit' or 'vague'."
            )
        ),
        HumanMessage(content=f"Teacher's message: {last_user}"),
    ]
    explicitness_resp = await _invoke_llm(
        explicitness_msgs, tag="selection_explicitness", session=session
    )
    is_explicit = explicitness_resp.content.strip().lower().startswith("explicit")
    _log_node(session, "handle_selection", "explicitness", is_explicit=is_explicit, user_message=last_user[:80])

    # ── Vague approval with existing matched LOs → auto-select all ──
    if not is_explicit and matched_los:
        valid_matched = [lo for lo in matched_los if "name" in lo and "code" in lo]
        if valid_matched:
            lo_names = ", ".join(lo.get("name", "") for lo in valid_matched)
            reply = AIMessage(
                content=(
                    f"Sure thing! I'll use all the suggested Learning Outcomes "
                    f"({lo_names}) for your assessment. "
                    f"Ready for me to pull up the relevant textbook material?"
                )
            )
            session = {
                **session,
                "state": "topic_selection",
                "selected_los": valid_matched,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            return {
                "messages": [reply],
                "session": session,
                "selected_los": valid_matched,
            }

    # ── Vague approval with NO matched LOs → ask for clarification ──
    if not is_explicit:
        _log_node(session, "handle_selection", "vague_no_context", user_message=last_user[:120])
        reply = AIMessage(
            content=(
                "I'd love to proceed, but I need to know which Learning Outcomes "
                "you'd like to include. Could you pick from the list above "
                "(e.g., 'number 1', 'both', or mention the topic name)?"
            )
        )
        session = {
            **session,
            "state": "domain_reasoning",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        return {
            "messages": [reply],
            "session": session,
            "selected_los": [],
        }

    # ── Explicit selection → extract specific LO codes ──
    extraction_prompt = [
        SystemMessage(
            content=(
                "Extract the Learning Outcome codes (format: 6.5.X.X.X) "
                "that the teacher EXPLICITLY selected in their message. "
                "The teacher may refer to LOs by:\n"
                "- Position numbers (e.g., '1, 3, 5') from the numbered list below\n"
                "- LO codes directly (e.g., '6.5.3.1.1')\n"
                "- Topic name references (e.g., 'the cell structures one')\n"
                "- Phrases like 'all of them' or 'the first three'\n\n"
                "IMPORTANT: Only extract codes the teacher EXPLICITLY referenced. "
                "Do NOT include codes just because they appear in the conversation "
                "history. If the teacher says 'go ahead' or 'ok' without specifying "
                "which LOs, return an empty array.\n\n"
                f"Available LOs from previous suggestions:\n{matched_summary}\n\n"
                "Return ONLY a valid JSON array of LO code strings. "
                "If 'all' is selected, return all codes from the list above."
            )
        ),
    ] + list(messages[-4:]) + [
        HumanMessage(content=f"Teacher's selection: {last_user}"),
    ]

    response = await _invoke_llm(extraction_prompt, tag="selection_extraction", session=session)
    raw = response.content.strip()

    # Handle markdown code blocks
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    selected: list[dict] = []
    try:
        codes = json.loads(raw)
        if isinstance(codes, list):
            selected = [{"code": c} for c in codes]
    except (json.JSONDecodeError, TypeError):
        selected = [{"description": last_user}]

    # Look up full LO details from curriculum DB
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

    valid_enriched = [e for e in enriched if "name" in e and "code" in e]

    if not valid_enriched:
        _log_node(session, "handle_selection", "empty_extraction", user_message=last_user[:120])
        reply = AIMessage(
            content=(
                "I didn't quite catch which specific Learning Outcomes you wanted to select. "
                "Could you please let me know which ones from the list above you'd like to use "
                "(for example, by saying 'number 1' or 'both')?"
            )
        )
        session = {
            **session,
            "state": "domain_reasoning",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        return {
            "messages": [reply],
            "session": session,
            "selected_los": [],
        }

    lo_summary = "\n".join(
        f"- **[{e.get('code', 'N/A')}] {e.get('name', e.get('description', ''))}**\n"
        f"  {e.get('description', '')[:200]}"
        for e in valid_enriched
    )

    reply = AIMessage(
        content=(
            f"Great! You've selected the following Learning Outcomes:\n\n"
            f"{lo_summary}\n\n"
            "Would you like to:\n"
            "- **Confirm** this selection so I can retrieve relevant textbook content\n"
            "- **Modify** the selection (add or remove specific LOs)\n"
            "- **Go back** and explore different topics"
        )
    )

    session = {
        **session,
        "state": "topic_selection",
        "selected_los": valid_enriched,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "messages": [reply],
        "session": session,
        "selected_los": enriched,
    }


async def retrieve_content(state: AgentState) -> dict:
    """Retrieve textbook chunks for the selected LOs via targeted vector search.

    Uses LO codes for metadata filtering (precise) and LO code+name for
    vector queries (targeted) rather than sending the full user conversation
    to the embedding model.
    """
    session = state["session"]
    selected = state.get("selected_los", session.get("selected_los", []))
    _log_node(session, "retrieve_content", "enter", selected_count=len(selected))

    # Extract LO codes for metadata-based filtering
    lo_codes = [lo.get("code", "") for lo in selected if lo.get("code")]

    chunks: list[dict] = []
    if lo_codes:
        # Primary: search with metadata filtering by associated_lo_codes
        chunks = await search_chunks_by_lo_codes(lo_codes, top_k=3)

    if not chunks:
        # Fallback: search per-LO using code + name as targeted queries
        chunks = await search_chunks_per_lo(selected, top_k=3)

    _log_node(session, "retrieve_content", "retrieved", chunk_count=len(chunks), lo_codes=lo_codes)

    # Rerank: filter out off-topic chunks using a small LLM
    chunks = await rerank_chunks(chunks, selected)
    _log_node(session, "retrieve_content", "after_rerank", chunk_count=len(chunks))

    if not chunks:
        lo_labels = ", ".join(
            f"{lo.get('code', '')} ({lo.get('name', '')})"
            for lo in selected
        )
        reply = AIMessage(
            content=(
                f"I could not find any relevant textbook content for the "
                f"selected Learning Outcomes: {lo_labels}.\n\n"
                "This likely means the loaded textbook does not cover this "
                "topic. You can:\n"
                "- **Go back** and choose different Learning Outcomes\n"
                "- Ask an administrator to add textbook content for this topic"
            )
        )
        session = {
            **session,
            "state": "review_refinement",
            "retrieved_chunks": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        return {
            "messages": [reply],
            "session": session,
            "retrieved_chunks": [],
        }

    chunk_summaries = []
    for idx, ch in enumerate(chunks, 1):
        preview = ch.get("content", "")[:300]
        lo_tags = ", ".join(ch.get("associated_lo_codes", [])) or "General"
        chunk_summaries.append(
            f"**Chunk {idx}** (pages {ch.get('page_start')}–{ch.get('page_end')}, "
            f"LOs: {lo_tags}):\n{preview}…"
        )
    content_text = "\n\n".join(chunk_summaries)

    reply = AIMessage(
        content=(
            f"Here is the relevant textbook content for your selected LOs:\n\n"
            f"{content_text}\n\n"
            "Please review and let me know:\n"
            "- **Approve** to generate the assessment\n"
            "- **Reject** or request changes to refine the content"
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
    _log_node(session, "handle_refinement", "enter", message_count=len(messages))

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

    response = await _invoke_llm([sys_msg] + list(messages) + [refinement], tag="handle_refinement", session=session)

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
    _log_node(session, "generate_assessment", "enter", message_count=len(messages))

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

    response = await _invoke_llm([sys_msg] + list(messages[-4:]) + [gen_prompt], tag="generate_assessment", session=session)

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
