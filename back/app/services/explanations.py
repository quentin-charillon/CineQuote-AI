import logging
import re
from dataclasses import dataclass
from threading import RLock
from time import perf_counter
from typing import Any, Protocol

from groq import Groq
from openai import OpenAI

from app.config import Settings, get_settings
from app.schemas.quiz import QuizQuestion
from app.services.hints import CombinedRateLimiter, InMemoryRateLimiter, global_ai_limiter

logger = logging.getLogger(__name__)


class ExplanationGenerator(Protocol):
    namespace: str
    def generate(self, question: QuizQuestion) -> str: ...


def explanation_prompt(question: QuizQuestion) -> str:
    return (
        "Explain in English why this quote is associated with the named film. Use at most three short sentences. "
        "Discuss only wording, tone, character voice, or a broadly safe thematic connection. Do not invent scene details, "
        "characters, speakers, plot events, trivia, or production facts. Do not mention any other film or quiz option. "
        "If the context cannot be safely inferred, simply say the wording is a memorable line catalogued from this film.\n\n"
        f"Quote: {question.quote}\nFilm: {question.film_title}"
    )


class GroqExplanationGenerator:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._model=settings.groq_model; self.namespace=f"groq:{self._model}"; self._max=settings.groq_max_completion_tokens
        self._client=client or (Groq(api_key=settings.groq_api_key.get_secret_value(),timeout=settings.groq_timeout_seconds,max_retries=0) if settings.groq_api_key else None)
    def generate(self, question: QuizQuestion) -> str:
        if self._client is None: raise RuntimeError("Groq is not configured")
        request: dict[str, Any]={"model":self._model,"messages":[{"role":"user","content":explanation_prompt(question)}],"max_completion_tokens":self._max,"temperature":.2}
        if self._model.startswith("openai/gpt-oss-"): request.update(reasoning_effort="low",include_reasoning=False)
        content=self._client.chat.completions.create(**request).choices[0].message.content
        return content.strip() if isinstance(content,str) else ""


class OpenAIExplanationGenerator:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._model=settings.openai_model; self.namespace=f"openai:{self._model}"; self._max=settings.openai_max_output_tokens
        self._client=client or (OpenAI(api_key=settings.openai_api_key.get_secret_value(),timeout=settings.openai_timeout_seconds,max_retries=0) if settings.openai_api_key else None)
    def generate(self, question: QuizQuestion) -> str:
        if self._client is None: raise RuntimeError("OpenAI is not configured")
        response=self._client.responses.create(model=self._model,instructions="Return only the explanation.",input=explanation_prompt(question),max_output_tokens=self._max,reasoning={"effort":"none"})
        return response.output_text.strip()


class FallbackExplanationGenerator:
    namespace="fallback"
    def generate(self, question: QuizQuestion) -> str: raise RuntimeError("Cloud explanation is disabled")


@dataclass(frozen=True)
class GeneratedExplanation:
    text: str
    fallback_used: bool


class ExplanationService:
    def __init__(self, generator: ExplanationGenerator, limiter: InMemoryRateLimiter | None = None) -> None:
        self._generator=generator; self._limiter=limiter; self._cache: dict[tuple[str,str],GeneratedExplanation]={}; self._lock=RLock()
    def create(self, question: QuizQuestion) -> GeneratedExplanation:
        key=(question.id,self._generator.namespace)
        with self._lock:
            if key in self._cache: return self._cache[key]
        started=perf_counter(); text=self._fallback(question); fallback=True; validation=False
        if self._limiter is None or self._limiter.allow():
            try:
                candidate=self._generator.generate(question); validation=self._valid(candidate,question)
                if validation: text=candidate; fallback=False
            except Exception: pass
        result=GeneratedExplanation(text,fallback)
        with self._lock: self._cache[key]=result
        logger.info("explanation_generated latency_ms=%d fallback_used=%s validation_passed=%s",round((perf_counter()-started)*1000),fallback,validation)
        return result
    @staticmethod
    def _fallback(question: QuizQuestion) -> str:
        return f'This line is catalogued as dialogue from "{question.film_title}". Focus on its wording and tone when connecting it to the film.'
    @staticmethod
    def _valid(text: str, question: QuizQuestion) -> bool:
        stripped=text.strip()
        if not 20 <= len(stripped) <= 500 or len(re.findall(r"[.!?](?:\s|$)",stripped)) > 3 or re.search(r"https?://",stripped,re.I): return False
        normalized=lambda value:" ".join(re.sub(r"[^a-z0-9]+"," ",value.casefold()).split())
        body=f" {normalized(stripped)} "
        return not any(f" {normalized(choice)} " in body for choice in question.choices if choice != question.film_title and normalized(choice))


def build_explanation_service(settings: Settings) -> ExplanationService:
    generators: dict[str,ExplanationGenerator]={"groq":GroqExplanationGenerator(settings),"openai":OpenAIExplanationGenerator(settings),"fallback":FallbackExplanationGenerator()}
    return ExplanationService(generators[settings.ai_provider],CombinedRateLimiter(InMemoryRateLimiter(settings.explanation_rate_limit_requests,settings.explanation_rate_limit_window_seconds),global_ai_limiter(settings)))


explanation_service=build_explanation_service(get_settings())
