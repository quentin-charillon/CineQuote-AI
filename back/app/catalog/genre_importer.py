from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.catalog import Film, FilmGenreEvidence, Genre
from app.repositories.catalog import normalize_catalog_text


class GenreImporter:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def import_records(self, records: list[dict[str, object]]) -> dict[str, int]:
        summary = {"films_matched": 0, "assignments_added": 0, "assignments_existing": 0, "records_rejected": 0}
        with self._session_factory() as database:
            for record in records:
                film = database.scalar(select(Film).where(
                    Film.normalized_title == normalize_catalog_text(str(record["film_title"])),
                    Film.release_year == int(record["release_year"]),
                ))
                source_url = str(record.get("source_url") or "")
                genre_name = str(record.get("genre") or "")
                external_id = str(record.get("external_genre_id") or "")
                trusted_source = (
                    source_url.startswith("https://www.wikidata.org/")
                    or source_url.startswith("https://www.imdb.com/title/")
                    or source_url.startswith("https://www.rottentomatoes.com/m/")
                )
                if film is None or not trusted_source or not genre_name or not external_id:
                    summary["records_rejected"] += 1
                    continue
                summary["films_matched"] += 1
                genre = database.scalar(select(Genre).where(Genre.name == genre_name))
                if genre is None:
                    genre = Genre(name=genre_name)
                    database.add(genre)
                    database.flush()
                evidence = database.scalar(select(FilmGenreEvidence).where(
                    FilmGenreEvidence.film_id == film.id,
                    FilmGenreEvidence.genre_id == genre.id,
                    FilmGenreEvidence.source_url == source_url,
                ))
                if evidence is None:
                    database.add(FilmGenreEvidence(
                        film_id=film.id, genre_id=genre.id, source_url=source_url,
                        external_genre_id=external_id, verified=True,
                        reviewed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    ))
                    if genre not in film.genres:
                        film.genres.append(genre)
                    summary["assignments_added"] += 1
                else:
                    evidence.verified = True
                    summary["assignments_existing"] += 1
            database.commit()
        return summary
