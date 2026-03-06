"""Request / response schemas for the API."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.models.session import Message, SessionState


# ---------------------------------------------------------------------------
# Answer endpoint
# ---------------------------------------------------------------------------

class AnswerRequest(BaseModel):
    """Payload sent by the client to the /answer/ endpoint."""

    session_id: str | None = Field(
        default=None,
        description="Omit or null to start a new session.",
    )
    message: str = Field(..., min_length=1, description="User message text.")


class AnswerResponse(BaseModel):
    """Payload returned to the client from the /answer/ endpoint."""

    session_id: str
    response: str = Field(..., description="Agent reply text.")
    state: SessionState
    data: dict | None = Field(
        default=None,
        description=(
            "Optional structured payload — e.g. suggested LOs, "
            "retrieved chunks, or the generated assessment."
        ),
    )


# ---------------------------------------------------------------------------
# Session endpoints
# ---------------------------------------------------------------------------

class SessionSummary(BaseModel):
    """Lightweight session info for the list view."""

    session_id: str
    state: SessionState
    created_at: datetime
    updated_at: datetime
    last_message_preview: str | None = Field(
        default=None,
        description="Truncated content of the most recent message (≤100 chars).",
    )


class SessionListResponse(BaseModel):
    """Paginated list of sessions."""

    total: int = Field(..., description="Total number of sessions in the database.")
    sessions: list[SessionSummary]


class SessionDetailResponse(BaseModel):
    """Full session data returned when loading a specific session."""

    session_id: str
    state: SessionState
    messages: list[Message]
    identified_topics: list[str] = Field(default_factory=list)
    matched_los: list[dict] = Field(default_factory=list)
    selected_los: list[dict] = Field(default_factory=list)
    retrieved_chunks: list[dict] = Field(default_factory=list)
    rejected_chunks: list[dict] = Field(default_factory=list)
    generated_assessment: str | None = None
    created_at: datetime
    updated_at: datetime


class CreateSessionResponse(BaseModel):
    """Returned after creating a brand-new session."""

    session_id: str
    state: SessionState
