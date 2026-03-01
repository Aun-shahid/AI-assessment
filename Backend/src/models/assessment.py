"""Assessment output models."""

from pydantic import BaseModel, Field


class Question(BaseModel):
    """A single generated assessment question."""

    question_text: str
    question_type: str = Field(..., description="MCQ or Short")
    options: list[str] | None = Field(
        default=None, description="Answer options for MCQ questions."
    )
    correct_answer: str
    lo_code: str
    domain: str
    subdomain: str


class Assessment(BaseModel):
    """A complete assessment consisting of multiple questions."""

    questions: list[Question] = Field(default_factory=list)
    metadata: dict = Field(
        default_factory=dict,
        description="Summary of domain/LO coverage.",
    )
