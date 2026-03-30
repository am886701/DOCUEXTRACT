from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True, encoding="utf-8-sig")


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


settings = Settings()

settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.vector_store_dir.mkdir(parents=True, exist_ok=True)
