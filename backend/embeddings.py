from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np


class EmbeddingBackend:
    def encode(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError


@dataclass(slots=True)
class SentenceTransformerBackend(EmbeddingBackend):
    model_name: str

    def __post_init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(self.model_name)

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return np.asarray(vectors, dtype="float32")


@dataclass(slots=True)
class HashEmbeddingBackend(EmbeddingBackend):
    dimension: int = 384

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dimension), dtype="float32")
        for row, text in enumerate(texts):
            for token in text.lower().split():
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimension
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vectors[row, index] += sign

        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms


def build_embedding_backend(model_name: str) -> EmbeddingBackend:
    try:
        return SentenceTransformerBackend(model_name=model_name)
    except Exception:
        return HashEmbeddingBackend()
