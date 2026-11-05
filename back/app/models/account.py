from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320))
    normalized_email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(50))
    normalized_username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
    auth_sessions: Mapped[list[AuthSession]] = relationship(back_populates="user", cascade="all, delete-orphan")
    attempts: Mapped[list[QuizAttempt]] = relationship(back_populates="user", cascade="all, delete-orphan")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    user: Mapped[User] = relationship(back_populates="auth_sessions")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (UniqueConstraint("quiz_session_id", name="uq_quiz_attempt_session"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    quiz_session_id: Mapped[str] = mapped_column(String(64))
    genre: Mapped[str] = mapped_column(String(40), index=True)
    difficulty: Mapped[str] = mapped_column(String(10), index=True)
    score: Mapped[int]
    total_questions: Mapped[int]
    percentage: Mapped[int]
    hints_used: Mapped[int]
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), index=True)
    user: Mapped[User] = relationship(back_populates="attempts")
    answers: Mapped[list[QuizAttemptAnswer]] = relationship(back_populates="attempt", cascade="all, delete-orphan")


class QuizAttemptAnswer(Base):
    __tablename__ = "quiz_attempt_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("quiz_attempts.id", ondelete="CASCADE"), index=True)
    film_title: Mapped[str] = mapped_column(String(300), index=True)
    correct: Mapped[bool]
    attempt: Mapped[QuizAttempt] = relationship(back_populates="answers")
