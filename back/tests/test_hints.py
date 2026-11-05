import random
from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.repositories.questions import JsonQuestionRepository
from app.repositories.sessions import InMemorySessionRepository
from app.schemas.quiz import QuizQuestion
from app.services.hints import (
    FALLBACK_HINT,
    GroqHintGenerator,
    HintService,
    InMemoryHintCache,
    InMemoryRateLimiter,
    OpenAIHintGenerator,
)
from app.services.quiz import QuizService, get_quiz_service


class MockHintGenerator:
    def __init__(self, output: str = "Notice the line's confident, futuristic tone.", error: Exception | None = None) -> None:
        self.output = output
        self.error = error
        self.calls = 0
        self.cache_namespace = "mock:test-model"

    def generate(self, question: QuizQuestion) -> str:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.output.replace("{title}", question.film_title)


@pytest.fixture
def hint_client() -> Iterator[tuple[TestClient, MockHintGenerator, dict[str, str]]]:
    questions = JsonQuestionRepository()
    answers = {question.id: question.film_title for question in questions.list_all()}
    generator = MockHintGenerator()
    service = QuizService(
        questions,
        InMemorySessionRepository(),
        random.Random(11),
        HintService(generator),
    )
    app.dependency_overrides[get_quiz_service] = lambda: service
    with TestClient(app) as client:
        yield client, generator, answers
    app.dependency_overrides.clear()


def start_question(client: TestClient) -> tuple[str, dict[str, object]]:
    session_id = client.post("/quiz/sessions", json={"difficulty": "easy"}).json()["session_id"]
    question = client.get(f"/quiz/sessions/{session_id}/question").json()
    return session_id, question


def test_successful_hint_is_returned_once(
    hint_client: tuple[TestClient, MockHintGenerator, dict[str, str]],
) -> None:
    client, generator, _ = hint_client
    session_id, question = start_question(client)
    response = client.post(
        f"/quiz/sessions/{session_id}/hint",
        json={"question_id": question["id"]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "question_id": question["id"],
        "hint": generator.output,
        "fallback_used": False,
    }
    assert generator.calls == 1
    assert client.get(f"/quiz/sessions/{session_id}/question").json()["hint_used"] is True
    repeated = client.post(
        f"/quiz/sessions/{session_id}/hint",
        json={"question_id": question["id"]},
    )
    assert repeated.status_code == 409
    assert generator.calls == 1


@pytest.mark.parametrize(
    ("output", "error"),
    [
        ("The answer is {title}.", None),
        ("Option B is the best fit.", None),
        ("", TimeoutError("provider timed out")),
        ("", RuntimeError("mock 429 quota exhausted")),
        ("", RuntimeError("mock provider error")),
    ],
)
def test_unsafe_or_failed_generation_uses_fallback(
    output: str,
    error: Exception | None,
) -> None:
    generator = MockHintGenerator(output=output, error=error)
    question = JsonQuestionRepository().list_all()[0]

    result = HintService(generator).create_hint(question)

    assert result.text == FALLBACK_HINT
    assert result.fallback_used is True
    assert result.validation_passed is False


def test_missing_api_key_uses_fallback_without_a_request() -> None:
    generator = OpenAIHintGenerator(Settings(openai_api_key=None))
    question = JsonQuestionRepository().list_all()[0]

    result = HintService(generator).create_hint(question)

    assert result.text == FALLBACK_HINT
    assert result.fallback_used is True


def test_missing_groq_api_key_uses_fallback_without_a_request() -> None:
    generator = GroqHintGenerator(Settings(groq_api_key=None))
    question = JsonQuestionRepository().list_all()[0]

    result = HintService(generator).create_hint(question)

    assert result.text == FALLBACK_HINT
    assert result.fallback_used is True


def test_groq_generator_uses_expected_model_and_reasoning_settings() -> None:
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Consider the line's dramatic tone."))]
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: response)
        )
    )
    captured: dict[str, object] = {}

    def fake_create(**kwargs: object) -> object:
        captured.update(kwargs)
        return response

    client.chat.completions.create = fake_create
    generator = GroqHintGenerator(Settings(groq_api_key="test-key"), client=client)
    question = JsonQuestionRepository().list_all()[0]

    assert generator.generate(question) == "Consider the line's dramatic tone."
    assert captured["model"] == "openai/gpt-oss-20b"
    assert captured["reasoning_effort"] == "low"
    assert captured["include_reasoning"] is False
    assert captured["max_completion_tokens"] == 128


def test_cache_reuses_only_validated_safe_hints() -> None:
    question = JsonQuestionRepository().list_all()[0]
    cache = InMemoryHintCache(enabled=True)
    safe_generator = MockHintGenerator(output="Consider the line's hopeful tone.")
    safe_service = HintService(safe_generator, cache=cache)

    assert safe_service.create_hint(question).fallback_used is False
    assert safe_service.create_hint(question).fallback_used is False
    assert safe_generator.calls == 1

    unsafe_generator = MockHintGenerator(output="The film is {title}.")
    unsafe_generator.cache_namespace = "mock:unsafe-model"
    unsafe_service = HintService(unsafe_generator, cache=cache)
    assert unsafe_service.create_hint(question).fallback_used is True
    assert unsafe_service.create_hint(question).fallback_used is True
    assert unsafe_generator.calls == 2


def test_in_memory_rate_limit_falls_back_without_second_provider_call() -> None:
    questions = JsonQuestionRepository().list_all()[:2]
    generator = MockHintGenerator()
    service = HintService(generator, rate_limiter=InMemoryRateLimiter(1, 60))

    assert service.create_hint(questions[0]).fallback_used is False
    limited = service.create_hint(questions[1])

    assert limited.text == FALLBACK_HINT
    assert limited.fallback_used is True
    assert generator.calls == 1


def test_hint_rejects_missing_and_already_answered_questions(
    hint_client: tuple[TestClient, MockHintGenerator, dict[str, str]],
) -> None:
    client, generator, answers = hint_client
    assert client.post(
        "/quiz/sessions/missing/hint",
        json={"question_id": "missing"},
    ).status_code == 404

    session_id, question = start_question(client)
    client.post(
        f"/quiz/sessions/{session_id}/answers",
        json={"question_id": question["id"], "answer": answers[str(question["id"])]},
    )
    response = client.post(
        f"/quiz/sessions/{session_id}/hint",
        json={"question_id": question["id"]},
    )
    assert response.status_code == 409
    assert generator.calls == 0

