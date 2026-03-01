"""Curriculum hierarchy models: Domain → Subdomain → Learning Outcome."""

from pydantic import BaseModel, Field


class LearningOutcome(BaseModel):
    """A single Learning Outcome with an enriched description for LLM reasoning."""

    code: str = Field(..., examples=["6.5.1.1.1"])
    name: str = Field(..., examples=["Cell structures"])
    description: str = Field(
        ...,
        description="Enriched explanation of the LO for semantic matching.",
    )
    subdomain_code: str = Field(..., examples=["1.1"])
    domain_code: str = Field(..., examples=["1"])


class Subdomain(BaseModel):
    """A subdomain grouping several Learning Outcomes."""

    code: str = Field(..., examples=["1.1"])
    name: str = Field(..., examples=["Structure & Function"])
    domain_code: str = Field(..., examples=["1"])
    learning_outcome_codes: list[str] = Field(default_factory=list)


class Domain(BaseModel):
    """A top-level curriculum domain."""

    code: str = Field(..., examples=["1"])
    name: str = Field(..., examples=["Life Sciences"])
    subdomain_codes: list[str] = Field(default_factory=list)
