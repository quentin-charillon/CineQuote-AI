from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.catalog.importer import CatalogImporter
from app.database import Base, create_database_engine
from app.models.catalog import Film, Quote


def test_mission11_reviewed_batch_is_complete_verified_and_idempotent(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'mission11.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    path = Path(__file__).parents[1] / "app" / "data" / "mission11_animation_quotes.json"
    importer = CatalogImporter(factory)

    first = importer.import_file(path, independently_reviewed=True)
    second = importer.import_file(path, independently_reviewed=True)

    assert first["films_created"] == 10
    assert first["quotes_created"] == 30
    assert second["quotes_created"] == 0
    assert second["quotes_existing"] == 30
    with factory() as database:
        assert database.scalar(select(func.count(Film.id))) == 10
        assert database.scalar(select(func.count(Quote.id)).where(Quote.is_verified.is_(True))) == 30
        distribution = dict(database.execute(select(Quote.difficulty, func.count(Quote.id)).group_by(Quote.difficulty)).all())
        assert distribution == {"easy": 10, "medium": 10, "hard": 10}
        duplicates = database.execute(
            select(Quote.film_id, Quote.normalized_text, func.count())
            .group_by(Quote.film_id, Quote.normalized_text).having(func.count() > 1)
        ).all()
        assert duplicates == []
