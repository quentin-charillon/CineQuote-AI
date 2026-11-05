from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.catalog.genre_importer import GenreImporter
from app.database import Base, create_database_engine
from app.models.catalog import Film, FilmGenreEvidence, Genre


def test_genre_import_is_verified_multi_genre_and_idempotent(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'genres.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as database:
        database.add(Film(title="Test Film", normalized_title="test film", release_year=2000))
        database.commit()
    records = [
        {"film_title": "Test Film", "release_year": 2000, "genre": "Drama", "source_url": "https://www.imdb.com/title/tt0000001/", "external_genre_id": "Drama"},
        {"film_title": "Test Film", "release_year": 2000, "genre": "Romance", "source_url": "https://www.imdb.com/title/tt0000001/", "external_genre_id": "Romance"},
    ]
    importer = GenreImporter(factory)

    first = importer.import_records(records)
    second = importer.import_records(records)

    assert first["assignments_added"] == 2
    assert second["assignments_existing"] == 2
    with factory() as database:
        film = database.scalar(select(Film))
        assert film is not None and {genre.name for genre in film.genres} == {"Drama", "Romance"}
        assert database.scalar(select(func.count(FilmGenreEvidence.id))) == 2
        assert database.scalar(select(func.count(FilmGenreEvidence.id)).where(FilmGenreEvidence.verified.is_(True))) == 2


def test_genre_import_rejects_missing_film_and_untrusted_evidence(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'rejected.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    importer = GenreImporter(factory)

    result = importer.import_records([{
        "film_title": "Invented", "release_year": 2000, "genre": "Drama",
        "source_url": "https://example.test/not-evidence", "external_genre_id": "Drama",
    }])

    assert result["records_rejected"] == 1
    with factory() as database:
        assert database.scalar(select(func.count(Genre.id))) == 0
