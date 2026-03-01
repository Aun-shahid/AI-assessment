"""Request / response schemas for the answer endpoint."""

from pydantic import BaseModel, Field

from src.models.session import SessionState


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
