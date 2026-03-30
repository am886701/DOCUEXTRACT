from __future__ import annotations

from typing import Any, TypedDict


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
