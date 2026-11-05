"""Idempotently apply the reviewed difficulty change artifact."""

import json
import argparse
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.models.catalog import Quote

CHANGES = Path("difficulty-changes-approved.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changes", type=Path, default=CHANGES)
    args = parser.parse_args()
    changes = json.loads(args.changes.read_text(encoding="utf-8"))
    applied = already_applied = 0
    with SessionLocal() as database:
        for item in changes:
            quote = database.scalar(select(Quote).where(Quote.id == int(item["quote_id"])))
            if quote is None or quote.text != item["quote"] or quote.film.title != item["film"]:
                raise ValueError(f"Difficulty change identity mismatch for quote {item['quote_id']}")
            if quote.difficulty == item["proposed_difficulty"]:
                already_applied += 1
                continue
            previous = item.get("current_difficulty", item.get("old_difficulty"))
            if quote.difficulty != previous:
                raise ValueError(f"Unexpected current difficulty for quote {item['quote_id']}")
            quote.difficulty = item["proposed_difficulty"]
            applied += 1
        database.commit()
    print(json.dumps({"changes": len(changes), "applied": applied, "already_applied": already_applied}, indent=2))


if __name__ == "__main__":
    main()
