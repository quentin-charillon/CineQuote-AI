from dataclasses import dataclass

from app.schemas.quiz import Difficulty


@dataclass(frozen=True)
class ClassificationConfig:
    easy_recognizability_min: int = 4
    easy_knowledge_max: int = 2
    hard_recognizability_max: int = 2
    hard_knowledge_min: int = 4


def classify_difficulty(
    recognizability_score: int,
    knowledge_score: int,
    config: ClassificationConfig = ClassificationConfig(),
) -> Difficulty:
    """Initial human-scored suggestion; never an objective or final judgment."""
    if not 1 <= recognizability_score <= 5 or not 1 <= knowledge_score <= 5:
        raise ValueError("Classification scores must be between 1 and 5")
    if (
        recognizability_score >= config.easy_recognizability_min
        and knowledge_score <= config.easy_knowledge_max
    ):
        return "easy"
    if (
        recognizability_score <= config.hard_recognizability_max
        and knowledge_score >= config.hard_knowledge_min
    ):
        return "hard"
    return "medium"


INITIAL_DIFFICULTIES: dict[str, Difficulty] = {
    "star-wars-force": "easy",
    "terminator-back": "easy",
    "et-home": "easy",
    "wizard-home": "easy",
    "godfather-offer": "easy",
    "taxi-driver-talking": "easy",
    "sixth-sense-dead": "easy",
    "jerry-maguire-money": "easy",
    "casablanca-looking": "easy",
    "apollo-houston": "easy",
    "dirty-dancing-baby": "medium",
    "few-good-men-truth": "medium",
    "top-gun-speed": "medium",
    "airplane-serious": "hard",
}
