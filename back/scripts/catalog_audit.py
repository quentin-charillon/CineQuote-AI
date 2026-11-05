"""Print a JSON integrity and distribution report for the SQLite catalog."""

import json

from sqlalchemy import Integer, func, select

from app.database import SessionLocal
from app.models.catalog import Film, Genre, Quote


def build_report() -> dict[str, object]:
    with SessionLocal() as database:
        difficulty_rows = database.execute(select(Quote.difficulty, func.count(Quote.id)).where(Quote.is_verified.is_(True)).group_by(Quote.difficulty)).all()
        decade = (Film.release_year / 10).cast(Integer) * 10
        decade_rows = database.execute(
            select(decade, func.count(Film.id)).group_by(decade).order_by(decade)
        ).all()
        country_rows = database.execute(select(func.coalesce(Film.country_of_origin, "Unknown"), func.count(Film.id)).group_by(func.coalesce(Film.country_of_origin, "Unknown"))).all()
        genre_rows = database.execute(select(Genre.name, func.count()).select_from(Genre).join(Genre.films).group_by(Genre.name)).all()
        duplicate_rows = database.execute(select(Quote.film_id, Quote.normalized_text, func.count()).group_by(Quote.film_id, Quote.normalized_text).having(func.count() > 1)).all()
        difficulty = {name: count for name, count in difficulty_rows}
        return {
            "films": database.scalar(select(func.count(Film.id))),
            "quotes": database.scalar(select(func.count(Quote.id))),
            "verified_quotes": database.scalar(select(func.count(Quote.id)).where(Quote.is_verified.is_(True))),
            "unverified_quotes": database.scalar(select(func.count(Quote.id)).where(Quote.is_verified.is_(False))),
            "verified_by_difficulty": {name: difficulty.get(name, 0) for name in ("easy", "medium", "hard")},
            "playable": {name: difficulty.get(name, 0) >= 10 for name in ("easy", "medium", "hard")},
            "genres": dict(genre_rows) if genre_rows else {"Unknown": database.scalar(select(func.count(Film.id)))},
            "countries": dict(country_rows),
            "decades": {str(decade): count for decade, count in decade_rows},
            "duplicate_warnings": [{"film_id": film_id, "normalized_text": text, "count": count} for film_id, text, count in duplicate_rows],
        }


if __name__ == "__main__":
    print(json.dumps(build_report(), indent=2))
