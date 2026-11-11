"""HTTP middleware for request correlation IDs, security headers, and timeout control."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

import structlog
from fastapi import status
from fastapi.responses import JSONResponse
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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces defense-in-depth HTTP response security headers."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        response.headers["X-XSS-Protection"] = "0"
        return response


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """Guards against hung requests by enforcing an async processing deadline."""

    def __init__(self, app: Any, timeout_seconds: float = 30.0) -> None:
        super().__init__(app)
        self.timeout_seconds = timeout_seconds

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        try:
            async with asyncio.timeout(self.timeout_seconds):
                return await call_next(request)
        except TimeoutError:
            from packages.shared.errors import ProblemDetail

            problem = ProblemDetail(
                type="https://changescope.io/errors/gateway-timeout",
                title="Gateway Timeout",
                status=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Request processing exceeded deadline of {self.timeout_seconds}s.",
                instance=str(request.url),
                request_id=get_correlation_id(),
            )
            return JSONResponse(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                content=problem.model_dump(exclude_none=True),
                media_type="application/problem+json",
            )
