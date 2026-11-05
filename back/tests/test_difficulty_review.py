import json
from pathlib import Path

from scripts.audit_difficulty import afi_policy


def test_afi_policy_keeps_easy_deliberately_narrow() -> None:
    assert afi_policy(1)[0] == "easy"
    assert afi_policy(20)[0] == "easy"
    assert afi_policy(21)[0] == "medium"
    assert afi_policy(60)[0] == "medium"
    assert afi_policy(61)[0] == "hard"
    assert afi_policy(100)[0] == "hard"


def test_approved_difficulty_change_artifact_is_reviewable_and_unique() -> None:
    path = Path(__file__).parents[1] / "difficulty-changes-approved.json"
    changes = json.loads(path.read_text(encoding="utf-8"))

    assert len(changes) == 40
    assert len({item["quote_id"] for item in changes}) == len(changes)
    assert all(item["review_status"] == "approved" for item in changes)
    assert all(item["current_difficulty"] != item["proposed_difficulty"] for item in changes)
    assert all(item["rationale"] and item["quote_source_urls"] for item in changes)


def test_full_review_covers_every_catalog_quote_and_flags_uncertainty() -> None:
    path = Path(__file__).parents[1] / "difficulty-review.json"
    review = json.loads(path.read_text(encoding="utf-8"))

    assert len(review) == 145
    assert len({item["quote_id"] for item in review}) == 145
    assert sum(item["review_status"] == "pending" for item in review) == 25
