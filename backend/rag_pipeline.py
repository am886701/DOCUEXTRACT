from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.chunking import chunk_documents
from backend.config import Settings
from backend.database import AppDatabase
from backend.document_loader import EmptyDocumentError, load_document
from backend.embeddings import build_embedding_backend
from backend.vector_store import VectorStore


UUID_PREFIX_PATTERN = re.compile(r"^[0-9a-f]{32}_(.+)$")


@dataclass
class RAGPipeline:
    settings: Settings

    def __post_init__(self) -> None:
        self.vector_store = VectorStore(self.settings.vector_store_dir)
        self.embedding_backend = build_embedding_backend(self.settings.embedding_model)
        self.app_database = AppDatabase(self.settings.sqlite_db_path)
        self._sync_existing_documents()

    def ingest_file(self, source_path: Path, filename: str) -> dict[str, Any]:
        content_hash = self._hash_file(source_path)
        existing_document = self.app_database.find_document_by_hash(content_hash)
        if existing_document is not None:
            return {
                "document_id": existing_document["id"],
                "filename": existing_document["original_name"],
                "stored_as": existing_document["stored_name"],
                "chunks_added": 0,
                "stats": self.vector_store.stats(),
                "duplicate": True,
                "message": "This document was already indexed earlier, so the existing index was reused.",
            }

        safe_name = f"{uuid4().hex}_{filename}"
        destination = self.settings.upload_dir / safe_name
        shutil.copy2(source_path, destination)

        try:
            pages = load_document(destination, display_name=filename)
            chunks = chunk_documents(
                pages,
                chunk_size=self.settings.chunk_size,
                chunk_overlap=self.settings.chunk_overlap,
            )
            if not chunks:
                raise ValueError("No extractable text was found in the uploaded document.")

            texts = [chunk["text"] for chunk in chunks]
            metadatas = [chunk["metadata"] for chunk in chunks]
            embeddings = self.embedding_backend.encode(texts)
            self.vector_store.add(texts, embeddings, metadatas)

            document_id = self.app_database.log_document(
                original_name=filename,
                stored_name=safe_name,
                source_type=destination.suffix.lower().lstrip("."),
                file_size_bytes=destination.stat().st_size,
                chunk_count=len(chunks),
                content_hash=content_hash,
            )
        except Exception:
            destination.unlink(missing_ok=True)
            raise

        return {
            "document_id": document_id,
            "filename": filename,
            "stored_as": safe_name,
            "chunks_added": len(chunks),
            "stats": self.vector_store.stats(),
            "duplicate": False,
        }

    def answer_question(self, question: str) -> dict[str, Any]:
        question = question.strip()
        if not question:
            raise ValueError("Question cannot be empty.")

        results = self.retrieve(question)
        if not results:
            answer = "I could not find any indexed content yet. Upload a document first."
            self.app_database.log_question(question=question, answer=answer, used_gemini=False, sources=[])
            return {
                "answer": answer,
                "sources": [],
                "context": [],
            }

        answer, used_gemini = self._generate_answer(question, results)
        sources = self._build_sources(results)
        question_id = self.app_database.log_question(
            question=question,
            answer=answer,
            used_gemini=used_gemini,
            sources=results,
        )
        return {
            "question_id": question_id,
            "answer": answer,
            "sources": sources,
            "context": results,
            "used_gemini": used_gemini,
        }

    def retrieve(self, question: str) -> list[dict[str, Any]]:
        query_embedding = self.embedding_backend.encode([question])[0]
        return self.vector_store.search(query_embedding, self.settings.retrieval_k)

    def _generate_answer(self, question: str, retrieved_chunks: list[dict[str, Any]]) -> tuple[str, bool]:
        prompt = self._build_prompt(question, retrieved_chunks)
        if self.settings.google_api_key:
            try:
                from google import genai

                client = genai.Client(api_key=self.settings.google_api_key)
                response = client.models.generate_content(
                    model=self.settings.gemini_model,
                    contents=prompt,
                )
                text = (response.text or "").strip()
                if text:
                    return text, True
            except Exception as exc:
                return self._fallback_answer(question, retrieved_chunks, error=str(exc)), False

        return self._fallback_answer(question, retrieved_chunks), False

    def _build_prompt(self, question: str, retrieved_chunks: list[dict[str, Any]]) -> str:
        context_parts: list[str] = []
        for chunk in retrieved_chunks:
            metadata = chunk["metadata"]
            source = f'{self._display_document_name(metadata)} (page {metadata.get("page", 1)})'
            context_parts.append(f"Source: {source}\nContent: {chunk['text']}")

        context = "\n\n".join(context_parts)
        return (
            "You are a helpful RAG question answering assistant.\n"
            "Answer the question only using the provided context.\n"
            "If the answer is not supported by the context, say so clearly.\n"
            "Cite supporting sources inline using the source names exactly as provided.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}"
        )

    def _fallback_answer(
        self,
        question: str,
        retrieved_chunks: list[dict[str, Any]],
        *,
        error: str | None = None,
    ) -> str:
        lead = retrieved_chunks[0]
        metadata = lead["metadata"]
        source = f'{self._display_document_name(metadata)} (page {metadata.get("page", 1)})'
        snippet = lead["text"][:700].strip()

        answer = (
            "LLM generation is unavailable, so this is a retrieval-only answer.\n\n"
            f"Best matching source: {source}\n"
            f"Question: {question}\n"
            f"Relevant excerpt: {snippet}"
        )
        if error:
            answer += f"\n\nModel error: {error}"
        elif not self.settings.google_api_key:
            answer += "\n\nSet GOOGLE_API_KEY or GEMINI_API_KEY in your environment or .env to enable the full agentic workflow with Gemini-generated answers."
        return answer

    def _build_sources(self, retrieved_chunks: list[dict[str, Any]]) -> list[str]:
        seen: set[str] = set()
        sources: list[str] = []
        for chunk in retrieved_chunks:
            metadata = chunk["metadata"]
            label = f'{self._display_document_name(metadata)} - Page {metadata.get("page", 1)}'
            if label not in seen:
                seen.add(label)
                sources.append(label)
        return sources

    def _display_document_name(self, metadata: dict[str, Any]) -> str:
        display_name = str(metadata.get("display_document") or "").strip()
        if display_name:
            return display_name

        raw_name = str(metadata.get("document") or "Document").strip()
        match = UUID_PREFIX_PATTERN.match(raw_name)
        if match:
            return match.group(1)
        return raw_name

    def _sync_existing_documents(self) -> None:
        grouped_documents: dict[str, dict[str, Any]] = {}
        for metadata in self.vector_store.metadatas:
            stored_name = str(metadata.get("document") or "").strip()
            if not stored_name or stored_name in grouped_documents:
                continue

            file_path = self.settings.upload_dir / stored_name
            grouped_documents[stored_name] = {
                "original_name": self._display_document_name(metadata),
                "stored_name": stored_name,
                "source_type": str(metadata.get("source_type") or file_path.suffix.lower().lstrip(".")),
                "file_size_bytes": file_path.stat().st_size if file_path.exists() else 0,
                "chunk_count": 0,
                "content_hash": self._hash_file(file_path) if file_path.exists() else "",
            }

        for metadata in self.vector_store.metadatas:
            stored_name = str(metadata.get("document") or "").strip()
            if stored_name in grouped_documents:
                grouped_documents[stored_name]["chunk_count"] += 1

        for document in grouped_documents.values():
            self.app_database.log_document(**document)

    def _hash_file(self, file_path: Path) -> str:
        digest = hashlib.sha256()
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


def supported_file_types() -> tuple[str, ...]:
    return (".pdf", ".docx", ".txt")
