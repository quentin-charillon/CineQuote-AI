"""Validated single-worker Render entrypoint with serialized database bootstrap."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import uvicorn
from sqlalchemy import text

from app.config import get_settings
from app.database import create_database_engine
from scripts.bootstrap_database import bootstrap

MIGRATION_LOCK_ID = 1_984_201_026


@contextmanager
def migration_lock(database_url: str) -> Iterator[None]:
    """Serialize migrations across overlapping Render starts."""
    engine = create_database_engine(database_url)
    if engine.dialect.name != "postgresql":
        engine.dispose()
        raise RuntimeError("Production startup requires PostgreSQL")
    try:
        with engine.connect() as connection:
            connection.execute(text("SET lock_timeout = '120s'"))
            connection.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": MIGRATION_LOCK_ID})
            try:
                yield
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": MIGRATION_LOCK_ID})
    finally:
        engine.dispose()


def main() -> None:
    settings = get_settings()  # Production validation fails closed here.
    if settings.app_env.casefold() != "production":
        raise RuntimeError("scripts/start_production.py requires APP_ENV=production")
    port_text = os.getenv("PORT", "10000")
    try:
        port = int(port_text)
    except ValueError as error:
        raise RuntimeError("PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise RuntimeError("PORT must be between 1 and 65535")

    with migration_lock(settings.database_url):
        result = bootstrap(settings.database_url)
        print(f"catalog_ready films={result['films_total']} quotes={result['quotes_total']}", flush=True)

    uvicorn.run("app.main:app", host="0.0.0.0", port=port, workers=1, proxy_headers=False)


if __name__ == "__main__":
    main()
