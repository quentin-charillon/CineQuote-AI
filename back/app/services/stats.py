from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.database import SessionLocal
from app.models.account import QuizAttempt, QuizAttemptAnswer
from app.schemas.account import AttemptResponse, StatsBreakdown, UserStatsResponse


class StatsService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def record(self, *, user_id: int, session_id: str, genre: str, difficulty: str,
               score: int, total: int, hints_used: int,
               answers: list[tuple[str, bool]] | None = None) -> None:
        with self._session_factory() as database:
            attempt = QuizAttempt(
                user_id=user_id, quiz_session_id=session_id, genre=genre, difficulty=difficulty,
                score=score, total_questions=total, percentage=round(score / total * 100), hints_used=hints_used,
            )
            database.add(attempt)
            try:
                database.flush()
                database.add_all(QuizAttemptAnswer(attempt_id=attempt.id, film_title=title, correct=correct)
                                 for title, correct in (answers or []))
                database.commit()
            except IntegrityError:
                database.rollback()

    def get(self, user_id: int) -> UserStatsResponse:
        with self._session_factory() as database:
            attempts = database.scalars(
                select(QuizAttempt).where(QuizAttempt.user_id == user_id).order_by(QuizAttempt.completed_at.desc())
            ).all()
        games = len(attempts)
        total_correct = sum(item.score for item in attempts)
        total_questions = sum(item.total_questions for item in attempts)
        return UserStatsResponse(
            games_played=games,
            average_percentage=round(sum(item.percentage for item in attempts) / games) if games else 0,
            best_percentage=max((item.percentage for item in attempts), default=0),
            total_correct=total_correct,
            total_questions=total_questions,
            accuracy_percentage=round(total_correct / total_questions * 100) if total_questions else 0,
            hints_used=sum(item.hints_used for item in attempts),
            by_genre=self._breakdown(attempts, "genre"),
            by_difficulty=self._breakdown(attempts, "difficulty"),
            recent_attempts=[AttemptResponse.model_validate({
                "genre": item.genre, "difficulty": item.difficulty, "score": item.score,
                "total_questions": item.total_questions, "percentage": item.percentage,
                "hints_used": item.hints_used, "completed_at": item.completed_at,
            }) for item in attempts[:10]],
        )

    @staticmethod
    def _breakdown(attempts: list[QuizAttempt], attribute: str) -> list[StatsBreakdown]:
        groups: dict[str, list[QuizAttempt]] = defaultdict(list)
        for attempt in attempts:
            groups[getattr(attempt, attribute)].append(attempt)
        return [StatsBreakdown(
            label=label, games_played=len(items),
            average_percentage=round(sum(item.percentage for item in items) / len(items)),
            best_percentage=max(item.percentage for item in items),
        ) for label, items in sorted(groups.items())]


stats_service = StatsService(SessionLocal)
