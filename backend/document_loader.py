from __future__ import annotations

from pathlib import Path
from typing import Any


class UnsupportedFileTypeError(ValueError):
    pass


class EmptyDocumentError(ValueError):
    pass


def load_document(file_path: Path, display_name: str | None = None) -> list[dict[str, Any]]:
    display_name = display_name or file_path.name
    suffix = file_path.suffix.lower()
    if suffix == ".txt":
        return _load_txt(file_path, display_name)
    if suffix == ".pdf":
        return _load_pdf(file_path, display_name)
    if suffix == ".docx":
        return _load_docx(file_path, display_name)
    raise UnsupportedFileTypeError(f"Unsupported file type: {suffix}")


def _load_txt(file_path: Path, display_name: str) -> list[dict[str, Any]]:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    if not text.strip():
        raise EmptyDocumentError("The TXT file is empty.")
    return [
        {
            "text": text,
            "metadata": {
                "document": file_path.name,
                "display_document": display_name,
                "page": 1,
                "source_type": "txt",
            },
        }
    ]


def _load_pdf(file_path: Path, display_name: str) -> list[dict[str, Any]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required to process PDF files.") from exc

    reader = PdfReader(str(file_path))
    pages: list[dict[str, Any]] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(
                {
                    "text": text,
                    "metadata": {
                        "document": file_path.name,
                        "display_document": display_name,
                        "page": index,
                        "source_type": "pdf",
                    },
                }
            )
    if not pages:
        raise EmptyDocumentError(
            "No extractable text was found in this PDF. It may be scanned or image-based and require OCR."
        )
    return pages


def _load_docx(file_path: Path, display_name: str) -> list[dict[str, Any]]:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("python-docx is required to process DOCX files.") from exc

    document = Document(str(file_path))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())
    if not text.strip():
        raise EmptyDocumentError("The DOCX file does not contain any readable paragraph text.")
    return [
        {
            "text": text,
            "metadata": {
                "document": file_path.name,
                "display_document": display_name,
                "page": 1,
                "source_type": "docx",
            },
        }
    ]
