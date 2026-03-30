from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from backend.agents.reasoning_agent import ReasoningAgent
from backend.agents.response_agent import ResponseAgent
from backend.agents.retrieval_agent import RetrievalAgent
from backend.agents.summarizer_agent import SummarizerAgent
from backend.config import Settings
from backend.core.llm_factory import LLMFactory
from backend.core.models import AgenticRAGState
from backend.rag_pipeline import RAGPipeline, supported_file_types


class AgenticRAGService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.pipeline = RAGPipeline(settings=settings)
        self.chat_model = LLMFactory.build_chat_model(settings)
        self.reasoning_agent = ReasoningAgent(self.chat_model)
        self.retrieval_agent = RetrievalAgent(self.pipeline)
        self.summarizer_agent = SummarizerAgent(self.chat_model, self.pipeline)
        self.response_agent = ResponseAgent(self.chat_model, self.pipeline)
        self.graph = self._build_graph()

    def ingest_file(self, source_path, filename: str) -> dict[str, object]:
        return self.pipeline.ingest_file(source_path, filename)

    def answer_question(self, question: str) -> dict[str, object]:
        question = question.strip()
        if not question:
            raise ValueError("Question cannot be empty.")

        state = self.graph.invoke(
            {
                "question": question,
                "workflow_steps": [],
                "errors": [],
            }
        )
        retrieved_chunks = state.get("retrieved_chunks", [])
        answer = state.get("answer") or "I could not generate an answer."
        used_gemini = bool(state.get("used_gemini", False))
        question_id = self.pipeline.app_database.log_question(
            question=question,
            answer=answer,
            used_gemini=used_gemini,
            sources=retrieved_chunks,
        )
        return {
            "question_id": question_id,
            "answer": answer,
            "sources": state.get("sources", []),
            "summary": state.get("summary", ""),
            "reasoning": state.get("reasoning", ""),
            "workflow_steps": state.get("workflow_steps", []),
            "context": retrieved_chunks,
            "used_gemini": used_gemini,
            "provider": state.get("provider", "heuristic-fallback"),
        }

    def get_health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "index": self.pipeline.vector_store.stats(),
            "database": self.pipeline.app_database.stats(),
            "agentic": {
                "framework": "langgraph",
                "provider": "gemini" if self.chat_model is not None else "heuristic-fallback",
                "agents": [
                    "reasoning_agent",
                    "retrieval_agent",
                    "summarizer_agent",
                    "response_agent",
                ],
            },
        }

    def get_history(self, limit: int = 12) -> dict[str, object]:
        return {"items": self.pipeline.app_database.get_recent_questions(limit=limit)}

    def supported_file_types(self) -> tuple[str, ...]:
        return supported_file_types()

    def _build_graph(self):
        builder = StateGraph(AgenticRAGState)
        builder.add_node("reasoning", self.reasoning_agent.run)
        builder.add_node("retrieval", self.retrieval_agent.run)
        builder.add_node("summarization", self.summarizer_agent.run)
        builder.add_node("response", self.response_agent.run)

        builder.add_edge(START, "reasoning")
        builder.add_edge("reasoning", "retrieval")
        builder.add_conditional_edges(
            "retrieval",
            self._route_after_retrieval,
            {
                "summarization": "summarization",
                "response": "response",
            },
        )
        builder.add_edge("summarization", "response")
        builder.add_edge("response", END)
        return builder.compile()

    def _route_after_retrieval(self, state: AgenticRAGState) -> str:
        return "summarization" if state.get("retrieved_chunks") else "response"
