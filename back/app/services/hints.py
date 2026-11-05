import logging
import re
from collections import deque
from dataclasses import dataclass
from threading import RLock
from time import monotonic, perf_counter
from typing import Any, Protocol

from groq import Groq
from openai import OpenAI

from app.config import Settings
from app.schemas.quiz import QuizQuestion

logger = logging.getLogger(__name__)

FALLBACK_HINT = (
    "Focus on the wording and tone of the quote, then eliminate the options "
    "that feel least consistent with it."
)
HINT_INSTRUCTIONS = (
    "Write one short, helpful movie-quiz hint. Do not reveal or repeat the movie "
    "title. Do not identify the correct option by letter, number, position, or "
    "wording. Do not mention that you know the answer. Use at most two concise "
    "sentences and avoid spoilers. Return only the hint."
)


class HintGenerator(Protocol):
    cache_namespace: str

    def generate(self, question: QuizQuestion) -> str:
        """Generate an untrusted candidate hint."""


class GroqHintGenerator:
    """Generate hints with the official Groq Python SDK."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._model = settings.groq_model
        self.cache_namespace = f"groq:{self._model}"
        self._max_completion_tokens = settings.groq_max_completion_tokens
        self._client = client
        if self._client is None and settings.groq_api_key is not None:
            self._client = Groq(
                api_key=settings.groq_api_key.get_secret_value(),
                timeout=settings.groq_timeout_seconds,
                max_retries=0,
            )

    def generate(self, question: QuizQuestion) -> str:
        if self._client is None:
            raise RuntimeError("Groq generation is not configured")

        request: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "user", "content": build_hint_prompt(question)}],
            "max_completion_tokens": self._max_completion_tokens,
            "temperature": 0.5,
        }
        if self._model.startswith("openai/gpt-oss-"):
            request.update(reasoning_effort="low", include_reasoning=False)

        completion = self._client.chat.completions.create(**request)
        content = completion.choices[0].message.content
        return content.strip() if isinstance(content, str) else ""


class OpenAIHintGenerator:
    """Generate hints through the official OpenAI Responses API."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._model = settings.openai_model
        self.cache_namespace = f"openai:{self._model}"
        self._max_output_tokens = settings.openai_max_output_tokens
        self._client = client
        if self._client is None and settings.openai_api_key is not None:
            self._client = OpenAI(
                api_key=settings.openai_api_key.get_secret_value(),
                timeout=settings.openai_timeout_seconds,
                max_retries=0,
            )

    def generate(self, question: QuizQuestion) -> str:
        if self._client is None:
            raise RuntimeError("OpenAI generation is not configured")

        response = self._client.responses.create(
            model=self._model,
            instructions=HINT_INSTRUCTIONS,
            input=build_hint_context(question),
            max_output_tokens=self._max_output_tokens,
            reasoning={"effort": "none"},
        )
        return response.output_text.strip()


class FallbackHintGenerator:
    cache_namespace = "fallback"

    def generate(self, question: QuizQuestion) -> str:
        raise RuntimeError("Cloud hint generation is disabled")


@dataclass(frozen=True)
class HintValidation:
    passed: bool
    title_leaked: bool
    answer_label_leaked: bool


@dataclass(frozen=True)
class GeneratedHint:
    text: str
    fallback_used: bool
    validation_passed: bool
    latency_ms: int


class InMemoryRateLimiter:
    """Process-local sliding-window limiter for outbound provider requests."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self._limit = limit
        self._window_seconds = window_seconds
        self._requests: deque[float] = deque()
        self._lock = RLock()

    def allow(self) -> bool:
        now = monotonic()
        with self._lock:
            cutoff = now - self._window_seconds
            while self._requests and self._requests[0] <= cutoff:
                self._requests.popleft()
            if len(self._requests) >= self._limit:
                return False
            self._requests.append(now)
            return True


class CombinedRateLimiter:
    """Require both the feature budget and the process-wide provider budget."""

    def __init__(self, *limiters: InMemoryRateLimiter) -> None:
        self._limiters = limiters

    def allow(self) -> bool:
        return all(limiter.allow() for limiter in self._limiters)


_global_ai_limiters: dict[tuple[int, int], InMemoryRateLimiter] = {}
_global_ai_limiters_lock = RLock()


def global_ai_limiter(settings: Settings) -> InMemoryRateLimiter:
    key = (settings.ai_global_rate_limit_requests, settings.ai_global_rate_limit_window_seconds)
    with _global_ai_limiters_lock:
        return _global_ai_limiters.setdefault(key, InMemoryRateLimiter(*key))


class InMemoryHintCache:
    """Process-local cache containing validated hints only."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._items: dict[tuple[str, str], str] = {}
        self._lock = RLock()

    def get(self, question_id: str, namespace: str) -> str | None:
        if not self._enabled:
            return None
        with self._lock:
            return self._items.get((question_id, namespace))

    def put(self, question_id: str, namespace: str, hint: str) -> None:
        if not self._enabled:
            return
        with self._lock:
            self._items[(question_id, namespace)] = hint


