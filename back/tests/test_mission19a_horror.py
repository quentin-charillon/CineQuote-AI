import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.catalog.genre_importer import GenreImporter
from app.catalog.importer import CatalogImporter
from app.database import Base, create_database_engine
from app.models.catalog import Film, Genre, Quote


DATA = Path(__file__).parents[1] / "app" / "data"


def test_horror_batch_is_verified_distinct_classified_and_idempotent(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'horror.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    catalog = CatalogImporter(factory)

    first = catalog.import_file(DATA / "mission19a_horror_quotes.json", independently_reviewed=True)
    second = catalog.import_file(DATA / "mission19a_horror_quotes.json", independently_reviewed=True)
    with factory() as database:
        database.add(Film(title="Dracula", normalized_title="dracula", release_year=1931))
        database.commit()
    genres = json.loads((DATA / "mission19a_horror_genres.json").read_text(encoding="utf-8"))
    genre_first = GenreImporter(factory).import_records(genres)
    genre_second = GenreImporter(factory).import_records(genres)

    assert first["films_created"] == 11
    assert first["quotes_created"] == 16
    assert second["quotes_existing"] == 16
    assert genre_first["assignments_added"] == 2
    assert genre_second["assignments_existing"] == 2
    with factory() as database:
        assert database.scalar(select(func.count(Quote.id)).where(Quote.is_verified.is_(True))) == 16
        assert dict(database.execute(select(Quote.difficulty, func.count(Quote.id)).group_by(Quote.difficulty)).all()) == {
            "easy": 6, "medium": 6, "hard": 4,
        }
        assert database.execute(
            select(Quote.film_id, Quote.normalized_text, func.count())
            .group_by(Quote.film_id, Quote.normalized_text).having(func.count() > 1)
        ).all() == []
        horror = database.scalar(select(Genre).where(Genre.name == "Horror"))
        assert horror is not None
        assert {film.title for film in horror.films} == {"Scream", "Dracula"}
        assert all(quote.is_verified for quote in database.scalars(select(Quote)).all())


def test_horror_batch_uses_documented_editorial_difficulty_policy() -> None:
    records = json.loads((DATA / "mission19a_horror_quotes.json").read_text(encoding="utf-8"))
    easy = [record for record in records if record["difficulty"] == "easy"]

    assert len(easy) == 6
    assert {record["film_title"] for record in easy} == {"Scream", "The Shining", "Saw", "It"}
    assert all(record["difficulty"] in {"easy", "medium", "hard"} for record in records)
    assert len({(record["film_title"], record["release_year"], record["quote"].casefold()) for record in records}) == len(records)
