from typing import Literal

from pydantic import BaseModel, Field, model_validator


Difficulty = Literal["easy", "medium", "hard"]
Genre = Literal["all", "horror", "comedy", "science_fiction", "thriller", "action", "animation", "romance", "fantasy", "adventure"]


class QuizQuestion(BaseModel):
    id: str
    quote: str
    film_title: str
    choices: list[str]
    release_year: int | None = Field(default=None, ge=1888, le=2100)
    difficulty: Difficulty = "medium"

    @model_validator(mode="after")
    def validate_choices(self) -> "QuizQuestion":
        if not self.choices:
            return self
        if len(self.choices) != 4 or len(set(self.choices)) != 4:
            raise ValueError("Each question must have exactly four unique choices")
        if self.film_title not in self.choices:
            raise ValueError("The correct movie must be included in the choices")
        return self


class FilmChoiceCandidate(BaseModel):
    title: str
    release_year: int | None


class SessionCreated(BaseModel):
    session_id: str
    total_questions: int


class SessionCreateRequest(BaseModel):
    difficulty: Difficulty
    genre: Genre = "all"


class CustomSessionRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=500)


class CustomSessionCreated(SessionCreated):
    difficulty: Difficulty
    genres: list[Genre]
    interpretation: str
    fallback_used: bool


class DifficultyAvailability(BaseModel):
    difficulty: Difficulty
    verified_questions: int
    required_questions: int
    available: bool


class QuizAvailability(BaseModel):
    genre: Genre
    difficulty: Difficulty
    verified_questions: int
    required_questions: int
    eligible_films: int
    required_films: int
    available: bool


class PublicQuestion(BaseModel):
    id: str
    quote: str
    choices: list[str]
    question_number: int
    total_questions: int
    score: int
    hint_used: bool


class HintRequest(BaseModel):
    question_id: str = Field(min_length=1)


class HintResponse(BaseModel):
    question_id: str
    hint: str
    fallback_used: bool


class ExplanationRequest(BaseModel):
    question_id: str = Field(min_length=1)


class ExplanationResponse(BaseModel):
    question_id: str
    explanation: str
    fallback_used: bool


class AnswerSubmission(BaseModel):
    question_id: str = Field(min_length=1)
    answer: str = Field(min_length=1)


class AnswerResult(BaseModel):
    question_id: str
    is_correct: bool
    correct_answer: str
    movie_year: int | None
    score: int
    completed: bool


class QuizResults(BaseModel):
    score: int
    total_questions: int
    percentage: int

