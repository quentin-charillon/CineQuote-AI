"""Migrate a database and idempotently load the public movie catalog.

This command never reads another database and never imports users, authentication
sessions, quiz attempts, or passwords. DATABASE_URL selects the target database.
"""

import argparse
import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import delete, func, select
from sqlalchemy.orm import sessionmaker

from app.catalog.importer import CatalogImporter
from app.config import get_settings
from app.database import create_database_engine
from app.models.catalog import Film, Quote

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = BACKEND_ROOT / "app" / "data" / "manual_catalog.json"


def bootstrap(database_url: str, catalog_path: Path = DEFAULT_CATALOG) -> dict[str, int]:
    alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    alembic_config.attributes["database_url"] = database_url
    command.upgrade(alembic_config, "head")

    engine = create_database_engine(database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    # Migration 01 contains a small historical seed so old local databases can
    # still migrate. Production uses manual_catalog.json as its sole authority.
    # Only those explicitly tagged legacy rows are removed; user tables are not
    # queried or modified.
    with factory() as database:
        legacy_quotes_removed = database.execute(delete(Quote).where(Quote.external_id.is_not(None))).rowcount or 0
        database.execute(delete(Film).where(~Film.quotes.any()))
        database.commit()
    imported = CatalogImporter(factory).import_file(catalog_path)
    expected_records = json.loads(catalog_path.read_text(encoding="utf-8"))
    with factory() as database:
        films = database.scalar(select(func.count(Film.id))) or 0
        quotes = database.scalar(select(func.count(Quote.id))) or 0
    if quotes != len(expected_records):
        raise RuntimeError(f"Catalog bootstrap mismatch: expected {len(expected_records)} quotes, found {quotes}")
    engine.dispose()
    return {**imported, "legacy_quotes_removed": legacy_quotes_removed, "films_total": films, "quotes_total": quotes}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=get_settings().database_url, help="Defaults to DATABASE_URL")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    args = parser.parse_args()
    print(json.dumps(bootstrap(args.database_url, args.catalog), indent=2))


if __name__ == "__main__":
    main()
