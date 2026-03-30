from __future__ import annotations

from typing import Any

from backend.core.llm_factory import extract_text
from backend.core.models import AgenticRAGState
from backend.rag_pipeline import RAGPipeline


class SummarizerAgent:
    def __init__(self, llm: Any | None, pipeline: RAGPipeline) -> None:
        self.llm = llm
        self.pipeline = pipeline

    def run(self, state: AgenticRAGState) -> AgenticRAGState:
        retrieved_chunks = state.get("retrieved_chunks", [])
        workflow_steps = [*state.get("workflow_steps", []), "Summarizer agent condensed the retrieved evidence."]

        if not retrieved_chunks:
            return {
                "summary": "No relevant document context was retrieved.",
                "workflow_steps": workflow_steps,
            }

        context = self._build_context(retrieved_chunks)
        if self.llm is None:
            return {
                "summary": self._fallback_summary(retrieved_chunks),
                "workflow_steps": workflow_steps,
            }

        prompt = (
            "You are the Summarization Agent in an agentic RAG workflow. "
            "Summarize the retrieved document evidence into concise bullet points that will help answer the user. "
            "Focus on facts and preserve source grounding.\n\n"
            f"Question: {state['question']}\n\nRetrieved Context:\n{context}"
        )
        try:
            response = self.llm.invoke(prompt)
            summary = extract_text(response) or self._fallback_summary(retrieved_chunks)
        except Exception as exc:
            errors = [*state.get("errors", []), f"Summarizer agent fallback: {exc}"]
            return {
                "summary": self._fallback_summary(retrieved_chunks),
                "workflow_steps": workflow_steps,
                "errors": errors,
            }

        return {
            "summary": summary,
            "workflow_steps": workflow_steps,
        }

    def _build_context(self, chunks: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for chunk in chunks:
            metadata = chunk["metadata"]
            source = f"{self.pipeline._display_document_name(metadata)} (page {metadata.get('page', 1)})"
            parts.append(f"Source: {source}\nContent: {chunk['text']}")
        return "\n\n".join(parts)

    def _fallback_summary(self, retrieved_chunks: list[dict[str, Any]]) -> str:
        excerpts = [chunk["text"][:240].strip() for chunk in retrieved_chunks[:3]]
        return "\n".join(f"- {excerpt}" for excerpt in excerpts if excerpt) or "Relevant chunks were found but could not be summarized."
