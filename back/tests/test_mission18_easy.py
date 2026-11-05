import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.catalog.importer import CatalogImporter
from app.database import Base, create_database_engine
from app.models.catalog import Film, Quote


def test_mission18_batch_is_verified_easy_distinct_and_idempotent(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'mission18.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    path = Path(__file__).parents[1] / "app" / "data" / "mission18_easy_quotes.json"
    importer = CatalogImporter(factory)

    first = importer.import_file(path, independently_reviewed=True)
    second = importer.import_file(path, independently_reviewed=True)

    assert first["films_created"] == first["quotes_created"] == 3
    assert second["quotes_existing"] == 3
    with factory() as database:
        assert database.scalar(select(func.count(Film.id))) == 3
        assert database.scalar(select(func.count(Quote.id)).where(Quote.is_verified.is_(True), Quote.difficulty == "easy")) == 3
        assert database.scalar(select(func.count(func.distinct(Quote.normalized_text)))) == 3


def test_easy_expansion_review_preserves_strict_dual_gate() -> None:
    path = Path(__file__).parents[1] / "easy-expansion-review.json"
    review = json.loads(path.read_text(encoding="utf-8"))
    easy = [item for item in review if item["proposed_difficulty"] == "easy"]

    assert len(review) == 148
    assert len({item["film_id"] for item in review}) == 103
    assert all(item["film_familiarity"] == "mainstream" for item in easy)
    assert all(item["quote_recognizability"] == "iconic" for item in easy)


def test_mission18_changes_are_reviewed_promotions_only() -> None:
    path = Path(__file__).parents[1] / "easy-expansion-changes-approved.json"
    changes = json.loads(path.read_text(encoding="utf-8"))

    assert len(changes) == 4
    assert all(item["old_difficulty"] in {"medium", "hard"} for item in changes)
    assert all(item["proposed_difficulty"] == "easy" for item in changes)
