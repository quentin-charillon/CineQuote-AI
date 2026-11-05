from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.database import Base, create_database_engine
from app.models.account import QuizAttempt, User
from app.services.coach import CoachPlan, CoachService


class MockCoachGenerator:
    namespace = "mock:coach"
    def __init__(self, output: str = "Your horror instincts are sharp. Try a medium screening next.", error: Exception | None = None) -> None:
        self.output = output; self.error = error; self.calls = 0; self.plan: CoachPlan | None = None
    def generate(self, plan: CoachPlan) -> str:
        self.calls += 1; self.plan = plan
        if self.error: raise self.error
        return self.output


def factory(tmp_path: Path) -> sessionmaker:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'coach.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def seed(session_factory: sessionmaker) -> int:
    with session_factory() as database:
        user = User(email="c@example.com", normalized_email="c@example.com", username="Coach", normalized_username="coach", password_hash="unused")
        database.add(user); database.flush()
        database.add_all([
            QuizAttempt(user_id=user.id, quiz_session_id="one", genre="horror", difficulty="easy", score=9, total_questions=10, percentage=90, hints_used=0),
            QuizAttempt(user_id=user.id, quiz_session_id="two", genre="science_fiction", difficulty="hard", score=4, total_questions=10, percentage=40, hints_used=1),
        ])
        database.commit(); return user.id


def test_coach_uses_server_calculated_plan_and_caches(tmp_path: Path) -> None:
    session_factory = factory(tmp_path); user_id = seed(session_factory); generator = MockCoachGenerator()
    service = CoachService(session_factory, generator)
    result = service.create(user_id); repeated = service.create(user_id)
    assert result.summary == generator.output and result.fallback_used is False
    assert result.strength == "horror · easy"
    assert result.improvement == "science_fiction · hard"
    assert result.recommended_genre == "horror"
    assert result.recommended_difficulty == "medium"
    assert repeated == result and generator.calls == 1


def test_invalid_provider_output_and_missing_history_use_safe_fallback(tmp_path: Path) -> None:
    session_factory = factory(tmp_path); user_id = seed(session_factory)
    invalid = CoachService(session_factory, MockCoachGenerator("bad" )).create(user_id)
    assert invalid.fallback_used is True
    empty_generator = MockCoachGenerator()
    empty = CoachService(session_factory, empty_generator).create(999)
    assert empty.games_analyzed == 0 and empty.fallback_used is True
    assert empty_generator.calls == 0
