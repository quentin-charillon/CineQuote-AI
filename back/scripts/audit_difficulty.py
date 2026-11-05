"""Create a reviewable difficulty audit and optionally apply approved changes."""

import argparse
import json
from pathlib import Path

from sqlalchemy import select

from app.catalog.afi import fetch_afi_records
from app.database import SessionLocal
from app.models.catalog import Quote
from app.repositories.catalog import normalize_catalog_text

AFI_URL = "https://www.afi.com/afis-100-years-100-movie-quotes/"

# Conservative human editorial decisions for lines outside AFI's ranked list.
# Anything omitted remains explicitly pending at its current tier.
EDITORIAL: dict[str, tuple[str, str]] = {
    "to infinity and beyond": ("easy", "Widely repeated catchphrase beyond the film's audience."),
    "just keep swimming": ("easy", "Widely repeated catchphrase beyond the film's audience."),
    "kitty": ("hard", "One-word contextual dialogue is not attributable without deep film knowledge."),
    "do you trust me": ("medium", "Recognizable to viewers of the film but not uniquely attributable broadly."),
    "you can t marry a man you just met": ("medium", "Recognizable within the film, but not a universal movie catchphrase."),
    "our fate lives within us you only have to be brave enough to see it": ("medium", "Prominent thematic line, primarily recognizable to viewers familiar with the film."),
    "remember who you are": ("easy", "Highly prominent and broadly associated with the film."),
    "no capes": ("easy", "Short, heavily repeated line broadly associated with the film."),
    "adventure is out there": ("easy", "Marketing-level catchphrase broadly associated with the film."),
    "anyone can cook but only the fearless can be great": ("medium", "Recognizable thematic dialogue, but not universally attributable."),
    "you are a toy": ("easy", "Frequently cited confrontation line strongly associated with the film."),
    "honey where is my super suit": ("easy", "Frequently quoted scene recognizable beyond dedicated viewers."),
    "that wasn t flying that was falling with style": ("easy", "Frequently repeated line strongly associated with the film."),
    "put that thing back where it came from or so help me": ("medium", "Recognizable scene dialogue for viewers familiar with the film."),
    "it was big": ("hard", "Generic, context-dependent dialogue with almost no standalone attribution signal."),
    "what s a bad miracle they got a word for that": ("medium", "Distinctive thematic line, mainly recognizable to viewers of the film."),
    "i m gonna find your daughter": ("hard", "Generic plot dialogue that is difficult to attribute outside its scene."),
    "pray for the best prepare for the worst": ("medium", "Memorable aphoristic line, but not uniquely or universally tied to the film."),
    "anyone can wear the mask": ("medium", "Central thematic line recognizable to fans, but not universally iconic."),
    "you gotta say i love you back": ("hard", "Context-dependent family dialogue requiring knowledge of the scene."),
}


def afi_policy(rank: int) -> tuple[str, str]:
    if rank <= 20:
        return "easy", f"AFI rank {rank}; top-20 placement is used as strong cultural-recognition evidence."
    if rank <= 60:
        return "medium", f"AFI rank {rank}; culturally notable, but outside the deliberately narrow top-20 Easy band."
    return "hard", f"AFI rank {rank}; AFI-listed but lower-ranked, so attribution is treated as deeper cinema knowledge."


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-approved", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("difficulty-review.json"))
    parser.add_argument("--changes", type=Path, default=Path("difficulty-changes-approved.json"))
    args = parser.parse_args()

    afi = {}
    for record in fetch_afi_records():
        key = (normalize_catalog_text(str(record["film_title"])), normalize_catalog_text(str(record["quote"])))
        afi[key] = int(record["afi_rank"])
        raw = str(record["quote"])
        if ":" in raw:
            afi[(key[0], normalize_catalog_text(raw.split(":", 1)[1]))] = int(record["afi_rank"])

    report: list[dict[str, object]] = []
    with SessionLocal() as database:
        quotes = database.scalars(select(Quote).order_by(Quote.id)).all()
        for quote in quotes:
            key = (quote.film.normalized_title, quote.normalized_text)
            if key in afi:
                proposed, rationale = afi_policy(afi[key])
                status = "approved"
                evidence = f"AFI rank {afi[key]}"
            elif quote.normalized_text in EDITORIAL:
                proposed, rationale = EDITORIAL[quote.normalized_text]
                status = "approved"
                evidence = "documented human editorial review"
            else:
                proposed = quote.difficulty
                rationale = "Insufficient external recognizability evidence for a high-confidence change; retain pending human review."
                status = "pending"
                evidence = "quote authenticity source only; no independent difficulty evidence"
            report.append({
                "quote_id": quote.id, "quote": quote.text, "film": quote.film.title,
                "current_difficulty": quote.difficulty, "proposed_difficulty": proposed,
                "rationale": rationale, "review_status": status, "difficulty_evidence": evidence,
            })

        changes = [item for item in report if item["review_status"] == "approved" and item["current_difficulty"] != item["proposed_difficulty"]]
        if args.apply_approved:
            by_id = {quote.id: quote for quote in quotes}
            for item in changes:
                by_id[int(item["quote_id"])].difficulty = str(item["proposed_difficulty"])
            database.commit()

    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    # Preserve the reviewed before/after artifact after it has been applied;
    # a routine post-migration audit must not replace it with an empty file.
    if changes or not args.changes.exists():
        args.changes.write_text(json.dumps(changes, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"quotes_reviewed": len(report), "approved_changes": len(changes), "pending_review": sum(item["review_status"] == "pending" for item in report), "applied": args.apply_approved}, indent=2))


if __name__ == "__main__":
    main()
