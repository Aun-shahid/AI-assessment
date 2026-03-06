"""Session CRUD endpoints — list, create, get, and delete sessions."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.database import sessions_col
from src.models.api import (
    CreateSessionResponse,
    SessionDetailResponse,
    SessionListResponse,
    SessionSummary,
)
from src.models.session import Session

router = APIRouter(prefix="/sessions", tags=["sessions"])


# ---------------------------------------------------------------------------
# POST /sessions/ — create a new empty session
# ---------------------------------------------------------------------------

@router.post("/", response_model=CreateSessionResponse, status_code=201)
async def create_session() -> CreateSessionResponse:
    """
    Create a brand-new session (triggered by the "+" button on the frontend).
    The session starts in the GREETING state with an empty message history.
    """
    session = Session()
    await sessions_col.insert_one(session.model_dump(mode="json"))

    return CreateSessionResponse(
        session_id=session.session_id,
        state=session.state,
    )


# ---------------------------------------------------------------------------
# GET /sessions/ — list all sessions (paginated, most recent first)
# ---------------------------------------------------------------------------

@router.get("/", response_model=SessionListResponse)
async def list_sessions(
    skip: int = Query(default=0, ge=0, description="Number of sessions to skip."),
    limit: int = Query(default=20, ge=1, le=100, description="Max sessions to return."),
) -> SessionListResponse:
    """
    Return a paginated list of session summaries sorted by most recently
    updated.  Each summary includes a short preview of the last message.
    """
    total = await sessions_col.count_documents({})

    cursor = (
        sessions_col.find({}, {"_id": 0})
        .sort("updated_at", -1)
        .skip(skip)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)

    summaries: list[SessionSummary] = []
    for doc in docs:
        # Build a short preview from the last message (if any)
        last_preview: str | None = None
        messages = doc.get("messages", [])
        if messages:
            content = messages[-1].get("content", "")
            last_preview = content[:100] + ("…" if len(content) > 100 else "")

        summaries.append(
            SessionSummary(
                session_id=doc["session_id"],
                state=doc["state"],
                created_at=doc["created_at"],
                updated_at=doc["updated_at"],
                last_message_preview=last_preview,
            )
        )

    return SessionListResponse(total=total, sessions=summaries)


# ---------------------------------------------------------------------------
# GET /sessions/{session_id} — full session detail
# ---------------------------------------------------------------------------

@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str) -> SessionDetailResponse:
    """Load the full session including all messages, LOs, chunks, and assessment."""
    doc = await sessions_col.find_one({"session_id": session_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found.")

    doc.pop("_id", None)
    session = Session(**doc)

    # Strip embedding vectors from chunks to keep the response light
    clean_chunks = [
        {k: v for k, v in ch.items() if k != "embedding"}
        for ch in session.retrieved_chunks
    ]

    return SessionDetailResponse(
        session_id=session.session_id,
        state=session.state,
        messages=session.messages,
        identified_topics=session.identified_topics,
        matched_los=session.matched_los,
        selected_los=session.selected_los,
        retrieved_chunks=clean_chunks,
        rejected_chunks=session.rejected_chunks,
        generated_assessment=session.generated_assessment,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


# ---------------------------------------------------------------------------
# DELETE /sessions/{session_id} — remove a session
# ---------------------------------------------------------------------------

@router.delete("/{session_id}", status_code=200)
async def delete_session(session_id: str) -> dict:
    """Delete a session by ID. Returns 404 if the session doesn't exist."""
    result = await sessions_col.delete_one({"session_id": session_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found.")

    return {"detail": "Session deleted."}
