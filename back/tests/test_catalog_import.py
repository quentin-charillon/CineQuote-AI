import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.catalog.classification import ClassificationConfig, classify_difficulty
from app.catalog.importer import CatalogImporter
from app.database import Base, create_database_engine
from app.models.catalog import Film, Quote


def test_human_scored_classification_is_configurable() -> None:
    assert classify_difficulty(5, 1) == "easy"
    assert classify_difficulty(1, 5) == "hard"
    assert classify_difficulty(3, 3) == "medium"
    config = ClassificationConfig(easy_recognizability_min=3, easy_knowledge_max=3)
    assert classify_difficulty(3, 3, config) == "easy"


def test_json_import_is_idempotent_playable_and_accepts_minimal_fields(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'import.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps([{
        "film_title": "Reviewed Test Film",
        "quote": "A synthetic import test line.",
        "difficulty": "easy",
        "genres": ["Drama"],
    }]), encoding="utf-8")
    importer = CatalogImporter(factory)

    first = importer.import_file(path)
    second = importer.import_file(path)

    assert first["quotes_created"] == 1
    assert second["quotes_existing"] == 1
    with factory() as database:
        assert database.scalar(select(func.count(Film.id))) == 1
        quote = database.scalar(select(Quote))
        assert quote is not None and quote.is_verified is True
        assert quote.film.release_year is None


def test_import_treats_speaker_label_as_same_spoken_quote(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'speaker.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    importer = CatalogImporter(factory)
    base = {
        "film_title": "Test Film",
        "release_year": 2001,
        "difficulty": "hard",
    }

    importer.import_records([{**base, "quote": "Surely this is a test."}], independently_reviewed=True)
    result = importer.import_records([{**base, "quote": "Speaker: Surely this is a test."}], independently_reviewed=True)

    assert result["quotes_created"] == 0
    assert result["quotes_existing"] == 1
    with factory() as database:
        assert database.scalar(select(func.count(Quote.id))) == 1
