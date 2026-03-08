"""Single /answer/ endpoint — the core conversational API."""

from __future__ import annotations

from datetime import datetime, timezone
import logging

from fastapi import APIRouter, HTTPException
from langchain_core.messages import AIMessage, HumanMessage

from src.agent.graph import graph
from src.agent.state import AgentState
from src.database import (
    domains_col,
    learning_outcomes_col,
    sessions_col,
    subdomains_col,
)
from src.models.api import AnswerRequest, AnswerResponse
from src.models.session import Message, Session, SessionState

router = APIRouter(tags=["answer"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _load_curriculum_context() -> str:
    """Build a human-readable curriculum string for injection into prompts."""
    domains = await domains_col.find().to_list(length=100)
    subdomains = await subdomains_col.find().to_list(length=100)
    los = await learning_outcomes_col.find().to_list(length=200)

    sub_map: dict[str, list] = {}
    for lo in los:
        sub_map.setdefault(lo["subdomain_code"], []).append(lo)

    lines: list[str] = []
    for domain in sorted(domains, key=lambda d: d["code"]):
        lines.append(f"\n### Domain {domain['code']}: {domain['name']}")
        for sub in sorted(subdomains, key=lambda s: s["code"]):
            if sub["domain_code"] != domain["code"]:
                continue
            lines.append(f"  **{sub['code']} {sub['name']}**")
            for lo in sub_map.get(sub["code"], []):
                lines.append(
                    f"    - [{lo['code']}] {lo['name']}: {lo['description']}"
                )
    return "\n".join(lines)


def _session_to_messages(session: Session) -> list[HumanMessage | AIMessage]:
    """Convert stored session messages to LangChain message objects."""
    lc_msgs: list[HumanMessage | AIMessage] = []
    for m in session.messages:
        if m.role == "user":
            lc_msgs.append(HumanMessage(content=m.content))
        elif m.role == "assistant":
            lc_msgs.append(AIMessage(content=m.content))
    return lc_msgs


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/answer/", response_model=AnswerResponse)
async def answer(req: AnswerRequest) -> AnswerResponse:
    """
    Accept a user message, run the LangGraph agent, persist the updated
    session, and return the agent's response.
    """

    # 1. Load or create session -----------------------------------------------
    if req.session_id:
        doc = await sessions_col.find_one({"session_id": req.session_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Session not found.")
        doc.pop("_id", None)
        session = Session(**doc)
    else:
        session = Session()

    logger.info(
        "[answer] session=%s incoming state=%s message=%s",
        session.session_id,
        session.state,
        req.message[:200],
    )

    # 2. Append the incoming user message -------------------------------------
    session.messages.append(
        Message(role="user", content=req.message)
    )

    # 3. Build LangGraph initial state ----------------------------------------
    curriculum_ctx = await _load_curriculum_context()
    lc_messages = _session_to_messages(session)

    initial_state: AgentState = {
        "messages": lc_messages,
        "session": session.model_dump(mode="json"),
        "conversation_summary": session.summary or "",
        "curriculum_context": curriculum_ctx,
        "matched_los": session.matched_los,
        "selected_los": session.selected_los,
        "retrieved_chunks": session.retrieved_chunks,
        "assessment": session.generated_assessment or "",
    }

    # 4. Invoke the graph -----------------------------------------------------
    result = await graph.ainvoke(initial_state)
    logger.info(
        "[answer] session=%s graph_complete result_state=%s",
        session.session_id,
        result.get("session", {}).get("state", session.state),
    )

    # 5. Extract the agent's reply --------------------------------------------
    agent_reply = ""
    result_messages = result.get("messages", [])
    if result_messages:
        last_msg = result_messages[-1]
        if isinstance(last_msg, AIMessage):
            agent_reply = last_msg.content

    if not agent_reply:
        agent_reply = "I'm sorry, I didn't quite understand that. Could you rephrase?"

    # 6. Update session from graph result -------------------------------------
    updated_session_dict = result.get("session", session.model_dump(mode="json"))
    # Remove internal routing key
    updated_session_dict.pop("_next", None)

    session.state = SessionState(updated_session_dict.get("state", session.state))
    session.matched_los = updated_session_dict.get("matched_los", session.matched_los)
    session.selected_los = result.get("selected_los", updated_session_dict.get("selected_los", session.selected_los))
    session.retrieved_chunks = result.get("retrieved_chunks", updated_session_dict.get("retrieved_chunks", session.retrieved_chunks))
    session.generated_assessment = updated_session_dict.get("generated_assessment", session.generated_assessment)
    # Persist any updated conversation summary and its metadata produced by the graph
    updated_summary = updated_session_dict.get("conversation_summary")
    if updated_summary is not None:
        session.summary = updated_summary
    last_at = updated_session_dict.get("last_summary_at")
    if last_at:
        try:
            session.last_summary_at = datetime.fromisoformat(last_at)
        except Exception:
            session.last_summary_at = session.last_summary_at
    session.last_summary_msg_count = updated_session_dict.get("last_summary_msg_count", session.last_summary_msg_count)
    # Persist archived messages if the graph returned them
    if "archived_messages" in updated_session_dict:
        session.archived_messages = updated_session_dict.get("archived_messages", session.archived_messages)
    session.updated_at = datetime.now(timezone.utc)

    # Append agent reply to message history
    session.messages.append(
        Message(role="assistant", content=agent_reply)
    )

    # 7. Persist session to MongoDB -------------------------------------------
    await sessions_col.update_one(
        {"session_id": session.session_id},
        {"$set": session.model_dump(mode="json")},
        upsert=True,
    )
    logger.info(
        "[answer] session=%s persisted state=%s messages=%s",
        session.session_id,
        session.state,
        len(session.messages),
    )

    # 8. Build structured data payload ----------------------------------------
    data: dict | None = None
    if session.state == SessionState.DOMAIN_REASONING:
        data = {"matched_los": session.matched_los}
    elif session.state == SessionState.TOPIC_SELECTION:
        data = {"selected_los": session.selected_los}
    elif session.state == SessionState.REVIEW_REFINEMENT:
        data = {
            "selected_los": session.selected_los,
            "retrieved_chunks": [
                {k: v for k, v in ch.items() if k != "embedding"}
                for ch in session.retrieved_chunks
            ],
        }
    elif session.state == SessionState.COMPLETE:
        data = {"assessment": session.generated_assessment}

    return AnswerResponse(
        session_id=session.session_id,
        response=agent_reply,
        state=session.state,
        data=data,
    )
