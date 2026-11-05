import json
import logging
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from threading import RLock
from time import perf_counter
from typing import Any, Protocol

from groq import Groq
from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, sessionmaker

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models.account import QuizAttempt, QuizAttemptAnswer
from app.models.catalog import Film
from app.schemas.account import FilmRecommendation, RecommendationsResponse
from app.services.hints import CombinedRateLimiter, InMemoryRateLimiter, global_ai_limiter

logger = logging.getLogger(__name__)


class WikipediaSynopsisSource:
    """Fetches a public introductory extract; never requests plot sections."""
    endpoint = "https://en.wikipedia.org/w/api.php"

    def fetch(self, title: str, year: int | None) -> tuple[str, str] | None:
        query = f'"{title}" {year or ""} film'.strip()
        params = urlencode({"action": "query", "generator": "search", "gsrsearch": query,
            "gsrnamespace": 0, "gsrlimit": 1, "prop": "extracts|info", "exintro": 1,
            "explaintext": 1, "exsentences": 4, "inprop": "url", "format": "json", "formatversion": 2})
        request = Request(f"{self.endpoint}?{params}", headers={"User-Agent": "CineQuoteAI/2.0 (portfolio app)"})
        try:
            with urlopen(request, timeout=4) as response:
                pages = json.load(response).get("query", {}).get("pages", [])
            if not pages: return None
            page = pages[0]; extract = str(page.get("extract", "")).strip(); url = str(page.get("fullurl", "")).strip()
            return (extract[:2500], url) if len(extract) >= 40 and url.startswith("https://") else None
        except Exception:
            return None


class RecommendationGenerator(Protocol):
    namespace: str
    def generate(self, genres: list[str], candidates: list[dict[str, Any]]) -> str: ...


def recommendation_prompt(genres: list[str], candidates: list[dict[str, Any]]) -> str:
    return (
        "Using only each supplied web-source excerpt, write a spoiler-free synopsis for EVERY film. Describe only "
        "the initial premise and setting. Never mention later developments, discoveries, identities, deaths, survivors, "
        "endings, twists, or resolutions. Never add facts absent from the source. Keep each synopsis between 20 and 45 "
        "words. Preserve every exact title and return no extra films. "
        "Return JSON only: {\"intro\":\"one short sentence\",\"films\":[{\"title\":\"exact title\",\"summary\":\"...\"}]}.\n"
        f"Genres played: {json.dumps(genres)}\nFilms missed in the latest game: {json.dumps(candidates, ensure_ascii=False)}"
    )


class GroqRecommendationGenerator:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._model = settings.groq_model; self.namespace = f"groq:{self._model}"
        self._client = client or (Groq(api_key=settings.groq_api_key.get_secret_value(), timeout=settings.groq_timeout_seconds, max_retries=0) if settings.groq_api_key else None)
    def generate(self, genres: list[str], candidates: list[dict[str, Any]]) -> str:
        if self._client is None: raise RuntimeError("Groq is not configured")
        request: dict[str, Any] = {"model": self._model, "messages": [{"role": "user", "content": recommendation_prompt(genres, candidates)}], "max_completion_tokens": 700, "temperature": .1, "response_format": {"type": "json_object"}}
        if self._model.startswith("openai/gpt-oss-"): request.update(reasoning_effort="low", include_reasoning=False)
        value = self._client.chat.completions.create(**request).choices[0].message.content
        return value.strip() if isinstance(value, str) else ""


class OpenAIRecommendationGenerator:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._model = settings.openai_model; self.namespace = f"openai:{self._model}"
        self._client = client or (OpenAI(api_key=settings.openai_api_key.get_secret_value(), timeout=settings.openai_timeout_seconds, max_retries=0) if settings.openai_api_key else None)
    def generate(self, genres: list[str], candidates: list[dict[str, Any]]) -> str:
        if self._client is None: raise RuntimeError("OpenAI is not configured")
        response = self._client.responses.create(model=self._model, instructions="Return valid JSON only.", input=recommendation_prompt(genres, candidates), max_output_tokens=700, reasoning={"effort": "none"})
        return response.output_text.strip()


class FallbackRecommendationGenerator:
    namespace = "fallback"
    def generate(self, genres: list[str], candidates: list[dict[str, Any]]) -> str:
        raise RuntimeError("Cloud recommendations are disabled")


