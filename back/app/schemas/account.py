from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    password: str = Field(min_length=10, max_length=128)

    @field_validator("password")
    @classmethod
    def password_has_variety(cls, value: str) -> str:
        if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one letter and one number")
        return value

    @field_validator("email")
    @classmethod
    def valid_email_shape(cls, value: str) -> str:
        value = value.strip()
        if value.count("@") != 1 or "." not in value.rsplit("@", 1)[1]:
            raise ValueError("Enter a valid email address")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    username: str
    created_at: datetime


class StatsBreakdown(BaseModel):
    label: str
    games_played: int
    average_percentage: int
    best_percentage: int


class AttemptResponse(BaseModel):
    genre: str
    difficulty: str
    score: int
    total_questions: int
    percentage: int
    hints_used: int
    completed_at: datetime


class UserStatsResponse(BaseModel):
    games_played: int
    average_percentage: int
    best_percentage: int
    total_correct: int
    total_questions: int
    accuracy_percentage: int
    hints_used: int
    by_genre: list[StatsBreakdown]
    by_difficulty: list[StatsBreakdown]
    recent_attempts: list[AttemptResponse]


class CoachResponse(BaseModel):
    summary: str
    strength: str
    improvement: str
    recommended_genre: str
    recommended_difficulty: str
    games_analyzed: int
    fallback_used: bool


class FilmRecommendation(BaseModel):
    title: str
    genres: list[str]
    reason: str
    summary: str
    source_url: str | None = None


class RecommendationsResponse(BaseModel):
    intro: str
    based_on_genres: list[str]
    recommendations: list[FilmRecommendation]
    games_analyzed: int
    recognized_films_excluded: int
    fallback_used: bool
