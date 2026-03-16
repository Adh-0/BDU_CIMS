"""
middleware.py — Request validation and logging for the API.
"""

import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.time()

        response = await call_next(request)

        duration_ms = (time.time() - start) * 1000
        logger.info(
            f"{request.method} {request.url.path} → {response.status_code} "
            f"({duration_ms:.0f}ms)"
        )
        return response
