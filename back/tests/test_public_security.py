from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.config import Settings
from app.middleware.security import BrowserSecurityMiddleware
from app.repositories.sessions import InMemorySessionRepository, QuizSession
from app.services.security import KeyedRateLimiter, SecurityLimiters, client_ip


def request(ip: str = "203.0.113.10", headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": headers or [], "client": (ip, 1234)})


def test_keyed_rate_limiter_isolated_keys_and_retry_after() -> None:
    now = [100.0]
    limiter = KeyedRateLimiter(2, 60, clock=lambda: now[0])
    assert limiter.check("account-a") == (True, 0)
    assert limiter.check("account-a") == (True, 0)
    allowed, retry = limiter.check("account-a")
    assert allowed is False and retry == 60
    assert limiter.check("account-b") == (True, 0)
    now[0] += 61
    assert limiter.check("account-a") == (True, 0)


def test_login_is_limited_by_account_even_when_ip_changes() -> None:
    settings = Settings(login_rate_limit_ip_requests=100, login_rate_limit_account_requests=2)
    limiters = SecurityLimiters(settings)
    limiters.check_login(request("203.0.113.1"), "Player@Example.com")
    limiters.check_login(request("203.0.113.2"), "player@example.com")
    try:
        limiters.check_login(request("203.0.113.3"), "PLAYER@example.com")
        raise AssertionError("expected account limiter")
    except Exception as error:
        assert getattr(error, "status_code", None) == 429
        assert getattr(error, "headers", {}).get("Retry-After")


def test_ai_is_limited_across_new_sessions_by_ip() -> None:
    settings = Settings(ai_ip_rate_limit_requests=2, ai_user_rate_limit_requests=100)
    limiters = SecurityLimiters(settings)
    limiters.check_ai(request(), user_id=None)
    limiters.check_ai(request(), user_id=None)
    try:
        limiters.check_ai(request(), user_id=None)
        raise AssertionError("expected IP limiter")
    except Exception as error:
        assert getattr(error, "status_code", None) == 429


def test_quiz_sessions_expire_and_oldest_is_evicted() -> None:
    now = [0.0]
    repository = InMemorySessionRepository(ttl_seconds=10, max_sessions=2, clock=lambda: now[0])
    repository.add(QuizSession(id="one", questions=[]))
    now[0] = 1
    repository.add(QuizSession(id="two", questions=[]))
    now[0] = 2
    repository.add(QuizSession(id="three", questions=[]))
    assert repository.get("one") is None
    assert len(repository) == 2
    now[0] = 12
    assert repository.get("two") is None
    assert repository.get("three") is None


def test_origin_check_rejects_cross_site_mutations() -> None:
    application = FastAPI()
    application.add_middleware(BrowserSecurityMiddleware, settings=Settings(
        frontend_url="https://cinequote.example", csrf_origin_check_enabled=True,
    ))

    @application.post("/change")
    def change() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(application)
    assert client.post("/change", headers={"Origin": "https://evil.example"}).status_code == 403
    allowed = client.post("/change", headers={"Origin": "https://cinequote.example"})
    assert allowed.status_code == 200
    assert allowed.headers["x-frame-options"] == "DENY"


def test_forwarded_ip_requires_proxy_secret() -> None:
    headers = [(b"x-forwarded-for", b"198.51.100.7"), (b"x-cinequote-proxy-secret", b"correct")]
    trusted = Settings(trust_proxy_headers=True, proxy_shared_secret="correct")
    assert client_ip(request(headers=headers), trusted) == "198.51.100.7"
    assert client_ip(request(headers=headers), Settings(trust_proxy_headers=True, proxy_shared_secret="wrong")) == "203.0.113.10"


def test_required_proxy_secret_blocks_direct_mutations() -> None:
    application = FastAPI()
    application.add_middleware(BrowserSecurityMiddleware, settings=Settings(
        proxy_shared_secret="shared-secret", require_proxy_secret=True,
    ))

    @application.post("/change")
    def change() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(application)
    assert client.post("/change").status_code == 403
    assert client.post("/change", headers={"X-CineQuote-Proxy-Secret": "shared-secret"}).status_code == 200
