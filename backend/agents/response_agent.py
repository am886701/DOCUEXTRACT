from __future__ import annotations

from typing import Any

from backend.core.llm_factory import extract_text
from backend.core.models import AgenticRAGState
from backend.rag_pipeline import RAGPipeline

import logging
logger = logging.getLogger(__name__)


class ResponseAgent:
    def __init__(self, llm: Any | None, pipeline: RAGPipeline) -> None:
        self.llm = llm
        self.pipeline = pipeline

    def run(self, state: AgenticRAGState) -> AgenticRAGState:
        retrieved_chunks = state.get("retrieved_chunks", [])
        workflow_steps = [*state.get("workflow_steps", []), "Response agent generated the final answer."]

        if not retrieved_chunks:
            return {
                "answer": "I could not find any indexed content yet. Upload a document first.",
                "used_gemini": False,
                "workflow_steps": workflow_steps,
            }

        if self.llm is None:
            answer = self.pipeline.fallback_answer(state["question"], retrieved_chunks)
            return {
                "answer": answer,
                "used_gemini": False,
                "workflow_steps": workflow_steps,
            }

        context = self._build_context(retrieved_chunks)
        prompt = (
            "You are the Response Agent in an agentic RAG system. "
            "Use the reasoning plan, summarized evidence, and retrieved context to answer the user accurately. "
            "Cite sources inline using the exact source names provided in the context. "
            "If the evidence is insufficient, say so clearly.\n\n"
            f"Question: {state['question']}\n\n"
            f"Reasoning Plan:\n{state.get('reasoning', '')}\n\n"
            f"Summary:\n{state.get('summary', '')}\n\n"
            f"Retrieved Context:\n{context}"
        )
        try:
            response = self.llm.invoke(prompt)
            answer = extract_text(response) or self.pipeline.fallback_answer(state["question"], retrieved_chunks)
            return {
                "answer": answer,
                "used_gemini": True,
                "workflow_steps": workflow_steps,
            }
        except Exception:
            logger.exception("Response agent failed to generate an answer")
            errors = [*state.get("errors", []), "Response agent fallback: generation failed."]
            return {
                "answer": self.pipeline.fallback_answer(state["question"], retrieved_chunks, error="Generation failed."),
                "used_gemini": False,
                "workflow_steps": workflow_steps,
                "errors": errors,
                "provider": "heuristic-fallback",
            }

    def _build_context(self, chunks: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for chunk in chunks:
            metadata = chunk["metadata"]
            source = f"{self.pipeline.display_document_name(metadata)} (page {metadata.get('page', 1)})"
            parts.append(f"Source: {source}\nContent: {chunk['text']}")
        return "\n\n".join(parts)
