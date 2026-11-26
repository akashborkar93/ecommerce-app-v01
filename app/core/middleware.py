import logging
import time
import uuid

from fastapi import Request, Response

from app.core.errors import error_response
from app.core.logging import request_id_var

logger = logging.getLogger("app.request")

_PROBE_PATHS = {"/health", "/ready"}


async def request_context_middleware(request: Request, call_next) -> Response:
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    token = request_id_var.set(request_id)
    start = time.perf_counter()
    path = request.url.path
    # Load balancer probes hit these constantly; keep them out of INFO logs.
    level = logging.DEBUG if path in _PROBE_PATHS else logging.INFO
    try:
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error(
                "unhandled exception",
                exc_info=True,
                extra={"method": request.method, "path": path, "error_type": type(exc).__name__},
            )
            response = error_response(500, "internal_error", "Internal server error")
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logger.log(
            level,
            "request completed",
            extra={
                "method": request.method,
                "path": path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
    finally:
        request_id_var.reset(token)
