"""Apply a narrowly reviewed difficulty change file with stale-data guards."""

import argparse
import json
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.models.catalog import Film, Quote


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    changes = json.loads(args.path.read_text(encoding="utf-8"))
    applied = 0
    already_applied = 0
    with SessionLocal() as database:
        for change in changes:
            quote = database.scalar(select(Quote).where(Quote.id == int(change["quote_id"])))
            if quote is None or quote.text != change["quote"] or quote.film.title != change["film"]:
                raise ValueError(f"Stale or mismatched review record: {change}")
            if not quote.is_verified:
                raise ValueError(f"Cannot reclassify unverified quote {quote.id}")
            target = str(change["proposed_difficulty"])
            if quote.difficulty == target:
                already_applied += 1
                continue
            if quote.difficulty != change["old_difficulty"]:
                raise ValueError(f"Unexpected current difficulty for quote {quote.id}: {quote.difficulty}")
            quote.difficulty = target
            if quote.film.title in {"Monsters, Inc.", "Ratatouille"}:
                quote.film.familiarity = "mainstream"
                quote.film.familiarity_review_status = "approved"
                quote.film.familiarity_rationale = "Reviewed mainstream family-animation recognition for the French-speaking casual audience."
            applied += 1
        database.commit()
    print(json.dumps({"applied": applied, "already_applied": already_applied}, indent=2))


if __name__ == "__main__":
    main()
