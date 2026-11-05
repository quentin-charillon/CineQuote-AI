"""Process-local abuse controls for the first single-worker deployment.

These controls intentionally keep no credentials or raw account identifiers.
They reset on restart and must be replaced by shared storage before scaling to
multiple workers or instances.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict, deque
from threading import RLock
from time import monotonic
from typing import Callable

from fastapi import HTTPException, Request, status

from app.config import Settings, get_settings


class KeyedRateLimiter:
    def __init__(self, limit: int, window_seconds: int, clock: Callable[[], float] = monotonic, max_keys: int = 10_000) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = RLock()
        self._max_keys = max_keys

    def check(self, key: str) -> tuple[bool, int]:
        now = self._clock()
        cutoff = now - self.window_seconds
        with self._lock:
            if key not in self._requests and len(self._requests) >= self._max_keys:
                oldest_key = min(self._requests, key=lambda item: self._requests[item][-1] if self._requests[item] else 0)
                del self._requests[oldest_key]
            bucket = self._requests[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False, max(1, round(bucket[0] + self.window_seconds - now))
            bucket.append(now)
            return True, 0

    def clear(self) -> None:
        with self._lock:
            self._requests.clear()


def private_key(value: str) -> str:
    """Keep emails, session ids, and tokens out of in-memory limiter keys."""
    return hashlib.sha256(value.strip().casefold().encode()).hexdigest()


def client_ip(request: Request, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    supplied_secret = request.headers.get("x-cinequote-proxy-secret", "")
    expected_secret = settings.proxy_shared_secret.get_secret_value() if settings.proxy_shared_secret else ""
    trusted_proxy = settings.trust_proxy_headers and expected_secret and supplied_secret == expected_secret
    if trusted_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def reject_rate_limit(retry_after: int, detail: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=detail,
        headers={"Retry-After": str(retry_after)},
    )


class SecurityLimiters:
    def __init__(self, settings: Settings) -> None:
        self.login_ip = KeyedRateLimiter(settings.login_rate_limit_ip_requests, settings.login_rate_limit_window_seconds)
        self.login_account = KeyedRateLimiter(settings.login_rate_limit_account_requests, settings.login_rate_limit_window_seconds)
        self.register_ip = KeyedRateLimiter(settings.register_rate_limit_ip_requests, settings.register_rate_limit_window_seconds)
        self.ai_user = KeyedRateLimiter(settings.ai_user_rate_limit_requests, settings.ai_rate_limit_window_seconds)
        self.ai_ip = KeyedRateLimiter(settings.ai_ip_rate_limit_requests, settings.ai_rate_limit_window_seconds)

    def check_login(self, request: Request, email: str) -> None:
        checks = (
            self.login_ip.check(client_ip(request)),
            self.login_account.check(private_key(email)),
        )
        denied = [retry for allowed, retry in checks if not allowed]
        if denied:
            reject_rate_limit(max(denied), "Too many sign-in attempts. Please wait and try again.")

    def check_registration(self, request: Request) -> None:
        allowed, retry = self.register_ip.check(client_ip(request))
        if not allowed:
            reject_rate_limit(retry, "Too many account creation attempts. Please wait and try again.")

    def check_ai(self, request: Request, user_id: int | None = None) -> None:
        checks = [self.ai_ip.check(client_ip(request))]
        if user_id is not None:
            checks.append(self.ai_user.check(str(user_id)))
        denied = [retry for allowed, retry in checks if not allowed]
        if denied:
            reject_rate_limit(max(denied), "This feature has reached its usage limit. Please try again later.")


security_limiters = SecurityLimiters(get_settings())
