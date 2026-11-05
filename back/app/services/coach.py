import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from threading import RLock
from time import perf_counter
from typing import Any, Protocol

from groq import Groq
from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models.account import QuizAttempt
from app.schemas.account import CoachResponse
from app.services.hints import CombinedRateLimiter, InMemoryRateLimiter, global_ai_limiter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CoachPlan:
    games: int
    average: int
    strength: str
    strength_average: int
    improvement: str
    improvement_average: int
    recommended_genre: str
    recommended_difficulty: str


class CoachGenerator(Protocol):
    namespace: str
    def generate(self, plan: CoachPlan) -> str: ...


def coach_prompt(plan: CoachPlan) -> str:
    return (
        "Write a warm, concise movie-quiz coaching note in English. Use no more than three short sentences. "
        "Use only the aggregate facts below. Do not invent films, scores, personal details, or statistics. "
        "Do not mention AI. Encourage the recommended next mode. Return only the note.\n\n"
        f"Games analyzed: {plan.games}\nOverall average: {plan.average}%\n"
        f"Strongest area: {plan.strength} ({plan.strength_average}%)\n"
        f"Area to improve: {plan.improvement} ({plan.improvement_average}%)\n"
        f"Recommended next mode: {plan.recommended_genre} + {plan.recommended_difficulty}"
    )


class GroqCoachGenerator:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._model = settings.groq_model; self.namespace = f"groq:{self._model}"
        self._max_tokens = settings.groq_max_completion_tokens
        self._client = client or (Groq(api_key=settings.groq_api_key.get_secret_value(), timeout=settings.groq_timeout_seconds, max_retries=0) if settings.groq_api_key else None)

    def generate(self, plan: CoachPlan) -> str:
        if self._client is None: raise RuntimeError("Groq is not configured")
        request: dict[str, Any] = {"model": self._model, "messages": [{"role": "user", "content": coach_prompt(plan)}], "max_completion_tokens": self._max_tokens, "temperature": .4}
        if self._model.startswith("openai/gpt-oss-"):
            request.update(reasoning_effort="low", include_reasoning=False)
        content = self._client.chat.completions.create(**request).choices[0].message.content
        return content.strip() if isinstance(content, str) else ""


class OpenAICoachGenerator:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._model = settings.openai_model; self.namespace = f"openai:{self._model}"
        self._max_tokens = settings.openai_max_output_tokens
        self._client = client or (OpenAI(api_key=settings.openai_api_key.get_secret_value(), timeout=settings.openai_timeout_seconds, max_retries=0) if settings.openai_api_key else None)

    def generate(self, plan: CoachPlan) -> str:
        if self._client is None: raise RuntimeError("OpenAI is not configured")
        response = self._client.responses.create(model=self._model, instructions="Return only the coaching note.", input=coach_prompt(plan), max_output_tokens=self._max_tokens, reasoning={"effort": "none"})
        return response.output_text.strip()


class FallbackCoachGenerator:
    namespace = "fallback"
    def generate(self, plan: CoachPlan) -> str:
        raise RuntimeError("Cloud coach generation is disabled")


class CoachService:
    def __init__(self, session_factory: sessionmaker[Session], generator: CoachGenerator, limiter: InMemoryRateLimiter | None = None) -> None:
        self._session_factory = session_factory; self._generator = generator; self._limiter = limiter
        self._cache: dict[tuple[int, int, str], CoachResponse] = {}; self._lock = RLock()

    def create(self, user_id: int) -> CoachResponse:
        with self._session_factory() as database:
            attempts = database.scalars(select(QuizAttempt).where(QuizAttempt.user_id == user_id).order_by(QuizAttempt.completed_at)).all()
        plan = self._plan(attempts)
        key = (user_id, len(attempts), self._generator.namespace)
        with self._lock:
            if key in self._cache: return self._cache[key]
        fallback = self._fallback(plan); text = fallback; fallback_used = True; validation = False
        started = perf_counter()
        if attempts and (self._limiter is None or self._limiter.allow()):
            try:
                candidate = self._generator.generate(plan)
                validation = self._valid(candidate)
                if validation: text = candidate; fallback_used = False
            except Exception:
                pass
        result = CoachResponse(summary=text, strength=plan.strength, improvement=plan.improvement,
            recommended_genre=plan.recommended_genre, recommended_difficulty=plan.recommended_difficulty,
            games_analyzed=plan.games, fallback_used=fallback_used)
        with self._lock: self._cache[key] = result
        logger.info("coach_generated latency_ms=%d fallback_used=%s validation_passed=%s games=%d", round((perf_counter()-started)*1000), fallback_used, validation, plan.games)
        return result

    @staticmethod
    def _plan(attempts: list[QuizAttempt]) -> CoachPlan:
        if not attempts:
            return CoachPlan(0, 0, "No completed games yet", 0, "Complete your first quiz", 0, "all", "easy")
        groups: dict[tuple[str, str], list[int]] = defaultdict(list)
        for attempt in attempts: groups[(attempt.genre, attempt.difficulty)].append(attempt.percentage)
        ranked = [(round(sum(values)/len(values)), len(values), genre, difficulty) for (genre, difficulty), values in groups.items()]
        best = max(ranked, key=lambda row: (row[0], row[1])); weakest = min(ranked, key=lambda row: (row[0], -row[1]))
        levels = ["easy", "medium", "hard"]; index = levels.index(best[3])
        recommended_difficulty = levels[min(index + 1, 2)] if best[0] >= 80 else levels[max(index - 1, 0)] if best[0] < 50 else best[3]
        average = round(sum(item.percentage for item in attempts)/len(attempts))
        return CoachPlan(len(attempts), average, f"{best[2]} · {best[3]}", best[0], f"{weakest[2]} · {weakest[3]}", weakest[0], best[2], recommended_difficulty)

    @staticmethod
    def _fallback(plan: CoachPlan) -> str:
        if plan.games == 0: return "Complete your first signed-in quiz to unlock personalized coaching."
        return f"Your strongest area is {plan.strength}. Keep building momentum by trying {plan.recommended_genre} on {plan.recommended_difficulty} next."

    @staticmethod
    def _valid(text: str) -> bool:
        stripped = text.strip()
        return 20 <= len(stripped) <= 500 and len(re.findall(r"[.!?](?:\s|$)", stripped)) <= 3 and not re.search(r"https?://|\b(?:email|password)\b", stripped, re.I)


def build_coach_service(settings: Settings) -> CoachService:
    generators: dict[str, CoachGenerator] = {"groq": GroqCoachGenerator(settings), "openai": OpenAICoachGenerator(settings), "fallback": FallbackCoachGenerator()}
    return CoachService(SessionLocal, generators[settings.ai_provider], CombinedRateLimiter(InMemoryRateLimiter(settings.coach_rate_limit_requests, settings.coach_rate_limit_window_seconds), global_ai_limiter(settings)))


coach_service = build_coach_service(get_settings())
