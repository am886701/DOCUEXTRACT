from __future__ import annotations

import json
import re
from typing import Any

from backend.core.llm_factory import extract_text
from backend.core.models import AgenticRAGState


class ReasoningAgent:
    def __init__(self, llm: Any | None) -> None:
        self.llm = llm

    def run(self, state: AgenticRAGState) -> AgenticRAGState:
        question = state["question"]
        workflow_steps = [*state.get("workflow_steps", []), "Reasoning agent analyzed the query."]

        if self.llm is None:
            return self._fallback(question, workflow_steps, provider="heuristic-fallback")

        prompt = (
            "You are the Reasoning Agent in an agentic RAG system. "
            "Analyze the user's question and decide how retrieval and answering should proceed. "
            "Return valid JSON with keys reasoning, retrieval_query, and response_strategy.\n\n"
            f"Question: {question}"
        )
        try:
            response = self.llm.invoke(prompt)
            raw_text = extract_text(response)
            data = self._parse_json(raw_text)
            if data:
                return {
                    "reasoning": data.get("reasoning") or "Use retrieved evidence to answer with citations.",
                    "retrieval_query": data.get("retrieval_query") or question,
                    "response_strategy": data.get("response_strategy") or "answer_with_citations",
                    "workflow_steps": workflow_steps,
                    "provider": "gemini",
                }
        except Exception as exc:
            errors = [*state.get("errors", []), f"Reasoning agent fallback: {exc}"]
            fallback = self._fallback(question, workflow_steps, provider="heuristic-fallback")
            fallback["errors"] = errors
            return fallback

        return self._fallback(question, workflow_steps, provider="heuristic-fallback")

    def _fallback(self, question: str, workflow_steps: list[str], provider: str) -> AgenticRAGState:
        return {
            "reasoning": "Use semantic retrieval to gather the most relevant chunks, summarize evidence, and answer with citations.",
            "retrieval_query": question,
            "response_strategy": "answer_with_citations",
            "workflow_steps": workflow_steps,
            "provider": provider,
        }

    def _parse_json(self, raw_text: str) -> dict[str, str]:
        fenced = re.search(r"\{.*\}", raw_text, re.DOTALL)
        candidate = fenced.group(0) if fenced else raw_text
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            return {}
        if isinstance(payload, dict):
            return {str(key): str(value) for key, value in payload.items()}
        return {}
