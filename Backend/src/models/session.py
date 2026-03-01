"""Conversation session models for stateful agent interactions."""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class SessionState(str, Enum):
    """Tracks the user's position in the abstract flow."""

    GREETING = "greeting"
    TOPIC_IDENTIFICATION = "topic_identification"
    DOMAIN_REASONING = "domain_reasoning"
    TOPIC_SELECTION = "topic_selection"
    CONTENT_RETRIEVAL = "content_retrieval"
    REVIEW_REFINEMENT = "review_refinement"
    ASSESSMENT_GENERATION = "assessment_generation"
    COMPLETE = "complete"


class Message(BaseModel):
    """A single message in the conversation history."""

    role: str = Field(..., description="user | assistant | system")
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Session(BaseModel):
    """Persistent conversation session stored in MongoDB."""

    session_id: str = Field(default_factory=lambda: uuid4().hex)
    state: SessionState = SessionState.GREETING
    messages: list[Message] = Field(default_factory=list)

    # Discovery phase
    identified_topics: list[str] = Field(default_factory=list)
    matched_los: list[dict] = Field(default_factory=list)

    # Selection phase
    selected_los: list[dict] = Field(default_factory=list)
    retrieved_chunks: list[dict] = Field(default_factory=list)
    rejected_chunks: list[dict] = Field(default_factory=list)

    # Generation phase
    generated_assessment: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
