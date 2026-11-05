"""Match catalog films to explicit Wikidata title/year/genre claims."""

import json
from pathlib import Path

from sqlalchemy import select

from app.catalog.genre_importer import GenreImporter
from app.catalog.wikidata_genres import WikidataGenreClient
from app.database import SessionLocal
from app.models.catalog import Film


def main() -> None:
    with SessionLocal() as database:
        films = database.scalars(select(Film).order_by(Film.id)).all()
        inputs = [(film.title, film.release_year) for film in films]

    records: list[dict[str, object]] = []
    review_queue: list[dict[str, object]] = []
    client = WikidataGenreClient()
    try:
        for title, year in inputs:
            try:
                genres, source_url = client.find_film(title, year)
            except Exception as error:
                review_queue.append({"film_title": title, "release_year": year, "reason": f"provider error: {type(error).__name__}"})
                continue
            if not genres or source_url is None:
                review_queue.append({"film_title": title, "release_year": year, "reason": source_url or "no supported genre"})
                continue
            for genre in genres:
                records.append({"film_title": title, "release_year": year, "source_url": source_url, **genre})
    finally:
        client.close()

    result = GenreImporter(SessionLocal).import_records(records)
    Path("genre-review-queue.json").write_text(json.dumps(review_queue, indent=2), encoding="utf-8")
    print(json.dumps({"films_inspected": len(inputs), "films_with_supported_genres": len({(r['film_title'], r['release_year']) for r in records}), "review_queue": len(review_queue), **result}, indent=2))


if __name__ == "__main__":
    main()
