import json
from pathlib import Path


def _review() -> list[dict[str, object]]:
    path = Path(__file__).parents[1] / "familiarity-difficulty-review.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_easy_requires_both_mainstream_film_and_iconic_quote() -> None:
    proposed_easy = [item for item in _review() if item["proposed_difficulty"] == "easy"]

    assert proposed_easy
    assert all(item["film_familiarity"] == "mainstream" for item in proposed_easy)
    assert all(item["quote_recognizability"] == "iconic" for item in proposed_easy)


def test_niche_film_cannot_remain_easy_even_with_iconic_quote() -> None:
    casablanca = [item for item in _review() if item["film"] == "Casablanca" and item["old_difficulty"] == "easy"]

    assert casablanca
    assert all(item["film_familiarity"] != "mainstream" for item in casablanca)
    assert all(item["proposed_difficulty"] != "easy" for item in casablanca)


def test_mainstream_film_can_have_quotes_across_multiple_difficulties() -> None:
    lion_king = [item for item in _review() if item["film"] == "The Lion King"]

    assert {item["proposed_difficulty"] for item in lion_king} == {"easy", "medium", "hard"}


def test_familiarity_review_covers_every_film_and_quote() -> None:
    review = _review()

    assert len(review) == 145
    assert len({item["film_id"] for item in review}) == 100
    assert {item["film_familiarity"] for item in review} == {"mainstream", "recognizable", "niche"}
