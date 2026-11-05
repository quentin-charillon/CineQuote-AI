import random
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.questions import JsonQuestionRepository
from app.repositories.sessions import InMemorySessionRepository
from app.services.quiz import QuizService, get_quiz_service


@pytest.fixture
def quiz_client() -> Iterator[tuple[TestClient, dict[str, str]]]:
    repository = JsonQuestionRepository()
    answers = {question.id: question.film_title for question in repository.list_all()}
    service = QuizService(repository, InMemorySessionRepository(), random.Random(7))
    app.dependency_overrides[get_quiz_service] = lambda: service

    with TestClient(app) as client:
        yield client, answers

    app.dependency_overrides.clear()


def create_session(client: TestClient) -> str:
    response = client.post("/quiz/sessions", json={"difficulty": "easy"})
    assert response.status_code == 201
    assert response.json()["total_questions"] == 10
    return response.json()["session_id"]


def test_session_has_ten_unique_sanitized_questions(
    quiz_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, answers = quiz_client
    session_id = create_session(client)
    seen_ids: set[str] = set()

    for question_number in range(1, 11):
        question_response = client.get(f"/quiz/sessions/{session_id}/question")
        assert question_response.status_code == 200
        question = question_response.json()
        assert question["question_number"] == question_number
        assert len(question["choices"]) == 4
        assert len(set(question["choices"])) == 4
        assert "movie" not in question
        assert "correct_answer" not in question
        assert question["id"] not in seen_ids
        seen_ids.add(question["id"])

        answer_response = client.post(
            f"/quiz/sessions/{session_id}/answers",
            json={"question_id": question["id"], "answer": answers[question["id"]]},
        )
        assert answer_response.status_code == 200

    assert len(seen_ids) == 10


def test_sessions_are_shuffled_independently(
    quiz_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, _ = quiz_client
    first_session = create_session(client)
    second_session = create_session(client)
    first_question = client.get(f"/quiz/sessions/{first_session}/question").json()
    second_question = client.get(f"/quiz/sessions/{second_session}/question").json()

    assert (first_question["id"], first_question["choices"]) != (
        second_question["id"],
        second_question["choices"],
    )


def test_answer_validation_and_server_scoring(
    quiz_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, answers = quiz_client
    session_id = create_session(client)
    question = client.get(f"/quiz/sessions/{session_id}/question").json()
    correct_answer = answers[question["id"]]
    wrong_answer = next(choice for choice in question["choices"] if choice != correct_answer)

    wrong = client.post(
        f"/quiz/sessions/{session_id}/answers",
        json={"question_id": question["id"], "answer": wrong_answer},
    )
    assert wrong.status_code == 200
    assert wrong.json() == {
        "question_id": question["id"],
        "is_correct": False,
        "correct_answer": correct_answer,
        "movie_year": wrong.json()["movie_year"],
        "score": 0,
        "completed": False,
    }

    next_question = client.get(f"/quiz/sessions/{session_id}/question").json()
    correct = client.post(
        f"/quiz/sessions/{session_id}/answers",
        json={"question_id": next_question["id"], "answer": answers[next_question["id"]]},
    )
    assert correct.json()["is_correct"] is True
    assert correct.json()["score"] == 1


def test_completed_session_returns_final_results(
    quiz_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, answers = quiz_client
    session_id = create_session(client)

    for _ in range(10):
        question = client.get(f"/quiz/sessions/{session_id}/question").json()
        response = client.post(
            f"/quiz/sessions/{session_id}/answers",
            json={"question_id": question["id"], "answer": answers[question["id"]]},
        )

    assert response.json()["completed"] is True
    results = client.get(f"/quiz/sessions/{session_id}/results")
    assert results.status_code == 200
    assert results.json() == {"score": 10, "total_questions": 10, "percentage": 100}
    assert client.get(f"/quiz/sessions/{session_id}/question").status_code == 409


def test_invalid_and_out_of_order_requests_are_rejected(
    quiz_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, answers = quiz_client
    session_id = create_session(client)
    question = client.get(f"/quiz/sessions/{session_id}/question").json()

    assert client.get(f"/quiz/sessions/{session_id}/results").status_code == 409
    assert client.get("/quiz/sessions/not-a-session/question").status_code == 404
    assert client.post(
        f"/quiz/sessions/{session_id}/answers",
        json={"question_id": question["id"], "answer": "Not an offered title"},
    ).status_code == 400
    assert client.post(
        f"/quiz/sessions/{session_id}/answers",
        json={"question_id": "stale-question", "answer": question["choices"][0]},
    ).status_code == 409

    client.post(
        f"/quiz/sessions/{session_id}/answers",
        json={"question_id": question["id"], "answer": answers[question["id"]]},
    )
    duplicate = client.post(
        f"/quiz/sessions/{session_id}/answers",
        json={"question_id": question["id"], "answer": answers[question["id"]]},
    )
    assert duplicate.status_code == 409

