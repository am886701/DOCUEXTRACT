import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile

from backend.config import settings
from backend.core.agentic_workflow import AgenticRAGService
from backend.core.auth import verify_api_key
from backend.core.models import AskRequest
from backend.document_loader import EmptyDocumentError, UnsupportedFileTypeError
from backend.rate_limit import limiter


logger = logging.getLogger(__name__)

router = APIRouter()
service = AgenticRAGService(settings=settings)


@router.get("/health")
def health() -> dict[str, object]:
    return service.get_health()


@router.get("/history", dependencies=[Depends(verify_api_key)])
def history(limit: int = Query(default=12, ge=1, le=50)) -> dict[str, object]:
    return service.get_history(limit=int(limit))


@router.post("/upload", dependencies=[Depends(verify_api_key)])
@limiter.limit("5/minute")
async def upload_document(request: Request, file: UploadFile = File(...)) -> dict[str, object]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in service.supported_file_types():
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {service.supported_file_types()}")

    raw_content = await file.read()
    if not raw_content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    size_mb = len(raw_content) / (1024 * 1024)
    if size_mb > settings.max_file_size_mb:
        raise HTTPException(status_code=400, detail=f"File exceeds {settings.max_file_size_mb} MB limit.")

    logger.info("Upload started: filename=%s, size=%.2fMB", file.filename, size_mb)

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(raw_content)
        temp_path = Path(temp_file.name)

    try:
        payload = service.ingest_file(temp_path, file.filename or temp_path.name)
        logger.info(
            "Upload complete: filename=%s, chunks=%d, duplicate=%s",
            file.filename,
            payload.get("chunks_added", 0),
            payload.get("duplicate", False),
        )
        return payload
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EmptyDocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Upload failed: filename=%s", file.filename)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)


@router.post("/ask", dependencies=[Depends(verify_api_key)])
@limiter.limit("10/minute")
def ask_question(request: Request, payload: AskRequest) -> dict[str, object]:
    question = payload.question
    logger.info("Question received: length=%d", len(question))
    try:
        result = service.answer_question(question)
        logger.info("Question answered: used_gemini=%s", result.get("used_gemini", False))
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
