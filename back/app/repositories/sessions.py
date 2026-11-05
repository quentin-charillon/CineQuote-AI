from dataclasses import dataclass, field
from threading import RLock
from time import monotonic
from typing import Callable

from app.schemas.quiz import QuizQuestion
from app.schemas.quiz import Difficulty, Genre


@dataclass
class QuizSession:
    id: str
    questions: list[QuizQuestion]
    difficulty: Difficulty = "easy"
    genre: str = "all"
    user_id: int | None = None
    current_index: int = 0
    score: int = 0
    hinted_question_ids: set[str] = field(default_factory=set)
    attempt_recorded: bool = False
    answered_films: list[tuple[str, bool]] = field(default_factory=list)
    created_at: float = field(default_factory=monotonic)
    last_accessed_at: float = field(default_factory=monotonic)

    @property
    def completed(self) -> bool:
        return self.current_index >= len(self.questions)


class InMemorySessionRepository:
    """Process-local session storage; all sessions disappear on restart."""

    def __init__(self, ttl_seconds: int = 3600, max_sessions: int = 2000, clock: Callable[[], float] = monotonic) -> None:
        self._sessions: dict[str, QuizSession] = {}
        self._lock = RLock()
        self._ttl_seconds = ttl_seconds
        self._max_sessions = max_sessions
        self._clock = clock

    def add(self, session: QuizSession) -> None:
        with self._lock:
            now = self._clock()
            session.created_at = now
            session.last_accessed_at = now
            self._prune(now)
            while len(self._sessions) >= self._max_sessions:
                oldest = min(self._sessions.values(), key=lambda item: item.last_accessed_at)
                del self._sessions[oldest.id]
            self._sessions[session.id] = session

    def get(self, session_id: str) -> QuizSession | None:
        with self._lock:
            now = self._clock()
            self._prune(now)
            session = self._sessions.get(session_id)
            if session is not None:
                session.last_accessed_at = now
            return session

    def _prune(self, now: float) -> None:
        expired = [
            session_id for session_id, session in self._sessions.items()
            if now - session.last_accessed_at >= self._ttl_seconds
        ]
        for session_id in expired:
            del self._sessions[session_id]

    def __len__(self) -> int:
        with self._lock:
            self._prune(self._clock())
            return len(self._sessions)

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()

