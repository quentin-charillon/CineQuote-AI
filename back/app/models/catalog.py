from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

film_genres = Table(
    "film_genres",
    Base.metadata,
    Column("film_id", ForeignKey("films.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
)

class Film(Base):
    __tablename__ = "films"
    __table_args__ = (UniqueConstraint("normalized_title", "release_year", name="uq_film_identity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    normalized_title: Mapped[str] = mapped_column(String(300), index=True)
    release_year: Mapped[int | None] = mapped_column(nullable=True)
    country_of_origin: Mapped[str | None] = mapped_column(String(120), nullable=True)
    familiarity: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    familiarity_rationale: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    familiarity_review_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quotes: Mapped[list[Quote]] = relationship(back_populates="film", cascade="all, delete-orphan")
    genres: Mapped[list[Genre]] = relationship(secondary=film_genres, back_populates="films")


class Quote(Base):
    __tablename__ = "quotes"
    __table_args__ = (
        UniqueConstraint("film_id", "normalized_text", name="uq_quote_film_text"),
        CheckConstraint("difficulty IN ('easy', 'medium', 'hard')", name="ck_quote_difficulty"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(120), unique=True)
    text: Mapped[str] = mapped_column(String(1000))
    normalized_text: Mapped[str] = mapped_column(String(1000), index=True)
    difficulty: Mapped[str] = mapped_column(String(10), index=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    film_id: Mapped[int] = mapped_column(ForeignKey("films.id", ondelete="CASCADE"), index=True)
    film: Mapped[Film] = relationship(back_populates="quotes")
class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    films: Mapped[list[Film]] = relationship(secondary=film_genres, back_populates="genres")


class FilmGenreEvidence(Base):
    __tablename__ = "film_genre_evidence"
    __table_args__ = (UniqueConstraint("film_id", "genre_id", "source_url", name="uq_film_genre_evidence"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    film_id: Mapped[int] = mapped_column(ForeignKey("films.id", ondelete="CASCADE"), index=True)
    genre_id: Mapped[int] = mapped_column(ForeignKey("genres.id", ondelete="CASCADE"), index=True)
    source_url: Mapped[str] = mapped_column(String(1000))
    external_genre_id: Mapped[str] = mapped_column(String(80))
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
