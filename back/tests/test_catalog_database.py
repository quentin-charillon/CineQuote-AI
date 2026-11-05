import random
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base, create_database_engine
from app.models.catalog import Film, Genre, Quote
from app.repositories.catalog import SqlAlchemyQuestionRepository, normalize_catalog_text
from app.repositories.sessions import InMemorySessionRepository
from app.services.hints import FallbackHintGenerator, HintService
from app.services.quiz import DatasetValidationError, QuizService


@pytest.fixture
def catalog_factory(tmp_path: Path) -> sessionmaker:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'catalog.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def seed_catalog(factory: sessionmaker, quote_count: int = 10) -> None:
    with factory() as database:
        films = [Film(title=f"Test Film {index}", normalized_title=f"test film {index}", release_year=2000 + index) for index in range(4)]
        database.add_all(films)
        database.flush()
        for index in range(quote_count):
            database.add(Quote(text=f"Synthetic test quote {index}", normalized_text=f"synthetic test quote {index}", difficulty="easy", is_verified=True, film=films[0]))
        for index, film in enumerate(films[1:]):
            database.add(Quote(text=f"Distractor evidence {index}", normalized_text=f"distractor evidence {index}", difficulty="hard", is_verified=True, film=film))
        database.commit()


def test_difficulty_filtering_and_repeated_film_quotes(catalog_factory: sessionmaker) -> None:
    seed_catalog(catalog_factory)
    repository = SqlAlchemyQuestionRepository(catalog_factory)
    service = QuizService(repository, InMemorySessionRepository(), random.Random(2), HintService(FallbackHintGenerator()))

    assert len(repository.list_verified("easy")) == 10
    assert repository.list_verified("medium") == []
    created = service.create_session("easy")
    session = service._sessions.get(created.session_id)  # verify stored quote identity, not public answers
    assert session is not None
    assert len({question.id for question in session.questions}) == 10
    assert {question.film_title for question in session.questions} == {"Test Film 0"}


def test_duplicate_quote_rejected_per_film_but_allowed_for_another_film(catalog_factory: sessionmaker) -> None:
    with catalog_factory() as database:
        first = Film(title="First", normalized_title="first", release_year=2001)
        second = Film(title="Second", normalized_title="second", release_year=2002)
        database.add_all([first, second])
        database.flush()
        text = normalize_catalog_text("Same test line!")
        database.add_all([
            Quote(text="Same test line!", normalized_text=text, difficulty="easy", is_verified=False, film=first),
            Quote(text="Same test line!", normalized_text=text, difficulty="hard", is_verified=False, film=second),
        ])
        database.commit()

        database.add(Quote(text="Same test line!", normalized_text=text, difficulty="medium", is_verified=False, film=first))
        with pytest.raises(IntegrityError):
            database.commit()


def test_genre_filter_supports_multi_genre_film_and_repeated_film_quotes(catalog_factory: sessionmaker) -> None:
    with catalog_factory() as database:
        horror = Genre(name="Horror")
        thriller = Genre(name="Thriller")
        film = Film(title="Multi Genre Film", normalized_title="multi genre film", release_year=2001, genres=[horror, thriller])
        distractors = [Film(title=f"Distractor {index}", normalized_title=f"distractor {index}", release_year=2010 + index, genres=[horror, thriller]) for index in range(3)]
        database.add_all([film, *distractors])
        database.flush()
        for index in range(10):
            database.add(Quote(text=f"Genre test quote {index}", normalized_text=f"genre test quote {index}", difficulty="easy", is_verified=True, film=film))
        for index, distractor in enumerate(distractors):
            database.add(Quote(text=f"Verified distractor {index}", normalized_text=f"verified distractor {index}", difficulty="hard", is_verified=True, film=distractor))
        database.commit()

    repository = SqlAlchemyQuestionRepository(catalog_factory)
    assert len(repository.list_verified("easy", "horror")) == 10
    assert len(repository.list_verified("easy", "thriller")) == 10
    assert repository.list_verified("easy", "comedy") == []

    service = QuizService(repository, InMemorySessionRepository(), random.Random(4), HintService(FallbackHintGenerator()))
    created = service.create_session("easy", "horror")
    session = service._sessions.get(created.session_id)
    assert session is not None
    assert len({question.id for question in session.questions}) == 10
    assert {question.film_title for question in session.questions} == {"Multi Genre Film"}
    allowed = {"Multi Genre Film", "Distractor 0", "Distractor 1", "Distractor 2"}
    assert all(set(question.choices) == allowed for question in session.questions)


def test_genre_availability_and_insufficient_combination(catalog_factory: sessionmaker) -> None:
    seed_catalog(catalog_factory, quote_count=10)
    repository = SqlAlchemyQuestionRepository(catalog_factory)
    service = QuizService(repository, InMemorySessionRepository(), random.Random(1), HintService(FallbackHintGenerator()))

    availability = {(item.genre, item.difficulty): item for item in service.list_availability()}
    assert availability[("all", "easy")].available is True
    assert availability[("horror", "easy")].verified_questions == 0
    assert availability[("horror", "easy")].available is False
    with pytest.raises(DatasetValidationError, match="Horror \\+ Easy requires 10 verified quotes; catalog contains 0"):
        service.create_session("easy", "horror")


