from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from backend.config import settings
from backend.core.agentic_workflow import AgenticRAGService
from backend.document_loader import EmptyDocumentError, UnsupportedFileTypeError


router = APIRouter()
service = AgenticRAGService(settings=settings)


@router.get("/health")
def health() -> dict[str, object]:
    return service.get_health()


@router.get("/history")
def history(limit: int = Query(default=12, ge=1, le=50)) -> dict[str, object]:
    return service.get_history(limit=int(limit))


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)) -> dict[str, object]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in service.supported_file_types():
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {service.supported_file_types()}")

    raw_content = await file.read()
    if not raw_content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    size_mb = len(raw_content) / (1024 * 1024)
    if size_mb > settings.max_file_size_mb:
        raise HTTPException(status_code=400, detail=f"File exceeds {settings.max_file_size_mb} MB limit.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(raw_content)
        temp_path = Path(temp_file.name)

    try:
        return service.ingest_file(temp_path, file.filename or temp_path.name)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EmptyDocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)


@router.post("/ask")
def ask_question(payload: dict[str, str]) -> dict[str, object]:
    question = (payload.get("question") or "").strip()
    try:
        return service.answer_question(question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
