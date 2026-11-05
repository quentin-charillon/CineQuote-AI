import random

import pytest

from app.repositories.questions import JsonQuestionRepository
from app.repositories.sessions import InMemorySessionRepository
from app.schemas.quiz import AnswerSubmission, ExplanationRequest, QuizQuestion
from app.services.explanations import ExplanationService
from app.services.quiz import ExplanationUnavailableError, QuizService


class MockExplanationGenerator:
    namespace = "mock:explanation"
    def __init__(self, output: str = "The distinctive wording and tone make this line closely associated with the film.", error: Exception | None = None) -> None:
        self.output=output; self.error=error; self.calls=0
    def generate(self, question: QuizQuestion) -> str:
        self.calls+=1
        if self.error: raise self.error
        return self.output


def test_explanation_is_available_only_after_answer_and_is_cached() -> None:
    repository=JsonQuestionRepository(); answers={q.id:q.film_title for q in repository.list_all()}; generator=MockExplanationGenerator()
    service=QuizService(repository,InMemorySessionRepository(),random.Random(3),explanations=ExplanationService(generator))
    created=service.create_session("easy"); question=service.get_current_question(created.session_id)
    with pytest.raises(ExplanationUnavailableError): service.get_explanation(created.session_id,ExplanationRequest(question_id=question.id))
    service.submit_answer(created.session_id,AnswerSubmission(question_id=question.id,answer=answers[question.id]))
    first=service.get_explanation(created.session_id,ExplanationRequest(question_id=question.id)); second=service.get_explanation(created.session_id,ExplanationRequest(question_id=question.id))
    assert first.explanation==generator.output and first.fallback_used is False
    assert second==first and generator.calls==1


def test_failed_or_distractor_leaking_explanation_uses_safe_fallback() -> None:
    question=JsonQuestionRepository().list_all()[0]
    leaked=ExplanationService(MockExplanationGenerator(f"This sounds like {question.choices[1]}." )).create(question)
    failed=ExplanationService(MockExplanationGenerator(error=TimeoutError())).create(question)
    assert leaked.fallback_used is True and question.film_title in leaked.text
    assert failed.fallback_used is True and question.film_title in failed.text
