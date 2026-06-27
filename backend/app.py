from __future__ import annotations

import logging

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


app = FastAPI(title=settings.app_name)
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
logger.info("Application initialized: name=%s", settings.app_name)

frontend_dir = BASE_DIR / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
def serve_frontend() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")
