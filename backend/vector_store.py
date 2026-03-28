from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class VectorStore:
    storage_dir: Path
    embedding_dim: int | None = None
    texts: list[str] = field(default_factory=list)
    metadatas: list[dict[str, Any]] = field(default_factory=list)
    _matrix: np.ndarray | None = None
    _faiss_index: Any = None

    def __post_init__(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._metadata_path = self.storage_dir / "store.json"
        self._index_path = self.storage_dir / "faiss.index"
        self._matrix_path = self.storage_dir / "embeddings.npy"
        self._load()

    def add(self, texts: list[str], embeddings: np.ndarray, metadatas: list[dict[str, Any]]) -> None:
        if len(texts) != len(metadatas) or len(texts) != len(embeddings):
            raise ValueError("texts, embeddings, and metadatas must have matching lengths")
        if len(texts) == 0:
            return

        embeddings = np.asarray(embeddings, dtype="float32")
        self.embedding_dim = embeddings.shape[1]
        self.texts.extend(texts)
        self.metadatas.extend(metadatas)

        if self._matrix is None:
            self._matrix = embeddings
        else:
            self._matrix = np.vstack([self._matrix, embeddings]).astype("float32")

        self._rebuild_index()
        self._persist()

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
            self._rebuild_index(load_only=True)

    def _persist(self) -> None:
        payload = {
            "texts": self.texts,
            "metadatas": self.metadatas,
            "embedding_dim": self.embedding_dim,
        }
        self._metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if self._matrix is not None:
            np.save(self._matrix_path, self._matrix)
        if self._faiss_index is not None:
            import faiss

            faiss.write_index(self._faiss_index, str(self._index_path))

    def _rebuild_index(self, load_only: bool = False) -> None:
        if self._matrix is None:
            self._faiss_index = None
            return
        try:
            import faiss

            if load_only and self._index_path.exists():
                self._faiss_index = faiss.read_index(str(self._index_path))
                return

            index = faiss.IndexFlatIP(self._matrix.shape[1])
            index.add(self._matrix)
            self._faiss_index = index
        except Exception:
            self._faiss_index = None
