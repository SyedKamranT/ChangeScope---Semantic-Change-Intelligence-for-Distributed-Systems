"""HTTP middleware for request correlation IDs and distributed tracing context."""

import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable for request correlation ID across async coroutines
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id_ctx", default="")


def get_correlation_id() -> str:
    """Returns the current request correlation ID."""
    return correlation_id_ctx.get()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Intercepts requests to extract or generate an X-Request-ID, binding it to structlog and response headers."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # Read incoming request correlation header or generate fresh UUIDv4
        req_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")
        if not req_id:
            req_id = str(uuid.uuid4())

        token = correlation_id_ctx.set(req_id)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=req_id, path=request.url.path, method=request.method)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            correlation_id_ctx.reset(token)
