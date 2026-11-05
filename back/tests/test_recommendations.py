import json
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.database import Base, create_database_engine
from app.models.account import QuizAttempt, QuizAttemptAnswer, User
from app.models.catalog import Film, Genre, Quote
from app.services.recommendations import RecommendationService


class MockGenerator:
    namespace = "mock:recommendations"
    def __init__(self, output: str) -> None: self.output = output; self.calls = 0
    def generate(self, genres, candidates) -> str:
        self.calls += 1
        return self.output


class MockSource:
    def fetch(self, title: str, year: int | None):
        return (f"{title} is a film whose opening premise is available from this mocked public source extract.", f"https://example.test/{title}")


def seeded_factory(tmp_path: Path) -> tuple[sessionmaker, int]:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'recommendations.db'}")
    Base.metadata.create_all(engine); factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as database:
        horror = Genre(name="Horror"); comedy = Genre(name="Comedy")
        films = []
        for index, (title, genre) in enumerate([("Recognized", horror), ("Alpha", horror), ("Beta", horror), ("Gamma", horror), ("Delta", comedy)]):
            film = Film(title=title, normalized_title=title.lower(), release_year=2000 + index, genres=[genre])
            film.quotes.append(Quote(text=f"Quote {index}", normalized_text=f"quote {index}", difficulty="easy", is_verified=True))
            films.append(film)
        user = User(email="r@example.com", normalized_email="r@example.com", username="Recs", normalized_username="recs", password_hash="unused")
        database.add_all([horror, comedy, user, *films]); database.flush()
        attempt = QuizAttempt(user_id=user.id, quiz_session_id="s1", genre="horror", difficulty="easy", score=9, total_questions=10, percentage=90, hints_used=0)
        database.add(attempt); database.flush(); database.add_all([
            QuizAttemptAnswer(attempt_id=attempt.id, film_title="Recognized", correct=True),
            QuizAttemptAnswer(attempt_id=attempt.id, film_title="Alpha", correct=False),
            QuizAttemptAnswer(attempt_id=attempt.id, film_title="Beta", correct=False),
            QuizAttemptAnswer(attempt_id=attempt.id, film_title="Gamma", correct=False),
            QuizAttemptAnswer(attempt_id=attempt.id, film_title="Delta", correct=False),
        ])
        database.commit(); return factory, user.id


def test_recommendations_include_every_film_missed_in_latest_game(tmp_path: Path) -> None:
    factory, user_id = seeded_factory(tmp_path)
    summaries = [{"title": title, "summary": f"A factual spoiler-free synopsis for {title}, written long enough for validation."} for title in ["Alpha", "Beta", "Gamma", "Delta"]]
    generator = MockGenerator(json.dumps({"intro": "Review all four films missed in your latest game.", "films": summaries}))
    result = RecommendationService(factory, generator).create(user_id)
    assert [item.title for item in result.recommendations] == ["Alpha", "Beta", "Gamma", "Delta"]
    assert all(item.reason == "Correct answer missed in your latest game." for item in result.recommendations)
    assert result.fallback_used is True and generator.calls == 0
    assert all("Characters, events and story details are intentionally hidden" in item.summary for item in result.recommendations)


def test_invented_provider_title_is_rejected(tmp_path: Path) -> None:
    factory, user_id = seeded_factory(tmp_path)
    generator = MockGenerator(json.dumps({"intro": "These are definitely worth watching next.", "films": [
        {"title": "Invented Movie", "summary": "An invented title that must be rejected by the strict server allowlist."},
        {"title": "Alpha", "summary": "A sufficiently long synopsis that should not rescue this invalid response."},
    ]}))
    result = RecommendationService(factory, generator).create(user_id)
    assert result.fallback_used is True
    assert "Invented Movie" not in {item.title for item in result.recommendations}
    assert generator.calls == 0


def test_source_based_safe_synopses_are_accepted_and_spoilers_rejected(tmp_path: Path) -> None:
    factory, user_id = seeded_factory(tmp_path)
    films = [{"title": title, "summary": f"The initial setting of {title} introduces its central situation while leaving every later event and outcome undisclosed."} for title in ["Alpha", "Beta", "Gamma", "Delta"]]
    safe = RecommendationService(factory, MockGenerator(json.dumps({"intro": "These opening premises avoid later story developments.", "films": films})), source=MockSource()).create(user_id)
    assert safe.fallback_used is False
    assert all(item.source_url and item.source_url.startswith("https://example.test/") for item in safe.recommendations)

    spoiled_films = [*films]
    spoiled_films[0] = {"title": "Alpha", "summary": "In the end, the killer is revealed and the central character survives the final confrontation."}
    blocked = RecommendationService(factory, MockGenerator(json.dumps({"intro": "This response contains a forbidden revelation.", "films": spoiled_films})), source=MockSource()).create(user_id)
    assert blocked.fallback_used is True
    assert "story details are intentionally hidden" in blocked.recommendations[0].summary
