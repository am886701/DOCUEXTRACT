from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


logger = logging.getLogger(__name__)


BASE_DIR = Path(__file__).resolve().parent.parent
# Runtime environment variables (including ECS-injected secrets) take priority
# over local development values from .env.
load_dotenv(BASE_DIR / ".env", override=False, encoding="utf-8-sig")


def _get_env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip().strip("\"'") if isinstance(value, str) else default


def _get_google_api_key() -> str:
    for key_name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GEMINT_API_KEY"):
        value = _get_env(key_name)
        if value:
            return value
    return ""


@dataclass(slots=True)
class Settings:
    app_name: str = "Agentic RAG System"
    google_api_key: str = _get_google_api_key()
    gemini_model: str = _get_env("GEMINI_MODEL", "gemini-2.5-flash")
    upload_dir: Path = BASE_DIR / "uploads"
    vector_store_dir: Path = BASE_DIR / "database"
    sqlite_db_path: Path = BASE_DIR / "database" / "app.db"
    embedding_model: str = _get_env("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    chunk_size: int = int(_get_env("CHUNK_SIZE", "500"))
    chunk_overlap: int = int(_get_env("CHUNK_OVERLAP", "50"))
    retrieval_k: int = int(_get_env("RETRIEVAL_K", "4"))
    max_file_size_mb: int = int(_get_env("MAX_FILE_SIZE_MB", "20"))
    allowed_origins: list[str] = field(default_factory=lambda: [
        origin.strip()
        for origin in _get_env("ALLOWED_ORIGINS", "http://localhost:8000").split(",")
        if origin.strip()
    ])
    app_api_key: str = _get_env("APP_API_KEY", "dev-secret-key")
    llm_timeout_seconds: int = int(_get_env("LLM_TIMEOUT_SECONDS", "60"))
    # How long to keep raw uploaded files in uploads/.
    # -1 = keep forever (default; safe for development and single-node).
    #  0 = delete immediately after successful indexing (saves disk, no recovery possible).
    # >0 = delete files older than this many days (swept on each app startup).
    upload_retention_days: int = int(_get_env("UPLOAD_RETENTION_DAYS", "-1"))
    graceful_timeout_seconds: int = int(_get_env("GRACEFUL_TIMEOUT_SECONDS", "30"))

settings = Settings()

settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.vector_store_dir.mkdir(parents=True, exist_ok=True)

if not settings.google_api_key:
    logger.warning(
        "No GOOGLE_API_KEY found. The app will run in fallback mode "
        "(heuristic answers without Gemini). Set GOOGLE_API_KEY or "
        "GEMINI_API_KEY in the environment or .env file."
    )
