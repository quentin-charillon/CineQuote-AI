"""Optional live PostgreSQL verification.

Set TEST_POSTGRES_DATABASE_URL to a disposable, empty database. The test imports
the public catalog, creates one temporary account and statistics record, then
deletes that account. It never reads the local SQLite database.
"""

import os
import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import create_database_engine
from app.models.account import User
from app.services.auth import AuthService
from app.services.stats import StatsService
from scripts.bootstrap_database import bootstrap


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_DATABASE_URL"), reason="requires a disposable PostgreSQL database")
def test_postgres_migrations_catalog_accounts_and_stats() -> None:
    raw_url = os.environ["TEST_POSTGRES_DATABASE_URL"]
    database_url = Settings(database_url=raw_url, _env_file=None).database_url
    result = bootstrap(database_url)
    assert result["quotes_total"] == 421

    engine = create_database_engine(database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    suffix = uuid.uuid4().hex
    auth = AuthService(factory)
    user, token = auth.register(f"deploy-{suffix}@example.com", f"deploy{suffix[:12]}", "temporary-pass-123")
    try:
        assert auth.resolve(token) is not None
        stats = StatsService(factory)
        stats.record(user_id=user.id, session_id=f"postgres-{suffix}", genre="all", difficulty="easy", score=8, total=10, hints_used=1)
        assert stats.get(user.id).games_played == 1
    finally:
        with factory() as database:
            database.execute(delete(User).where(User.id == user.id))
            database.commit()
        engine.dispose()
