from collections.abc import Awaitable, Callable
import secrets

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import Settings


class BrowserSecurityMiddleware(BaseHTTPMiddleware):
    """Validate browser mutation origins and attach conservative headers."""

    def __init__(self, app: Callable, settings: Settings) -> None:
        super().__init__(app)
        self._enabled = settings.csrf_origin_check_enabled
        self._allowed_origin = str(settings.frontend_url).rstrip("/")
        self._require_proxy_secret = settings.require_proxy_secret
        self._proxy_secret = settings.proxy_shared_secret.get_secret_value() if settings.proxy_shared_secret else ""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if self._enabled and request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin", "").rstrip("/")
            if origin != self._allowed_origin:
                return JSONResponse(status_code=403, content={"detail": "Request origin is not allowed"})
        if self._require_proxy_secret and request.method not in {"GET", "HEAD", "OPTIONS"}:
            supplied = request.headers.get("x-cinequote-proxy-secret", "")
            if not self._proxy_secret or not secrets.compare_digest(supplied, self._proxy_secret):
                return JSONResponse(status_code=403, content={"detail": "Request proxy is not allowed"})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        return response
