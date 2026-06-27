from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Header, HTTPException

from backend.config import settings


logger = logging.getLogger(__name__)

async def verify_api_key(
    x_api_key: Annotated[str | None, Header(description="API Key for authentication")] = None
) -> None:
    if not x_api_key or x_api_key != settings.app_api_key:
        logger.warning("API authentication failed")
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-API-Key header"
        )
