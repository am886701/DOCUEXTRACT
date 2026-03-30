from __future__ import annotations

from backend.core.models import AgenticRAGState
from backend.rag_pipeline import RAGPipeline


class RetrievalAgent:
    def __init__(self, pipeline: RAGPipeline) -> None:
        self.pipeline = pipeline

    def run(self, state: AgenticRAGState) -> AgenticRAGState:
        retrieval_query = state.get("retrieval_query") or state["question"]
        retrieved_chunks = self.pipeline.retrieve(retrieval_query)
        workflow_steps = [*state.get("workflow_steps", []), f"Retrieval agent fetched {len(retrieved_chunks)} chunk(s)."]

        return {
            "retrieved_chunks": retrieved_chunks,
            "sources": self.pipeline._build_sources(retrieved_chunks),
            "workflow_steps": workflow_steps,
        }
