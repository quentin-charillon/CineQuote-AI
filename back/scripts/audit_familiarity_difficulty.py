"""Audit film familiarity and quote recognizability for a French-speaking casual audience."""

import argparse
import json
import re
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.models.catalog import Film, Quote
from app.repositories.catalog import normalize_catalog_text

MAINSTREAM = {
    "Aladdin", "Dirty Dancing", "E.T.: The Extra-Terrestrial", "Finding Nemo", "Forrest Gump", "Frozen",
    "Jaws", "Rocky", "Spider-Man: Into the Spider-Verse", "Star Wars", "Terminator 2: Judgment Day",
    "The Godfather", "The Incredibles", "The Lion King", "The Lord of the Rings: The Two Towers",
    "The Shining", "The Silence of the Lambs", "The Sixth Sense", "The Terminator", "Titanic", "Top Gun",
    "Toy Story", "Up", "Avengers: Endgame", "Pirates of the Caribbean: The Curse of the Black Pearl",
    "Star Wars: Episode V - The Empire Strikes Back",
}

NICHE = {
    "42nd Street", "All About Eve", "Animal Crackers", "Auntie Mame", "Beyond the Forest", "Cool Hand Luke",
    "Grand Hotel", "In the Heat of the Night", "Knute Rockne--All American", "Little Caesar", "Love Story",
    "Now, Voyager", "On Golden Pond", "On the Waterfront", "Shane", "She Done Him Wrong", "Sons of the Desert",
    "The Jazz Singer", "The Maltese Falcon", "The Naughty Nineties", "The Pride of the Yankees",
    "The Treasure of the Sierra Madre", "To Have and Have Not", "White Heat", "Yankee Doodle Dandy",
}

ICONIC_MAINSTREAM_QUOTES = {
    "may the force be with you", "e t phone home", "i m gonna make him an offer he can t refuse",
    "to infinity and beyond", "just keep swimming", "remember who you are", "i ll be back",
    "i see dead people", "nobody puts baby in a corner", "i feel the need the need for speed",
    "you re gonna need a bigger boat", "here s johnny", "hasta la vista baby", "my precious",
    "i m the king of the world",
    "my mama always said life was like a box of chocolates you never know what you re gonna get",
    "yo adrian", "a census taker once tried to test me i ate his liver with some fava beans and a nice chianti",
    "adventure is out there", "i am your father",
    "this is the day you will always remember as the day you almost caught captain jack sparrow",
    "i love you 3000",
}


def familiarity_for(title: str) -> tuple[str, str, str]:
    if title in MAINSTREAM:
        return "mainstream", "High-confidence editorial classification: broad franchise, family, blockbuster, or enduring mass-audience familiarity in the French-speaking target context.", "approved"
    if title in NICHE:
        return "niche", "High-confidence editorial classification: primarily specialist, classic-cinema, or limited contemporary casual-audience familiarity; age alone is not the reason.", "approved"
    return "recognizable", "Editorial middle category: title is culturally or cinematically recognizable, but broad casual-audience familiarity is uncertain and should be validated by human research.", "pending"


def recognizability(item: dict[str, object], normalized_quote: str) -> tuple[str, str]:
    if normalized_quote in ICONIC_MAINSTREAM_QUOTES:
        return "iconic", "Explicit high-confidence catchphrase review."
    evidence = str(item.get("difficulty_evidence", ""))
    rank_match = re.search(r"AFI rank (\d+)", evidence)
    if rank_match:
        rank = int(rank_match.group(1))
        if rank <= 20:
            return "iconic", f"AFI top-20 rank {rank} supports quote recognizability, independently of movie familiarity."
        if rank <= 60:
            return "recognizable", f"AFI rank {rank} supports cultural notability but not broad iconic recognition."
        return "obscure", f"AFI rank {rank}; retained as deeper-recognition dialogue under the conservative policy."
    proposed = str(item.get("proposed_difficulty", item.get("current_difficulty", "hard")))
    return ("recognizable", "Prior editorial review supports film-viewer recognition.") if proposed == "medium" else ("obscure", "No independent evidence of broad standalone quote recognition.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-approved", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("familiarity-difficulty-review.json"))
    parser.add_argument("--changes", type=Path, default=Path("familiarity-difficulty-changes-approved.json"))
    args = parser.parse_args()
    prior = {int(item["quote_id"]): item for item in json.loads(Path("difficulty-review.json").read_text(encoding="utf-8"))}

    report = []
    with SessionLocal() as database:
        films = database.scalars(select(Film).order_by(Film.id)).all()
        for film in films:
            familiarity, film_rationale, film_status = familiarity_for(film.title)
            film.familiarity = familiarity
            film.familiarity_rationale = film_rationale
            film.familiarity_review_status = film_status
            for quote in sorted(film.quotes, key=lambda value: value.id):
                recognition, recognition_rationale = recognizability(prior.get(quote.id, {}), quote.normalized_text)
                easy_eligible = familiarity == "mainstream" and recognition == "iconic"
                proposed = quote.difficulty
                rationale = "No high-confidence difficulty change; retain for further review."
                status = "pending"
                if quote.difficulty == "easy" and not easy_eligible:
                    proposed = "medium" if recognition in {"iconic", "recognizable"} else "hard"
                    rationale = "Removed from Easy because both mainstream movie familiarity and iconic quote recognition are mandatory."
                    status = "approved"
                elif quote.difficulty != "easy" and easy_eligible and quote.normalized_text in ICONIC_MAINSTREAM_QUOTES:
                    proposed = "easy"
                    rationale = "Approved for Easy: high-confidence mainstream film and explicit iconic catchphrase evidence both pass."
                    status = "approved"
                report.append({
                    "film_id": film.id, "film": film.title, "release_year": film.release_year,
                    "film_familiarity": familiarity, "film_familiarity_rationale": film_rationale,
                    "film_review_status": film_status, "quote_id": quote.id, "quote": quote.text,
                    "quote_recognizability": recognition, "quote_recognizability_rationale": recognition_rationale,
                    "old_difficulty": quote.difficulty, "proposed_difficulty": proposed,
                    "difficulty_rationale": rationale, "difficulty_review_status": status,
                })

        changes = [item for item in report if item["difficulty_review_status"] == "approved" and item["old_difficulty"] != item["proposed_difficulty"]]
        if args.apply_approved:
            quotes = {quote.id: quote for quote in database.scalars(select(Quote)).all()}
            for item in changes:
                quotes[int(item["quote_id"])].difficulty = str(item["proposed_difficulty"])
        database.commit()

    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if changes or not args.changes.exists():
        args.changes.write_text(json.dumps(changes, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"films_reviewed": len({item['film_id'] for item in report}), "quotes_reviewed": len(report), "approved_changes": len(changes), "pending_quote_reviews": sum(item["difficulty_review_status"] == "pending" for item in report), "applied": args.apply_approved}, indent=2))


if __name__ == "__main__":
    main()
