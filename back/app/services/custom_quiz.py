import json
import re
from dataclasses import dataclass
from threading import RLock
from typing import Any, Protocol

from groq import Groq
from openai import OpenAI

from app.config import Settings, get_settings
from app.schemas.quiz import Difficulty, Genre
from app.services.hints import CombinedRateLimiter, InMemoryRateLimiter, global_ai_limiter

ALLOWED_GENRES: tuple[Genre, ...] = ("all","horror","comedy","science_fiction","thriller","action","animation","romance","fantasy","adventure")


@dataclass(frozen=True)
class CustomQuizPlan:
    difficulty: Difficulty
    genres: tuple[Genre, ...]
    fallback_used: bool


class PlanGenerator(Protocol):
    namespace: str
    def generate(self, prompt: str) -> str: ...


def planner_prompt(prompt: str) -> str:
    return (
        "Convert the user's movie-quiz request into JSON only, with exactly these keys: "
        '"difficulty" and "genres". Difficulty must be easy, medium, or hard. Genres must be an array of one to three values from: '
        + ", ".join(ALLOWED_GENRES) + ". Use all only when no specific genre is requested. Do not create questions or film titles.\n\nRequest: " + prompt
    )


class GroqPlanGenerator:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._model=settings.groq_model; self.namespace=f"groq:{self._model}"; self._max=settings.groq_max_completion_tokens
        self._client=client or (Groq(api_key=settings.groq_api_key.get_secret_value(),timeout=settings.groq_timeout_seconds,max_retries=0) if settings.groq_api_key else None)
    def generate(self,prompt:str)->str:
        if self._client is None: raise RuntimeError("Groq is not configured")
        request:dict[str,Any]={"model":self._model,"messages":[{"role":"user","content":planner_prompt(prompt)}],"max_completion_tokens":self._max,"temperature":0}
        if self._model.startswith("openai/gpt-oss-"): request.update(reasoning_effort="low",include_reasoning=False)
        content=self._client.chat.completions.create(**request).choices[0].message.content
        return content.strip() if isinstance(content,str) else ""


class OpenAIPlanGenerator:
    def __init__(self,settings:Settings,client:Any|None=None)->None:
        self._model=settings.openai_model; self.namespace=f"openai:{self._model}"; self._max=settings.openai_max_output_tokens
        self._client=client or (OpenAI(api_key=settings.openai_api_key.get_secret_value(),timeout=settings.openai_timeout_seconds,max_retries=0) if settings.openai_api_key else None)
    def generate(self,prompt:str)->str:
        if self._client is None: raise RuntimeError("OpenAI is not configured")
        response=self._client.responses.create(model=self._model,instructions="Return JSON only.",input=planner_prompt(prompt),max_output_tokens=self._max,reasoning={"effort":"none"})
        return response.output_text.strip()


class FallbackPlanGenerator:
    namespace="fallback"
    def generate(self,prompt:str)->str: raise RuntimeError("Cloud planning is disabled")


class CustomQuizPlanner:
    GENRE_ALIASES={
        "horror":("horror","horreur"),"comedy":("comedy","comedie","comédie"),"science_fiction":("science fiction","science-fiction","sci fi","sci-fi","sf"),
        "thriller":("thriller",),"action":("action",),"animation":("animation","animated"),"romance":("romance","romantique","musical"),
        "fantasy":("fantasy","fantastique"),"adventure":("adventure","aventure"),
    }
    def __init__(self,generator:PlanGenerator,limiter:InMemoryRateLimiter|None=None)->None:
        self._generator=generator; self._limiter=limiter; self._cache:dict[tuple[str,str],CustomQuizPlan]={}; self._lock=RLock()
    def plan(self,prompt:str)->CustomQuizPlan:
        normalized=" ".join(prompt.casefold().split()); key=(normalized,self._generator.namespace)
        with self._lock:
            if key in self._cache:return self._cache[key]
        plan=None
        if self._limiter is None or self._limiter.allow():
            try: plan=self._validate(self._generator.generate(prompt))
            except Exception: pass
        result=plan or self._fallback(prompt)
        with self._lock:self._cache[key]=result
        return result
    @staticmethod
    def _validate(raw:str)->CustomQuizPlan|None:
        try:
            data=json.loads(raw); difficulty=data["difficulty"]; genres=data["genres"]
            if difficulty not in ("easy","medium","hard") or not isinstance(genres,list) or not 1<=len(genres)<=3:return None
            clean=tuple(dict.fromkeys(genres))
            if any(genre not in ALLOWED_GENRES for genre in clean) or ("all" in clean and len(clean)>1):return None
            return CustomQuizPlan(difficulty,clean,False)
        except (ValueError,TypeError,KeyError,json.JSONDecodeError):return None
    def _fallback(self,prompt:str)->CustomQuizPlan:
        text=prompt.casefold(); difficulty:Difficulty="medium"
        if re.search(r"\b(?:hard|difficile|difficult)\b",text):difficulty="hard"
        elif re.search(r"\b(?:easy|facile)\b",text):difficulty="easy"
        genres:list[Genre]=[]
        for genre,aliases in self.GENRE_ALIASES.items():
            if any(alias in text for alias in aliases):genres.append(genre)  # type: ignore[arg-type]
        return CustomQuizPlan(difficulty,tuple(genres[:3] or ["all"]),True)


def build_custom_quiz_planner(settings:Settings)->CustomQuizPlanner:
    generators:dict[str,PlanGenerator]={"groq":GroqPlanGenerator(settings),"openai":OpenAIPlanGenerator(settings),"fallback":FallbackPlanGenerator()}
    return CustomQuizPlanner(generators[settings.ai_provider],CombinedRateLimiter(InMemoryRateLimiter(settings.custom_quiz_rate_limit_requests,settings.custom_quiz_rate_limit_window_seconds),global_ai_limiter(settings)))


custom_quiz_planner=build_custom_quiz_planner(get_settings())
