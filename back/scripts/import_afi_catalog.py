"""Fetch and idempotently import AFI's official 100 Movie Quotes list."""

import json

from app.catalog.afi import fetch_afi_records
from app.catalog.importer import CatalogImporter
from app.database import SessionLocal


def main() -> None:
    records = fetch_afi_records()
    result = CatalogImporter(SessionLocal).import_records(records, independently_reviewed=True)
    print(json.dumps({"source_entries": len(records), **result}, indent=2))


if __name__ == "__main__":
    main()
