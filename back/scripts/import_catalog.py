"""Idempotently import CSV/JSON catalog records into the migrated database."""

import argparse
import json
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.catalog.importer import CatalogImporter
from app.config import get_settings
from app.database import create_database_engine


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--database-url", default=get_settings().database_url)
    args = parser.parse_args()
    factory = sessionmaker(bind=create_database_engine(args.database_url), expire_on_commit=False)
    result = CatalogImporter(factory).import_file(args.path)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
