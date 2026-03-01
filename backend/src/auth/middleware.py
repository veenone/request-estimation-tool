"""FastAPI middleware for authentication context propagation.

This module provides Starlette-compatible middleware that runs on every
request before it reaches the route handler.  The middleware does **not**
enforce authentication — that responsibility belongs to the dependency
injection helpers in ``dependencies.py``.  Instead it extracts contextual
information (client IP, etc.) and stores it on ``request.state`` so that
route handlers and the audit service can access it without re-parsing the
raw request.

Usage — register during app creation::

    from fastapi import FastAPI
    from .auth.middleware import AuthContextMiddleware

    app = FastAPI()
    app.add_middleware(AuthContextMiddleware)
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class AuthContextMiddleware(BaseHTTPMiddleware):
    """Middleware that extracts auth-related context and attaches it to the request.

    Attributes added to ``request.state``:

    - ``client_ip`` (``str | None``): The remote client IP address, taken
      from ``X-Forwarded-For`` when present (reverse-proxy deployments) and
      falling back to the direct connection address.  ``None`` when the
      client address is unavailable.

    This middleware is intentionally lightweight.  It performs no I/O and
    adds negligible latency to every request.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        """Populate ``request.state`` and forward the request.

        Args:
            request: The incoming Starlette/FastAPI request object.
            call_next: Callable that forwards the request to the next
                middleware or the route handler.

        Returns:
            The ``Response`` produced by the downstream handler.
        """
        # Prefer X-Forwarded-For when the application sits behind a reverse
        # proxy (nginx, Traefik, etc.) so that audit logs record the real
        # client IP rather than the proxy's loopback address.
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # The header may contain a comma-separated chain; the leftmost
            # address is the original client.
            request.state.client_ip = forwarded_for.split(",")[0].strip()
        elif request.client:
            request.state.client_ip = request.client.host
        else:
            request.state.client_ip = None

        response = await call_next(request)
        return response
