"""Textbook chunk model stored alongside its vector embedding."""

from pydantic import BaseModel, Field


class TextbookChunk(BaseModel):
    """A chunk of textbook content with an optional embedding vector."""

    chunk_id: str = Field(..., examples=["c15"])
    content: str
    page_start: int = 0
    page_end: int = 0
    embedding: list[float] | None = Field(
        default=None,
        description="1536-dim embedding from text-embedding-3-small",
    )
    associated_lo_codes: list[str] = Field(
        default_factory=list,
        description="LO codes this chunk is relevant to (optional enrichment).",
    )