class RecommendationService:
    def __init__(self, session_factory: sessionmaker[Session], generator: RecommendationGenerator,
                 limiter: InMemoryRateLimiter | None = None, source: WikipediaSynopsisSource | None = None) -> None:
        self._session_factory = session_factory; self._generator = generator; self._limiter = limiter
        self._source = source
        self._cache: dict[tuple[int, int, str], RecommendationsResponse] = {}; self._lock = RLock()

    def create(self, user_id: int) -> RecommendationsResponse:
        with self._session_factory() as database:
            attempts = database.scalars(select(QuizAttempt).where(QuizAttempt.user_id == user_id).order_by(QuizAttempt.completed_at.desc(), QuizAttempt.id.desc())).all()
            latest = attempts[0] if attempts else None
            missed_titles = list(dict.fromkeys(database.scalars(select(QuizAttemptAnswer.film_title).where(QuizAttemptAnswer.attempt_id == latest.id, QuizAttemptAnswer.correct.is_(False)).order_by(QuizAttemptAnswer.id)).all())) if latest else []
            films = database.scalars(select(Film).options(joinedload(Film.genres)).where(Film.title.in_(missed_titles))).unique().all() if missed_titles else []
        film_by_title = {film.title: film for film in films}
        candidates = [{"title": title, "genres": sorted(genre.name for genre in film_by_title[title].genres),
            "release_year": film_by_title[title].release_year} for title in missed_titles if title in film_by_title]
        genres = sorted({genre.lower() for item in candidates for genre in item["genres"]})
        key = (user_id, latest.id if latest else 0, self._generator.namespace)
        with self._lock:
            if key in self._cache: return self._cache[key]
        intro = "Every film below was a correct answer missed in your latest game." if candidates else "You did not miss any catalog films in your latest recorded game."
        summaries = {item["title"]: self._spoiler_free_note(item["genres"]) for item in candidates}
        sources: dict[str, str | None] = {item["title"]: None for item in candidates}
        sourced: list[dict[str, Any]] = []
        if self._source:
            for item in candidates:
                found = self._source.fetch(item["title"], item["release_year"])
                if found:
                    excerpt, url = found; sources[item["title"]] = url
                    sourced.append({**item, "source_excerpt": excerpt, "source_url": url})
        fallback_used = True; started = perf_counter()
        if sourced and len(sourced) == len(candidates) and (self._limiter is None or self._limiter.allow()):
            try:
                payload = json.loads(self._generator.generate(genres, sourced))
                generated = payload.get("films") if isinstance(payload, dict) else None
                ai_intro = payload.get("intro") if isinstance(payload, dict) else None
                expected = {item["title"] for item in candidates}
                received = {item.get("title") for item in generated} if isinstance(generated, list) and all(isinstance(item, dict) for item in generated) else set()
                valid = received == expected and len(generated or []) == len(expected) and all(self._safe_summary(item.get("summary")) for item in (generated or []))
                if valid and isinstance(ai_intro, str) and 10 <= len(ai_intro.strip()) <= 240:
                    summaries = {item["title"]: item["summary"].strip() for item in generated}; intro = ai_intro.strip(); fallback_used = False
            except Exception:
                pass
        result = RecommendationsResponse(intro=intro, based_on_genres=genres,
            recommendations=[FilmRecommendation(title=item["title"], genres=item["genres"], reason="Correct answer missed in your latest game.", summary=summaries[item["title"]], source_url=sources[item["title"]]) for item in candidates],
            games_analyzed=1 if latest else 0, recognized_films_excluded=0, fallback_used=fallback_used)
        with self._lock: self._cache[key] = result
        logger.info("recommendations_generated latency_ms=%d spoiler_safe=true missed_films=%d", round((perf_counter()-started)*1000), len(candidates))
        return result

    @staticmethod
    def _spoiler_free_note(genres: list[str]) -> str:
        category = " and ".join(genres) if genres else "catalog"
        return f"A {category} film from your latest quiz. Characters, events and story details are intentionally hidden for a spoiler-free discovery."

    @staticmethod
    def _safe_summary(value: object) -> bool:
        if not isinstance(value, str) or not 40 <= len(value.strip()) <= 450: return False
        risky = r"\b(?:eventually|ultimately|in the end|ending|finale|turns out|is revealed|discovers that|killer is|murderer is|dies|is killed|survives|twist|resolution|finally|à la fin|finalement|se révèle|découvre que|meurt|est tué|survit|retournement|dénouement)\b"
        return re.search(risky, value, re.I) is None


def build_recommendation_service(settings: Settings) -> RecommendationService:
    generators: dict[str, RecommendationGenerator] = {"groq": GroqRecommendationGenerator(settings), "openai": OpenAIRecommendationGenerator(settings), "fallback": FallbackRecommendationGenerator()}
    return RecommendationService(SessionLocal, generators[settings.ai_provider], CombinedRateLimiter(InMemoryRateLimiter(settings.recommendation_rate_limit_requests, settings.recommendation_rate_limit_window_seconds), global_ai_limiter(settings)), WikipediaSynopsisSource())


recommendation_service = build_recommendation_service(get_settings())