def build_hint_prompt(question: QuizQuestion) -> str:
    return f"{HINT_INSTRUCTIONS}\n\n{build_hint_context(question)}"


def build_hint_context(question: QuizQuestion) -> str:
    return (
        f"Quote: {question.quote}\n"
        f"Correct film (private context; never output): {question.film_title}\n"
        f"Answer options (never identify the correct one): {', '.join(question.choices)}"
    )


def validate_hint(text: str, correct_title: str) -> HintValidation:
    normalized_text = _normalize(text)
    normalized_title = _normalize(correct_title)
    title_leaked = bool(
        normalized_title and f" {normalized_title} " in f" {normalized_text} "
    )
    label_pattern = re.compile(
        r"(?:^|\b)(?:option|choice|answer)\s*(?:is\s*)?(?:[a-d]|[1-4])(?:\b|$)"
        r"|(?:^|\s)[a-d1-4][).:\-](?:\s|$)",
        re.IGNORECASE,
    )
    answer_label_leaked = bool(label_pattern.search(text.strip()))
    passed = bool(text.strip()) and not title_leaked and not answer_label_leaked
    return HintValidation(
        passed=passed,
        title_leaked=title_leaked,
        answer_label_leaked=answer_label_leaked,
    )


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


class HintService:
    def __init__(
        self,
        generator: HintGenerator,
        rate_limiter: InMemoryRateLimiter | None = None,
        cache: InMemoryHintCache | None = None,
    ) -> None:
        self._generator = generator
        self._rate_limiter = rate_limiter
        self._cache = cache or InMemoryHintCache(enabled=False)

    def create_hint(self, question: QuizQuestion) -> GeneratedHint:
        started_at = perf_counter()
        cached = self._cache.get(question.id, self._generator.cache_namespace)
        if cached is not None:
            return self._finish(cached, False, True, started_at, cache_hit=True)

        if self._rate_limiter is not None and not self._rate_limiter.allow():
            return self._finish(FALLBACK_HINT, True, False, started_at)

        validation_passed = False
        fallback_used = True
        hint = FALLBACK_HINT
        try:
            candidate = self._generator.generate(question)
            validation = validate_hint(candidate, question.film_title)
            validation_passed = validation.passed
            if validation.passed:
                hint = candidate
                fallback_used = False
                self._cache.put(question.id, self._generator.cache_namespace, hint)
        except Exception:
            # Provider failures (including 429s and timeouts) intentionally become
            # safe fallbacks. Exception details can contain context and are not logged.
            pass

        return self._finish(hint, fallback_used, validation_passed, started_at)

    @staticmethod
    def _finish(
        text: str,
        fallback_used: bool,
        validation_passed: bool,
        started_at: float,
        cache_hit: bool = False,
    ) -> GeneratedHint:
        latency_ms = round((perf_counter() - started_at) * 1000)
        logger.info(
            "hint_generated latency_ms=%d fallback_used=%s validation_passed=%s cache_hit=%s",
            latency_ms,
            fallback_used,
            validation_passed,
            cache_hit,
        )
        return GeneratedHint(
            text=text,
            fallback_used=fallback_used,
            validation_passed=validation_passed,
            latency_ms=latency_ms,
        )


def build_hint_service(settings: Settings) -> HintService:
    generators: dict[str, HintGenerator] = {
        "groq": GroqHintGenerator(settings),
        "openai": OpenAIHintGenerator(settings),
        "fallback": FallbackHintGenerator(),
    }
    return HintService(
        generator=generators[settings.ai_provider],
        rate_limiter=CombinedRateLimiter(
            InMemoryRateLimiter(settings.hint_rate_limit_requests, settings.hint_rate_limit_window_seconds),
            global_ai_limiter(settings),
        ),
        cache=InMemoryHintCache(settings.hint_cache_enabled),
    )
