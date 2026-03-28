from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class AppDatabase:
    db_path: Path

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        self._migrate()

    def log_document(
        self,
        *,
        original_name: str,
        stored_name: str,
        source_type: str,
        file_size_bytes: int,
        chunk_count: int,
        content_hash: str,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO documents (
                    original_name,
                    stored_name,
                    source_type,
                    file_size_bytes,
                    chunk_count,
                    content_hash
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (original_name, stored_name, source_type, file_size_bytes, chunk_count, content_hash),
            )
            if cursor.lastrowid:
                connection.commit()
                return int(cursor.lastrowid)

            row = connection.execute(
                "SELECT id FROM documents WHERE stored_name = ?",
                (stored_name,),
            ).fetchone()
            connection.commit()
            return int(row[0])

    def find_document_by_hash(self, content_hash: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, original_name, stored_name, source_type, file_size_bytes, chunk_count, created_at
                FROM documents
                WHERE content_hash = ?
                LIMIT 1
                """,
                (content_hash,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": int(row["id"]),
            "original_name": str(row["original_name"]),
            "stored_name": str(row["stored_name"]),
            "source_type": str(row["source_type"]),
            "file_size_bytes": int(row["file_size_bytes"]),
            "chunk_count": int(row["chunk_count"]),
            "created_at": str(row["created_at"]),
        }

    def log_question(
        self,
        *,
        question: str,
        answer: str,
        used_gemini: bool,
        sources: list[dict[str, Any]],
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO questions (
                    question,
                    answer,
                    used_gemini
                )
                VALUES (?, ?, ?)
                """,
                (question, answer, int(used_gemini)),
            )
            question_id = int(cursor.lastrowid)

            seen_sources: set[tuple[str, int, str]] = set()
            for source in sources:
                metadata = source["metadata"]
                document_name = str(metadata.get("display_document") or metadata.get("document") or "Document")
                page = int(metadata.get("page", 1))
                excerpt = str(source.get("text", ""))[:1000]
                source_key = (document_name, page, excerpt)
                if source_key in seen_sources:
                    continue
                seen_sources.add(source_key)

                connection.execute(
                    """
                    INSERT INTO question_sources (
                        question_id,
                        document_name,
                        page,
                        score,
                        excerpt
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        question_id,
                        document_name,
                        page,
                        float(source.get("score", 0.0)),
                        excerpt,
                    ),
                )

            connection.commit()
            return question_id

    def get_recent_questions(self, limit: int = 12) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, question, answer, used_gemini, created_at
                FROM questions
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

            history: list[dict[str, Any]] = []
            for row in rows:
                sources = connection.execute(
                    """
                    SELECT document_name, page, score, excerpt
                    FROM question_sources
                    WHERE question_id = ?
                    ORDER BY score DESC, id ASC
                    """,
                    (row["id"],),
                ).fetchall()
                history.append(
                    {
                        "id": int(row["id"]),
                        "question": str(row["question"]),
                        "answer": str(row["answer"]),
                        "used_gemini": bool(row["used_gemini"]),
                        "created_at": str(row["created_at"]),
                        "sources": [
                            {
                                "document_name": str(source["document_name"]),
                                "page": int(source["page"]),
                                "score": float(source["score"]),
                                "excerpt": str(source["excerpt"]),
                            }
                            for source in sources
                        ],
                    }
                )
        return history

    def stats(self) -> dict[str, int]:
        with self._connect() as connection:
            documents_count = int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
            questions_count = int(connection.execute("SELECT COUNT(*) FROM questions").fetchone()[0])
            source_rows_count = int(connection.execute("SELECT COUNT(*) FROM question_sources").fetchone()[0])
        return {
            "documents": documents_count,
            "questions": questions_count,
            "source_rows": source_rows_count,
        }

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_name TEXT NOT NULL,
                    stored_name TEXT NOT NULL UNIQUE,
                    source_type TEXT NOT NULL,
                    file_size_bytes INTEGER NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    content_hash TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    used_gemini INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS question_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL,
                    document_name TEXT NOT NULL,
                    page INTEGER NOT NULL,
                    score REAL NOT NULL,
                    excerpt TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (question_id) REFERENCES questions (id) ON DELETE CASCADE
                );
                """
            )
            connection.commit()

    def _migrate(self) -> None:
        with self._connect() as connection:
            columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(documents)").fetchall()}
            if "content_hash" not in columns:
                connection.execute("ALTER TABLE documents ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash)")
            connection.commit()
