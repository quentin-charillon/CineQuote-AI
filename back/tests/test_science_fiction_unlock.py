import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.catalog.genre_importer import GenreImporter
from app.catalog.importer import CatalogImporter
from app.database import Base, create_database_engine
from app.models.catalog import Film, Quote


DATA = Path(__file__).parents[1] / "app" / "data"


def test_science_fiction_unlock_batch_is_verified_distinct_and_idempotent(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'science-fiction.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    importer = CatalogImporter(factory)
    path = DATA / "science_fiction_unlock_quotes.json"

    first = importer.import_file(path, independently_reviewed=True)
    second = importer.import_file(path, independently_reviewed=True)
    genres = json.loads((DATA / "science_fiction_unlock_genres.json").read_text(encoding="utf-8"))
    genre_first = GenreImporter(factory).import_records(genres)
    genre_second = GenreImporter(factory).import_records(genres)

    assert first["films_created"] == 2
    assert first["quotes_created"] == 11
    assert second["quotes_existing"] == 11
    assert genre_first["assignments_added"] == 1
    assert genre_second["assignments_existing"] == 1
    with factory() as database:
        assert dict(database.execute(select(Quote.difficulty, func.count()).group_by(Quote.difficulty)).all()) == {
            "easy": 4, "medium": 4, "hard": 3,
        }
        assert database.execute(
            select(Quote.film_id, Quote.normalized_text, func.count())
            .group_by(Quote.film_id, Quote.normalized_text).having(func.count() > 1)
        ).all() == []
        assert all(quote.is_verified for quote in database.scalars(select(Quote)).all())
        star_wars = database.scalar(select(Film).where(Film.title == "Star Wars"))
        assert star_wars is not None and "Science Fiction" in {genre.name for genre in star_wars.genres}