def test_dynamic_choices_are_diverse_distinct_and_seeded(catalog_factory: sessionmaker) -> None:
    with catalog_factory() as database:
        films = [Film(title=f"Catalog Film {index}", normalized_title=f"catalog film {index}", release_year=1980 + index) for index in range(16)]
        database.add_all(films)
        database.flush()
        for index, film in enumerate(films):
            database.add(Quote(
                text=f"Dynamic quote {index}", normalized_text=f"dynamic quote {index}",
                difficulty="easy" if index < 10 else "hard", is_verified=True, film=film,
            ))
        database.commit()

    def build(seed: int) -> list[tuple[str, tuple[str, ...]]]:
        service = QuizService(SqlAlchemyQuestionRepository(catalog_factory), InMemorySessionRepository(), random.Random(seed), HintService(FallbackHintGenerator()))
        created = service.create_session("easy")
        session = service._sessions.get(created.session_id)
        assert session is not None
        return [(question.film_title, tuple(question.choices)) for question in session.questions]

    first = build(23)
    repeated = build(23)
    assert first == repeated
    assert len({tuple(choice for choice in choices if choice != correct) for correct, choices in first}) > 1
    assert len({choices.index(correct) for correct, choices in first}) > 1
    for correct, choices in first:
        assert len(choices) == len(set(choices)) == 4
        assert choices.count(correct) == 1


def test_genre_with_fewer_than_four_films_does_not_fall_back_to_wider_catalog(catalog_factory: sessionmaker) -> None:
    with catalog_factory() as database:
        horror = Genre(name="Horror")
        correct = Film(title="Horror Lead", normalized_title="horror lead", release_year=2000, genres=[horror])
        horror_alternatives = [Film(title=f"Horror Alt {index}", normalized_title=f"horror alt {index}", release_year=1999 + index, genres=[horror]) for index in range(2)]
        wider = [Film(title=f"Wider Film {index}", normalized_title=f"wider film {index}", release_year=1998 + index) for index in range(4)]
        database.add_all([correct, *horror_alternatives, *wider])
        database.flush()
        for index in range(10):
            database.add(Quote(text=f"Repeated film quote {index}", normalized_text=f"repeated film quote {index}", difficulty="easy", is_verified=True, film=correct))
        for index, film in enumerate([*horror_alternatives, *wider]):
            database.add(Quote(text=f"Candidate quote {index}", normalized_text=f"candidate quote {index}", difficulty="hard", is_verified=True, film=film))
        database.commit()

    service = QuizService(SqlAlchemyQuestionRepository(catalog_factory), InMemorySessionRepository(), random.Random(8), HintService(FallbackHintGenerator()))
    availability = {(item.genre, item.difficulty): item for item in service.list_availability()}
    assert availability[("horror", "easy")].eligible_films == 3
    assert availability[("horror", "easy")].available is False
    with pytest.raises(DatasetValidationError, match="requires four distinct verified films"):
        service.create_session("easy", "horror")


@pytest.mark.parametrize("genre,difficulty", [
    ("adventure", "easy"), ("adventure", "medium"), ("adventure", "hard"),
    ("thriller", "medium"), ("horror", "hard"),
])
def test_named_genre_sessions_never_leak_questions_or_choices(
    catalog_factory: sessionmaker, genre: str, difficulty: str,
) -> None:
    with catalog_factory() as database:
        genres = {name: Genre(name=name.title()) for name in ("adventure", "thriller", "horror")}
        films: dict[str, list[Film]] = {}
        for name, genre_model in genres.items():
            films[name] = [
                Film(title=f"{name.title()} Film {index}", normalized_title=f"{name} film {index}", release_year=1990 + index, genres=[genre_model])
                for index in range(4)
            ]
            database.add_all(films[name])
        # One canonical film legitimately belongs to more than one genre.
        films["adventure"][0].genres.append(genres["thriller"])
        database.flush()
        quote_index = 0
        for name, levels in {"adventure": ("easy", "medium", "hard"), "thriller": ("medium",), "horror": ("hard",)}.items():
            for level in levels:
                for index in range(10):
                    database.add(Quote(
                        text=f"Strict quote {quote_index}", normalized_text=f"strict quote {quote_index}", difficulty=level,
                        is_verified=True, film=films[name][index % 4],
                    ))
                    quote_index += 1
        database.commit()

    service = QuizService(SqlAlchemyQuestionRepository(catalog_factory), InMemorySessionRepository(), random.Random(11), HintService(FallbackHintGenerator()))
    created = service.create_session(difficulty, genre)  # type: ignore[arg-type]
    session = service._sessions.get(created.session_id)
    assert session is not None
    allowed = {film.title for film in films[genre]}
    if genre == "thriller":
        allowed.add(films["adventure"][0].title)
    assert len(session.questions) == 10
    for question in session.questions:
        assert question.film_title in allowed
        assert len(question.choices) == len(set(question.choices)) == 4
        assert set(question.choices).issubset(allowed)
