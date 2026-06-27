FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/home/appuser/.cache/huggingface

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libgomp1 curl \
    && useradd --create-home --user-group --shell /usr/sbin/nologin appuser \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && python -m pip install -r /app/requirements.txt

COPY --chown=appuser:appuser backend /app/backend
COPY --chown=appuser:appuser frontend /app/frontend

RUN mkdir -p /app/uploads /app/database "$HF_HOME" \
    && chown -R appuser:appuser /app/uploads /app/database /home/appuser

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["gunicorn", "backend.app:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-"]
