import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, sessionmaker

from app.models.catalog import Film, Genre as GenreModel, Quote
from app.schemas.quiz import Difficulty, FilmChoiceCandidate, Genre, QuizQuestion


def normalize_catalog_text(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


class SqlAlchemyQuestionRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_verified(self, difficulty: Difficulty, genre: Genre = "all") -> list[QuizQuestion]:
        with self._session_factory() as database:
            statement = (
                select(Quote)
                .options(joinedload(Quote.film))
                .where(Quote.difficulty == difficulty)
                .order_by(Quote.id)
            )
            if genre != "all":
                statement = statement.join(Quote.film).join(Film.genres).where(
                    func.lower(GenreModel.name) == genre.replace("_", " ")
                )
            quotes = database.scalars(statement).unique().all()
            return [self._to_question(quote) for quote in quotes]

    def list_verified_films(self, genre: Genre = "all") -> list[FilmChoiceCandidate]:
        with self._session_factory() as database:
            statement = select(Film).join(Film.quotes)
            if genre != "all":
                statement = statement.join(Film.genres).where(func.lower(GenreModel.name) == genre.replace("_", " "))
            films = database.scalars(statement.order_by(Film.id)).unique().all()
        # Choices are titles, so collapse remakes with the same display title.
        unique = {film.title: FilmChoiceCandidate(title=film.title, release_year=film.release_year) for film in films}
        return list(unique.values())

    def count_verified_by_difficulty(self) -> dict[str, int]:
        with self._session_factory() as database:
            rows = database.execute(
                select(Quote.difficulty, func.count(Quote.id))
                .group_by(Quote.difficulty)
            ).all()
        return {difficulty: count for difficulty, count in rows}

    def count_verified_by_genre_and_difficulty(self) -> dict[tuple[str, str], int]:
        counts: dict[tuple[str, str], int] = {}
        with self._session_factory() as database:
            all_rows = database.execute(
                select(Quote.difficulty, func.count(Quote.id))
                .group_by(Quote.difficulty)
            ).all()
            genre_rows = database.execute(
                select(GenreModel.name, Quote.difficulty, func.count(Quote.id.distinct()))
                .select_from(Quote).join(Quote.film).join(Film.genres)
                .group_by(GenreModel.name, Quote.difficulty)
            ).all()
        counts.update({("all", difficulty): count for difficulty, count in all_rows})
        counts.update({(name.casefold().replace(" ", "_"), difficulty): count for name, difficulty, count in genre_rows})
        return counts

    def count_verified_films_by_genre(self) -> dict[str, int]:
        with self._session_factory() as database:
            total = database.scalar(select(func.count(func.distinct(Film.id))).join(Film.quotes)) or 0
            rows = database.execute(
                select(GenreModel.name, func.count(func.distinct(Film.id)))
                .select_from(Film).join(Film.quotes).join(Film.genres)
                .group_by(GenreModel.name)
            ).all()
        return {"all": total, **{name.casefold().replace(" ", "_"): count for name, count in rows}}

    @staticmethod
    def _to_question(quote: Quote) -> QuizQuestion:
        return QuizQuestion(
            id=str(quote.id),
            quote=quote.text,
            film_title=quote.film.title,
            release_year=quote.film.release_year,
            difficulty=quote.difficulty,
            choices=[],
        )
