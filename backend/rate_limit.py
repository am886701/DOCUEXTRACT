"""Rate limiting configuration — separated to avoid circular imports."""
from __future__ import annotations

import logging

from slowapi import Limiter
from slowapi.util import get_remote_address


logger = logging.getLogger(__name__)

# get_remote_address extracts the user's IP address from each request.
# This means limits are per-IP — each unique IP gets its own counter.
limiter = Limiter(key_func=get_remote_address)
logger.info("Per-IP rate limiter configured")
