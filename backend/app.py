from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.logging_config import setup_logging

setup_logging()

from backend.api.routes import router
from backend.config import BASE_DIR, settings
from backend.rate_limit import limiter


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan context manager.

    Everything before `yield` runs on startup; everything after runs on
    shutdown.  Using the lifespan pattern (instead of the deprecated
    @app.on_event decorators) gives Gunicorn / ECS a clear hook to log
    the shutdown phase and finish any in-flight work before the process
    exits.  The actual graceful-timeout window is controlled by Gunicorn's
    --graceful-timeout 30 flag (set in the Dockerfile CMD).
    """
    # ── startup ──────────────────────────────────────────────────────────
    logger.info("Application startup: name=%s, origins=%s", settings.app_name, settings.allowed_origins)
    yield
    # ── shutdown ─────────────────────────────────────────────────────────
    logger.info(
        "Graceful shutdown initiated — Gunicorn will wait up to %ds for "
        "in-flight requests to complete before force-killing the worker.",
        30,  # mirrors --graceful-timeout in Dockerfile CMD
    )


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda req, exc: exc.response())
app.add_middleware(SlowAPIMiddleware)

app.include_router(router)

frontend_dir = BASE_DIR / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
def serve_frontend() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")
