from __future__ import annotations

from typing import Any


def chunk_documents(
    pages: list[dict[str, Any]],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict[str, Any]]:
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    chunks: list[dict[str, Any]] = []
    for page in pages:
        text = " ".join(page["text"].split())
        if not text:
            continue

        words = text.split(" ")
        step = max(chunk_size - chunk_overlap, 1)
        for start in range(0, len(words), step):
            end = start + chunk_size
            chunk_words = words[start:end]
            if not chunk_words:
                continue
            chunk_text = " ".join(chunk_words)
            metadata = dict(page["metadata"])
            metadata["chunk_id"] = len(chunks)
            metadata["word_start"] = start
            metadata["word_end"] = min(end, len(words))
            chunks.append({"text": chunk_text, "metadata": metadata})

            if end >= len(words):
                break

    return chunks
