from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


logger = logging.getLogger(__name__)


@dataclass
class VectorStore:
    storage_dir: Path
    embedding_dim: int | None = None
    texts: list[str] = field(default_factory=list)
    metadatas: list[dict[str, Any]] = field(default_factory=list)
    _matrix: np.ndarray | None = None
    _faiss_index: Any = None

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._metadata_path = self.storage_dir / "store.json"
        self._index_path = self.storage_dir / "faiss.index"
        self._matrix_path = self.storage_dir / "embeddings.npy"
        self._load()
        logger.info("Vector store loaded: chunks=%d, path=%s", len(self.texts), self.storage_dir)

    def add(self, texts: list[str], embeddings: np.ndarray, metadatas: list[dict[str, Any]]) -> None:
        if len(texts) != len(metadatas) or len(texts) != len(embeddings):
            raise ValueError("texts, embeddings, and metadatas must have matching lengths")
        if len(texts) == 0:
            return

        embeddings = np.asarray(embeddings, dtype="float32")
        with self._lock:
            self.embedding_dim = embeddings.shape[1]
            self.texts.extend(texts)
            self.metadatas.extend(metadatas)

            if self._matrix is None:
                self._matrix = embeddings
            else:
                self._matrix = np.vstack([self._matrix, embeddings]).astype("float32")

            # P4.1 — Incremental FAISS add: if the index already exists and has
            # the right dimension, add only the new vectors instead of discarding
            # the whole index and rebuilding it from all vectors every time.
            self._add_to_index(embeddings)
            self._persist()
        logger.info("Vector store updated: chunks_added=%d, chunks_total=%d", len(texts), len(self.texts))

    def search(self, query_embedding: np.ndarray, top_k: int) -> list[dict[str, Any]]:
        if self._matrix is None or not self.texts:
            return []

        query = np.asarray(query_embedding, dtype="float32").reshape(1, -1)
        limit = min(top_k, len(self.texts))

        if self._faiss_index is not None:
            scores, indices = self._faiss_index.search(query, limit)
            ranked = zip(indices[0].tolist(), scores[0].tolist(), strict=False)
        else:
            similarities = self._matrix @ query.T
            ranked_indices = np.argsort(similarities[:, 0])[::-1][:limit]
            ranked = ((int(idx), float(similarities[idx, 0])) for idx in ranked_indices)

        results: list[dict[str, Any]] = []
        for idx, score in ranked:
            if idx < 0:
                continue
            results.append(
                {
                    "text": self.texts[idx],
                    "metadata": self.metadatas[idx],
                    "score": score,
                }
            )
        return results

    def stats(self) -> dict[str, Any]:
        documents = sorted({metadata["document"] for metadata in self.metadatas})
        return {
            "chunks": len(self.texts),
            "documents": documents,
        }

    def _load(self) -> None:
        if self._metadata_path.exists():
            payload = json.loads(self._metadata_path.read_text(encoding="utf-8"))
            self.texts = payload.get("texts", [])
            self.metadatas = payload.get("metadatas", [])
            self.embedding_dim = payload.get("embedding_dim")

        if self._matrix_path.exists():
            self._matrix = np.load(self._matrix_path).astype("float32")
        elif self.texts:
            self._matrix = None

        if self._matrix is not None:
            self._load_index()

    # ------------------------------------------------------------------
    # P4.1 — Incremental FAISS index management
    # ------------------------------------------------------------------

    def _load_index(self) -> None:
        """Load a persisted FAISS index from disk on startup."""
        try:
            import faiss

            if self._index_path.exists():
                self._faiss_index = faiss.read_index(str(self._index_path))
                logger.info("FAISS index loaded from disk: vectors=%d", self._faiss_index.ntotal)
            else:
                # No saved index — build one from the full matrix (first boot / migration)
                self._rebuild_index_from_matrix()
        except Exception:
            logger.warning("FAISS index load failed; using brute-force search", exc_info=True)
            self._faiss_index = None

    def _add_to_index(self, new_embeddings: np.ndarray) -> None:
        """Incrementally add new vectors to the existing FAISS index.

        If no FAISS index exists yet (e.g. faiss is unavailable, or first add),
        falls back to a full rebuild from the complete matrix.
        """
        try:
            import faiss

            if self._faiss_index is not None:
                # Happy path: just add the new vectors — O(n_new) not O(n_total)
                self._faiss_index.add(new_embeddings)
            else:
                # First add or previous failure — build from scratch
                self._rebuild_index_from_matrix()
        except Exception:
            logger.warning("FAISS incremental add failed; rebuilding from matrix", exc_info=True)
            self._rebuild_index_from_matrix()

    def _rebuild_index_from_matrix(self) -> None:
        """Full index rebuild from self._matrix — used on first boot or recovery."""
        if self._matrix is None:
            self._faiss_index = None
            return
        try:
            import faiss

            index = faiss.IndexFlatIP(self._matrix.shape[1])
            index.add(self._matrix)
            self._faiss_index = index
            logger.info("FAISS index rebuilt from matrix: vectors=%d", index.ntotal)
        except Exception:
            logger.warning("FAISS index rebuild failed; using brute-force search", exc_info=True)
            self._faiss_index = None

    # ------------------------------------------------------------------
    # P4.2 — Atomic persistence (temp-file + os.replace)
    # ------------------------------------------------------------------

    def _persist(self) -> None:
        """Write all store data atomically so a mid-write crash cannot corrupt files.

        Strategy:
        - Write to a sibling temp file in the same directory (same filesystem,
          so os.replace is guaranteed to be atomic on Linux/POSIX).
        - Rename over the target once the write completes successfully.
        - On failure the temp file is removed and the original is left intact.
        """
        storage_dir = str(self.storage_dir)

        # 1. Atomic JSON metadata write
        payload = {
            "texts": self.texts,
            "metadatas": self.metadatas,
            "embedding_dim": self.embedding_dim,
        }
        tmp_fd, tmp_path = tempfile.mkstemp(dir=storage_dir, suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            os.replace(tmp_path, str(self._metadata_path))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        # 2. Atomic numpy matrix write
        if self._matrix is not None:
            tmp_fd2, tmp_npy = tempfile.mkstemp(dir=storage_dir, suffix=".tmp.npy")
            try:
                os.close(tmp_fd2)
                np.save(tmp_npy, self._matrix)
                os.replace(tmp_npy, str(self._matrix_path))
            except Exception:
                try:
                    os.unlink(tmp_npy)
                except OSError:
                    pass
                raise

        # 3. Atomic FAISS index write
        if self._faiss_index is not None:
            import faiss

            tmp_fd3, tmp_idx = tempfile.mkstemp(dir=storage_dir, suffix=".tmp.index")
            try:
                os.close(tmp_fd3)
                faiss.write_index(self._faiss_index, tmp_idx)
                os.replace(tmp_idx, str(self._index_path))
            except Exception:
                try:
                    os.unlink(tmp_idx)
                except OSError:
                    pass
                raise
