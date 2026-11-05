import json
import re
from pathlib import Path

from pydantic import TypeAdapter

from app.catalog.classification import INITIAL_DIFFICULTIES
from app.schemas.quiz import Difficulty, FilmChoiceCandidate, Genre, QuizQuestion


class JsonQuestionRepository:
    """Load and validate the authoritative question dataset from JSON."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or Path(__file__).parents[1] / "data" / "questions.json"
        raw_questions = json.loads(self._path.read_text(encoding="utf-8"))
        for question in raw_questions:
            question.setdefault("difficulty", INITIAL_DIFFICULTIES.get(question.get("id"), "medium"))
        self._questions = TypeAdapter(list[QuizQuestion]).validate_python(raw_questions)
        self._validate_unique_questions()

    def list_all(self) -> list[QuizQuestion]:
        return [question.model_copy(deep=True) for question in self._questions]

    def list_verified(self, difficulty: Difficulty = "easy", genre: Genre = "all") -> list[QuizQuestion]:
        if genre != "all":
            return []
        return [
            question.model_copy(deep=True)
            for question in self._questions
            if question.difficulty == difficulty
        ]

    def count_verified_by_difficulty(self) -> dict[str, int]:
        counts = {"easy": 0, "medium": 0, "hard": 0}
        for question in self._questions:
            counts[question.difficulty] += 1
        return counts

    def count_verified_by_genre_and_difficulty(self) -> dict[tuple[str, str], int]:
        return {("all", difficulty): count for difficulty, count in self.count_verified_by_difficulty().items()}

    def list_verified_films(self, genre: Genre = "all") -> list[FilmChoiceCandidate]:
        if genre != "all":
            return []
        unique = {
            question.film_title: FilmChoiceCandidate(title=question.film_title, release_year=question.release_year)
            for question in self._questions
        }
        return list(unique.values())

    def count_verified_films_by_genre(self) -> dict[str, int]:
        return {"all": len(self.list_verified_films("all"))}

    def _validate_unique_questions(self) -> None:
        ids = [question.id for question in self._questions]
        if len(ids) != len(set(ids)):
            raise ValueError("Question IDs must be unique")

        normalized_quotes = [
            (
                re.sub(r"[^a-z0-9]+", " ", question.film_title.casefold()).strip(),
                re.sub(r"[^a-z0-9]+", " ", question.quote.casefold()).strip(),
            )
            for question in self._questions
        ]
        if len(normalized_quotes) != len(set(normalized_quotes)):
            raise ValueError("Question quotes must be unique within a film")

