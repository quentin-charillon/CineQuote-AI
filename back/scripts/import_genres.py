"""Import an explicitly reviewed film-genre evidence file."""

import argparse
import json
from pathlib import Path

from app.catalog.genre_importer import GenreImporter
from app.database import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    records = json.loads(args.path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("Genre import file must contain a JSON array")
    print(json.dumps(GenreImporter(SessionLocal).import_records(records), indent=2))


if __name__ == "__main__":
    main()
