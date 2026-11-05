import csv
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.catalog.classification import classify_difficulty
from app.models.catalog import Film, Genre, Quote
from app.repositories.catalog import normalize_catalog_text


class CatalogImporter:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def import_file(self, path: Path, independently_reviewed: bool = True) -> dict[str, int]:
        return self.import_records(self._read(path), independently_reviewed)

    def import_records(self, records: list[dict[str, Any]], independently_reviewed: bool = True) -> dict[str, int]:
        summary = {"films_created": 0, "quotes_created": 0, "quotes_existing": 0}
        with self._session_factory() as database:
            for record in records:
                film = self._film(database, record, summary)
                raw_quote = str(record["quote"])
                normalized_quote = normalize_catalog_text(raw_quote)
                quote = database.scalar(select(Quote).where(Quote.film_id == film.id, Quote.normalized_text == normalized_quote))
                # Curated lists sometimes prefix dialogue with a speaker name. Treat
                # that presentation label as equivalent to an existing spoken line.
                if quote is None and ":" in raw_quote:
                    speaker, spoken_text = raw_quote.split(":", 1)
                    if speaker.strip() and len(speaker.split()) <= 3 and spoken_text.strip():
                        quote = database.scalar(select(Quote).where(
                            Quote.film_id == film.id,
                            Quote.normalized_text == normalize_catalog_text(spoken_text),
                        ))
                if quote is None:
                    difficulty = record.get("difficulty")
                    if difficulty not in {"easy", "medium", "hard"}:
                        difficulty = classify_difficulty(int(record["recognizability_score"]), int(record["knowledge_score"]))
                    quote = Quote(text=raw_quote, normalized_text=normalized_quote, difficulty=difficulty, is_verified=True, film=film)
                    database.add(quote)
                    database.flush()
                    summary["quotes_created"] += 1
                else:
                    summary["quotes_existing"] += 1

                # ``is_verified`` is retained only for compatibility with existing
                # databases. Manual catalog entries are immediately playable.
                quote.is_verified = True
                for name in self._genres(record.get("genres")):
                    genre = database.scalar(select(Genre).where(Genre.name == name)) or Genre(name=name)
                    if genre not in film.genres:
                        film.genres.append(genre)
                country = str(record.get("country_of_origin") or "").strip()
                if country and not film.country_of_origin:
                    film.country_of_origin = country
            database.commit()
        return summary

    @staticmethod
    def _film(database: Session, record: dict[str, Any], summary: dict[str, int]) -> Film:
        title = str(record["film_title"])
        normalized_title = normalize_catalog_text(title)
        raw_year = record.get("release_year")
        year = int(raw_year) if raw_year not in (None, "") else None
        matches = database.scalars(select(Film).where(Film.normalized_title == normalized_title)).all()
        if len(matches) == 1:
            # The manual catalog treats a franchise label as one answer choice,
            # even when its quotations originate from different instalments.
            film = matches[0]
        elif len(matches) > 1 and year is not None:
            film = next((match for match in matches if match.release_year == year), None)
        elif len(matches) > 1:
            raise ValueError(f"Several films are named {title!r}; add release_year to select the right one")
        else:
            film = None
        if film is None:
            film = Film(title=title, normalized_title=normalized_title, release_year=year)
            database.add(film)
            database.flush()
            summary["films_created"] += 1
        return film

    @staticmethod
    def _genres(value: Any) -> list[str]:
        canonical = {
            name.casefold(): name
            for name in (
                "Horror", "Comedy", "Science Fiction", "Thriller", "Action",
                "Animation", "Drama", "Romance", "Fantasy", "Crime", "Adventure",
            )
        }
        if isinstance(value, list):
            names = [str(item).strip() for item in value if str(item).strip()]
        else:
            names = [item.strip() for item in str(value or "").split(";") if item.strip()]
        return [canonical.get(name.casefold(), name) for name in names]

    @staticmethod
    def _read(path: Path) -> list[dict[str, Any]]:
        if path.suffix.casefold() == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else [data]
        if path.suffix.casefold() == ".csv":
            with path.open(encoding="utf-8-sig", newline="") as handle:
                return list(csv.DictReader(handle))
        raise ValueError("Catalog import supports .json and .csv files")
