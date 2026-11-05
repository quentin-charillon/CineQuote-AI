import json
from pathlib import Path

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import create_database_engine
from app.models.account import User
from app.models.catalog import Film, Quote
from app.services.auth import AuthService
from app.services.stats import StatsService
from scripts.bootstrap_database import DEFAULT_CATALOG, bootstrap


def test_render_postgres_url_uses_psycopg_three_without_connecting() -> None:
    settings = Settings(database_url="postgresql://movie_user:p%40ss@db.internal/cinequote", _env_file=None)
    assert settings.database_url == "postgresql+psycopg://movie_user:p%40ss@db.internal/cinequote"
    engine = create_database_engine(settings.database_url)
    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg"
    engine.dispose()


def test_legacy_postgres_scheme_is_normalized() -> None:
    settings = Settings(database_url="postgres://user:pass@localhost/cinequote", _env_file=None)
    assert settings.database_url.startswith("postgresql+psycopg://")


def test_bootstrap_migrates_full_catalog_and_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "production-shaped.db"
    database_url = f"sqlite:///{database_path}"
    first = bootstrap(database_url)
    second = bootstrap(database_url)
    expected = len(json.loads(DEFAULT_CATALOG.read_text(encoding="utf-8")))

    assert first["quotes_total"] == expected == 421
    assert second["quotes_total"] == expected
    assert second["quotes_created"] == 0
    assert second["quotes_existing"] == expected

    engine = create_database_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    assert {"films", "quotes", "genres", "users", "auth_sessions", "quiz_attempts", "quiz_attempt_answers"} <= tables
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as database:
        assert database.scalar(select(func.count(Film.id))) == 73
        assert database.scalar(select(func.count(Quote.id))) == 421
        assert database.scalar(select(func.count(User.id))) == 0

    auth = AuthService(factory)
    user, token = auth.register("postgres-ready@example.com", "PostgresReady", "strong-pass-123")
    assert auth.resolve(token) is not None
    StatsService(factory).record(user_id=user.id, session_id="portable-session", genre="all", difficulty="easy", score=7, total=10, hints_used=1)
    assert StatsService(factory).get(user.id).games_played == 1
    engine.dispose()
