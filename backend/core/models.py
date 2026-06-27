from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field, field_validator


class AgenticRAGState(TypedDict, total=False):
    question: str
    reasoning: str
    retrieval_query: str
    response_strategy: str
    summary: str
    answer: str
    sources: list[str]
    retrieved_chunks: list[dict[str, Any]]
    workflow_steps: list[str]
    used_gemini: bool
    provider: str
    errors: list[str]


class AskRequest(BaseModel):
    """Validated request body for the /ask endpoint."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The question to ask about uploaded documents",
        examples=["What are the key responsibilities in this document?"],
    )

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        question = value.strip()
        if not question:
            raise ValueError("Question cannot be blank")
        return question
