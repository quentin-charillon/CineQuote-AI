import json
import random
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.repositories.questions import JsonQuestionRepository
from app.repositories.sessions import InMemorySessionRepository
from app.services.hints import FallbackHintGenerator, HintService
from app.services.quiz import QuizService, get_quiz_service


def question_data() -> list[dict[str, object]]:
    return [
        question.model_dump(mode="json")
        for question in JsonQuestionRepository().list_all()
    ]


def write_dataset(path: Path, data: list[dict[str, object]]) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_verified_question_does_not_require_source_field(tmp_path: Path) -> None:
    data = question_data()
    repository = JsonQuestionRepository(write_dataset(tmp_path / "no-source.json", data))

    assert len(repository.list_verified()) == 10


@pytest.mark.parametrize(("field", "value"), [("release_year", 1200)])
def test_invalid_question_metadata_is_rejected(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    data = question_data()
    data[0][field] = value

    with pytest.raises(ValidationError):
        JsonQuestionRepository(write_dataset(tmp_path / f"invalid-{field}.json", data))


def test_duplicate_quotes_are_rejected_after_normalization(tmp_path: Path) -> None:
    data = question_data()
    data[1]["quote"] = f"  {str(data[0]['quote']).upper()}  "
    data[1]["film_title"] = data[0]["film_title"]
    data[1]["release_year"] = data[0]["release_year"]
    data[1]["choices"] = data[0]["choices"]

    with pytest.raises(ValueError, match="quotes must be unique within a film"):
        JsonQuestionRepository(write_dataset(tmp_path / "duplicates.json", data))


@pytest.fixture
def insufficient_client(tmp_path: Path) -> Iterator[TestClient]:
    data = question_data()
    data = data[:9]
    repository = JsonQuestionRepository(write_dataset(tmp_path / "insufficient.json", data))
    service = QuizService(
        repository,
        InMemorySessionRepository(),
        random.Random(3),
        HintService(FallbackHintGenerator()),
    )
    app.dependency_overrides[get_quiz_service] = lambda: service
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_session_creation_reports_insufficient_verified_questions(
    insufficient_client: TestClient,
) -> None:
    response = insufficient_client.post("/quiz/sessions", json={"difficulty": "easy"})

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Easy quiz requires 10 verified quotes; catalog contains 9"
    }
