from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.config import BASE_DIR, settings
from backend.document_loader import EmptyDocumentError, UnsupportedFileTypeError
from backend.rag_pipeline import RAGPipeline, supported_file_types


app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = RAGPipeline(settings=settings)


class AskRequest(BaseModel):
    question: str


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "index": pipeline.vector_store.stats(),
        "database": pipeline.app_database.stats(),
    }


@app.get("/history")
def history(limit: int = Query(default=12, ge=1, le=50)) -> dict[str, object]:
    safe_limit = int(limit)
    return {"items": pipeline.app_database.get_recent_questions(limit=safe_limit)}


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)) -> dict[str, object]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in supported_file_types():
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {supported_file_types()}")

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
        return pipeline.ingest_file(temp_path, file.filename or temp_path.name)
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


@app.post("/ask")
def ask_question(payload: AskRequest) -> dict[str, object]:
    try:
        return pipeline.answer_question(payload.question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


frontend_dir = BASE_DIR / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
def serve_frontend() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")
