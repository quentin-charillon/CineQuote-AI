import json
from pathlib import Path


def test_comedy_easy_changes_are_narrow_reviewed_and_distinct() -> None:
    path = Path(__file__).parents[1] / "comedy-easy-changes-approved.json"
    changes = json.loads(path.read_text(encoding="utf-8"))

    assert len(changes) == 7
    assert len({item["quote_id"] for item in changes}) == 7
    assert len({item["quote"].casefold() for item in changes}) == 7
    assert all(item["proposed_difficulty"] == "easy" for item in changes)
    assert all(item["old_difficulty"] in {"medium", "hard"} for item in changes)
    assert {item["film"] for item in changes} == {
        "Toy Story", "Finding Nemo", "Monsters, Inc.", "Aladdin", "Frozen", "Ratatouille"
    }
