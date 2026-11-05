import random
from threading import RLock
from uuid import uuid4

from app.config import get_settings
from app.database import SessionLocal
from app.repositories.catalog import SqlAlchemyQuestionRepository
from app.repositories.questions import JsonQuestionRepository
from app.repositories.sessions import InMemorySessionRepository, QuizSession
from app.schemas.quiz import (
    AnswerResult,
    AnswerSubmission,
    HintRequest,
    HintResponse,
    ExplanationRequest,
    ExplanationResponse,
    Difficulty,
    DifficultyAvailability,
    FilmChoiceCandidate,
    Genre,
    QuizAvailability,
    PublicQuestion,
    QuizResults,
    SessionCreated,
)
from app.services.hints import HintService, build_hint_service
from app.services.stats import StatsService, stats_service
from app.services.explanations import ExplanationService, explanation_service


class SessionNotFoundError(Exception):
    pass


class QuizCompletedError(Exception):
    pass


class QuizNotCompletedError(Exception):
    pass


class StaleQuestionError(Exception):
    pass


class InvalidAnswerError(Exception):
    pass


class HintAlreadyUsedError(Exception):
    pass


class ExplanationUnavailableError(Exception):
    pass


class DatasetValidationError(Exception):
    pass


class QuizService:
    SESSION_SIZE = 10

    def __init__(
        self,
        questions: JsonQuestionRepository,
        sessions: InMemorySessionRepository,
        random_source: random.Random | None = None,
        hint_service: HintService | None = None,
        statistics: StatsService | None = None,
        explanations: ExplanationService | None = None,
    ) -> None:
        self._questions = questions
        self._sessions = sessions
        self._random = random_source or random.Random()
        self._lock = RLock()
        self._hint_service = hint_service or build_hint_service(get_settings())
        self._statistics = statistics
        self._explanations = explanations or explanation_service

    GENRES: tuple[Genre, ...] = ("all", "horror", "comedy", "science_fiction", "thriller", "action", "animation", "romance", "fantasy", "adventure")

    def create_session(self, difficulty: Difficulty, genre: Genre = "all", user_id: int | None = None) -> SessionCreated:
        with self._lock:
            question_pool = self._questions.list_verified(difficulty, genre)
            all_films = self._questions.list_verified_films("all")
            if len(all_films) < 4:
                raise DatasetValidationError(
                    f"Quiz answer generation requires four distinct verified films; catalog contains {len(all_films)}"
                )
            eligible_films = all_films if genre == "all" else self._questions.list_verified_films(genre)
            label = "All Genres" if genre == "all" else genre.replace("_", " ").title()
            return self._create_from_pool(question_pool, eligible_films, difficulty, genre, label, user_id, custom=False)

    def create_custom_session(self, difficulty: Difficulty, genres: list[Genre], user_id: int | None = None) -> SessionCreated:
        with self._lock:
            if "all" in genres:
                return self.create_session(difficulty, "all", user_id)
            questions = {question.id: question for genre in genres for question in self._questions.list_verified(difficulty, genre)}
            films = {film.title: film for genre in genres for film in self._questions.list_verified_films(genre)}
            label = " + ".join(genre.replace("_", " ").title() for genre in genres)
            return self._create_from_pool(list(questions.values()), list(films.values()), difficulty, "+".join(genres), label, user_id, custom=True)

    def _create_from_pool(self, question_pool: list, eligible_films: list[FilmChoiceCandidate], difficulty: Difficulty, genre_label_value: str, label: str, user_id: int | None, custom: bool) -> SessionCreated:
            if len(question_pool) < self.SESSION_SIZE:
                prefix = f"{difficulty.title()} quiz" if genre_label_value == "all" else f"{label} + {difficulty.title()}"
                qualifier = "" if custom else "verified "
                raise DatasetValidationError(f"{prefix} requires {self.SESSION_SIZE} {qualifier}quotes; catalog contains {len(question_pool)}")
            if len(eligible_films) < 4:
                qualifier = "" if custom else "verified "
                raise DatasetValidationError(f"{label} quiz requires four distinct {qualifier}films for answer choices; catalog contains {len(eligible_films)}")
            selected = self._random.sample(question_pool, self.SESSION_SIZE)
            used_distractors: set[str] = set()
            for question in selected:
                distractors = self._build_distractors(question.film_title, question.release_year, eligible_films, used_distractors)
                question.choices = [question.film_title, *distractors]
                self._random.shuffle(question.choices)

            session = QuizSession(id=str(uuid4()), questions=selected, difficulty=difficulty, genre=genre_label_value, user_id=user_id)
            self._sessions.add(session)
            return SessionCreated(session_id=session.id, total_questions=len(selected))

    def _build_distractors(
        self,
        correct_title: str,
        release_year: int | None,
        eligible_films: list[FilmChoiceCandidate],
        used: set[str],
    ) -> list[str]:
        chosen: list[FilmChoiceCandidate] = []
        self._take_candidates(chosen, eligible_films, correct_title, release_year, used, 3)
        # Preserve genre relevance even after the small genre-specific pool has
        # appeared elsewhere in the session.
        self._take_candidates(chosen, eligible_films, correct_title, release_year, set(), 3)
        # Reuse across questions only when the unused catalog cannot fill the row.
        if len(chosen) < 3:
            self._take_candidates(chosen, eligible_films, correct_title, release_year, set(), 3)
        if len(chosen) != 3:
            raise DatasetValidationError("Quiz answer generation requires four distinct verified film titles")
        titles = [candidate.title for candidate in chosen]
        used.update(titles)
        return titles

    def _take_candidates(
        self,
        chosen: list[FilmChoiceCandidate],
        pool: list[FilmChoiceCandidate],
        correct_title: str,
        release_year: int | None,
        excluded: set[str],
        target: int,
    ) -> None:
        already = {candidate.title for candidate in chosen}
        eligible = [candidate for candidate in pool if candidate.title != correct_title and candidate.title not in excluded and candidate.title not in already]
        eligible.sort(
            key=lambda candidate: abs(candidate.release_year - release_year)
            if candidate.release_year is not None and release_year is not None
            else 10_000
        )
        plausible_window = eligible[: min(12, len(eligible))]
        needed = min(target - len(chosen), len(plausible_window))
        if needed > 0:
            chosen.extend(self._random.sample(plausible_window, needed))

    def list_difficulties(self) -> list[DifficultyAvailability]:
        counts = self._questions.count_verified_by_difficulty()
        return [
            DifficultyAvailability(
                difficulty=difficulty,
                verified_questions=counts.get(difficulty, 0),
                required_questions=self.SESSION_SIZE,
                available=counts.get(difficulty, 0) >= self.SESSION_SIZE,
            )
            for difficulty in ("easy", "medium", "hard")
        ]

    def list_availability(self) -> list[QuizAvailability]:
        counts = self._questions.count_verified_by_genre_and_difficulty()
        film_counts = self._questions.count_verified_films_by_genre()
        return [
            QuizAvailability(
                genre=genre,
                difficulty=difficulty,
                verified_questions=counts.get((genre, difficulty), 0),
                required_questions=self.SESSION_SIZE,
                eligible_films=film_counts.get(genre, 0),
                required_films=4,
                available=counts.get((genre, difficulty), 0) >= self.SESSION_SIZE and film_counts.get(genre, 0) >= 4,
            )
            for genre in self.GENRES
            for difficulty in ("easy", "medium", "hard")
        ]

    def get_current_question(self, session_id: str) -> PublicQuestion:
        with self._lock:
            session = self._get_session(session_id)
            if session.completed:
                raise QuizCompletedError

            question = session.questions[session.current_index]
            return PublicQuestion(
                id=question.id,
                quote=question.quote,
                choices=question.choices,
                question_number=session.current_index + 1,
                total_questions=len(session.questions),
                score=session.score,
                hint_used=question.id in session.hinted_question_ids,
            )

    def get_hint(self, session_id: str, request: HintRequest) -> HintResponse:
        with self._lock:
            session = self._get_session(session_id)
            if session.completed:
                raise QuizCompletedError

            question = session.questions[session.current_index]
            if request.question_id != question.id:
                raise StaleQuestionError
            if question.id in session.hinted_question_ids:
                raise HintAlreadyUsedError

            # Reserve the one allowed hint before leaving the lock so concurrent
            # requests cannot generate multiple hints for the same question.
            session.hinted_question_ids.add(question.id)

        generated = self._hint_service.create_hint(question)
        return HintResponse(
            question_id=question.id,
            hint=generated.text,
            fallback_used=generated.fallback_used,
        )

    def get_explanation(self, session_id: str, request: ExplanationRequest) -> ExplanationResponse:
        with self._lock:
            session = self._get_session(session_id)
            question = next((item for item in session.questions[:session.current_index] if item.id == request.question_id), None)
            if question is None:
                raise ExplanationUnavailableError
        generated = self._explanations.create(question)
        return ExplanationResponse(question_id=question.id, explanation=generated.text, fallback_used=generated.fallback_used)

    def submit_answer(self, session_id: str, submission: AnswerSubmission) -> AnswerResult:
        with self._lock:
            session = self._get_session(session_id)
            if session.completed:
                raise QuizCompletedError

            question = session.questions[session.current_index]
            if submission.question_id != question.id:
                raise StaleQuestionError
            if submission.answer not in question.choices:
                raise InvalidAnswerError

            is_correct = submission.answer == question.film_title
            if is_correct:
                session.score += 1
            session.answered_films.append((question.film_title, is_correct))
            session.current_index += 1

            if session.completed and session.user_id is not None and not session.attempt_recorded and self._statistics is not None:
                self._statistics.record(
                    user_id=session.user_id, session_id=session.id, genre=session.genre,
                    difficulty=session.difficulty, score=session.score, total=len(session.questions),
                    hints_used=len(session.hinted_question_ids), answers=session.answered_films,
                )
                session.attempt_recorded = True

            return AnswerResult(
                question_id=question.id,
                is_correct=is_correct,
                correct_answer=question.film_title,
                movie_year=question.release_year,
                score=session.score,
                completed=session.completed,
            )

    def get_results(self, session_id: str) -> QuizResults:
        with self._lock:
            session = self._get_session(session_id)
            if not session.completed:
                raise QuizNotCompletedError

            total = len(session.questions)
            return QuizResults(
                score=session.score,
                total_questions=total,
                percentage=round((session.score / total) * 100),
            )

    def _get_session(self, session_id: str) -> QuizSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError
        return session


question_repository = SqlAlchemyQuestionRepository(SessionLocal)
_settings = get_settings()
session_repository = InMemorySessionRepository(
    ttl_seconds=_settings.quiz_session_ttl_seconds,
    max_sessions=_settings.quiz_session_max_active,
)
quiz_service = QuizService(question_repository, session_repository, statistics=stats_service)


def get_quiz_service() -> QuizService:
    return quiz_service
