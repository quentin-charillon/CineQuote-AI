from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.catalog.importer import CatalogImporter
from app.database import Base, create_database_engine
from app.models.catalog import Film, Quote


def test_mission12_priority_batch_is_verified_distinct_and_idempotent(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'mission12.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    path = Path(__file__).parents[1] / "app" / "data" / "mission12_priority_quotes.json"
    importer = CatalogImporter(factory)

    first = importer.import_file(path, independently_reviewed=True)
    second = importer.import_file(path, independently_reviewed=True)

    assert first["films_created"] == 3
    assert first["quotes_created"] == 15
    assert second["quotes_existing"] == 15
    with factory() as database:
        assert database.scalar(select(func.count(Film.id))) == 3
        assert database.scalar(select(func.count(Quote.id)).where(Quote.is_verified.is_(True))) == 15
        assert dict(database.execute(select(Quote.difficulty, func.count(Quote.id)).group_by(Quote.difficulty)).all()) == {"easy": 6, "medium": 3, "hard": 6}
        assert database.execute(
            select(Quote.film_id, Quote.normalized_text, func.count())
            .group_by(Quote.film_id, Quote.normalized_text).having(func.count() > 1)
        ).all() == []
