from pathlib import Path
import random

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database import Base, create_database_engine
from app.models.account import User
from app.services.auth import AccountConflictError, AuthService, InvalidCredentialsError
from app.services.security import SecurityLimiters
from app.config import Settings
from app.services.stats import StatsService
from app.repositories.questions import JsonQuestionRepository
from app.repositories.sessions import InMemorySessionRepository
from app.schemas.quiz import AnswerSubmission
from app.services.quiz import QuizService
from app.main import app
import app.api.routes.auth as auth_routes
import app.services.auth as auth_module


@pytest.fixture
def account_factory(tmp_path: Path) -> sessionmaker:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'accounts.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_registration_login_cookie_session_and_logout(account_factory: sessionmaker) -> None:
    service = AuthService(account_factory)
    user, token = service.register("Player@Example.com", "MovieFan", "strong-pass-123")

    assert user.password_hash != "strong-pass-123"
    assert service.resolve(token).id == user.id  # type: ignore[union-attr]
    logged_in, second_token = service.login("player@example.com", "strong-pass-123")
    assert logged_in.id == user.id
    assert second_token != token

    service.logout(token)
    assert service.resolve(token) is None
    with pytest.raises(InvalidCredentialsError):
        service.login("player@example.com", "wrong")
    with pytest.raises(AccountConflictError):
        service.register("PLAYER@example.com", "AnotherName", "strong-pass-123")


def test_statistics_are_aggregated_and_attempts_are_idempotent(account_factory: sessionmaker) -> None:
    with account_factory() as database:
        user = User(email="a@example.com", normalized_email="a@example.com", username="Player", normalized_username="player", password_hash="not-used")
        database.add(user); database.commit(); user_id = user.id

    service = StatsService(account_factory)
    service.record(user_id=user_id, session_id="session-1", genre="horror", difficulty="easy", score=8, total=10, hints_used=1)
    service.record(user_id=user_id, session_id="session-1", genre="horror", difficulty="easy", score=8, total=10, hints_used=1)
    service.record(user_id=user_id, session_id="session-2", genre="horror", difficulty="hard", score=6, total=10, hints_used=0)

    stats = service.get(user_id)
    assert stats.games_played == 2
    assert stats.average_percentage == 70
    assert stats.best_percentage == 80
    assert stats.accuracy_percentage == 70
    assert stats.hints_used == 1
    assert stats.by_genre[0].games_played == 2
    assert len(stats.recent_attempts) == 2


def test_auth_http_cookie_flow(account_factory: sessionmaker, monkeypatch: pytest.MonkeyPatch) -> None:
    service = AuthService(account_factory)
    monkeypatch.setattr(auth_routes, "auth_service", service)
    monkeypatch.setattr(auth_module, "auth_service", service)
    with TestClient(app) as client:
        registered = client.post("/auth/register", json={
            "email": "film@example.com", "username": "FilmFan", "password": "cinema-pass-123",
        })
        assert registered.status_code == 201
        assert registered.json()["username"] == "FilmFan"
        assert "cinequote_session" in registered.cookies
        assert client.get("/auth/me").status_code == 200
        assert client.post("/auth/logout").status_code == 204
        assert client.get("/auth/me").status_code == 401
        assert client.post("/ai/coach").status_code == 401


def test_auth_http_abuse_limits_and_secure_cookie(account_factory: sessionmaker, monkeypatch: pytest.MonkeyPatch) -> None:
    service = AuthService(account_factory)
    settings = Settings(
        auth_cookie_secure=True, auth_cookie_samesite="strict",
        register_rate_limit_ip_requests=1, login_rate_limit_ip_requests=100,
        login_rate_limit_account_requests=2,
    )
    monkeypatch.setattr(auth_routes, "auth_service", service)
    monkeypatch.setattr(auth_routes, "security_limiters", SecurityLimiters(settings))
    monkeypatch.setattr(auth_routes, "get_settings", lambda: settings)
    with TestClient(app) as client:
        registered = client.post("/auth/register", json={
            "email": "secure@example.com", "username": "SecureFan", "password": "cinema-pass-123",
        })
        cookie = registered.headers["set-cookie"].lower()
        assert "httponly" in cookie and "secure" in cookie and "samesite=strict" in cookie
        assert client.post("/auth/register", json={
            "email": "other@example.com", "username": "OtherFan", "password": "cinema-pass-123",
        }).status_code == 429

        for _ in range(2):
            response = client.post("/auth/login", json={"email": "secure@example.com", "password": "wrong"})
            assert response.status_code == 401
            assert response.json()["detail"] == "Invalid email or password"
        limited = client.post("/auth/login", json={"email": "SECURE@example.com", "password": "wrong"})
        assert limited.status_code == 429
        assert "Retry-After" in limited.headers


def test_completed_signed_in_quiz_is_added_to_statistics(account_factory: sessionmaker) -> None:
    with account_factory() as database:
        user = User(email="q@example.com", normalized_email="q@example.com", username="Quizzer", normalized_username="quizzer", password_hash="unused")
        database.add(user); database.commit(); user_id = user.id
    repository = JsonQuestionRepository()
    answers = {question.id: question.film_title for question in repository.list_all()}
    stats = StatsService(account_factory)
    service = QuizService(repository, InMemorySessionRepository(), random.Random(4), statistics=stats)
    created = service.create_session("easy", user_id=user_id)
    for _ in range(10):
        question = service.get_current_question(created.session_id)
        service.submit_answer(created.session_id, AnswerSubmission(question_id=question.id, answer=answers[question.id]))
    result = stats.get(user_id)
    assert result.games_played == 1
    assert result.best_percentage == 100
    assert result.recent_attempts[0].difficulty == "easy"
