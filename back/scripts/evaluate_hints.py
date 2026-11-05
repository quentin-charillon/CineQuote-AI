"""Offline safety check for fixed mocked hint outputs; makes no API calls."""

import argparse
import json
from pathlib import Path

from app.repositories.questions import JsonQuestionRepository
from app.services.hints import validate_hint


def build_report() -> dict[str, object]:
    questions = JsonQuestionRepository().list_all()[:4]
    mocked_outputs = [
        "Focus on the line's mood and the era suggested by its phrasing.",
        f"This line comes from {questions[1].film_title}.",
        "Option B is the correct choice.",
        "",
    ]
    validations = [
        validate_hint(output, question.film_title)
        for question, output in zip(questions, mocked_outputs, strict=True)
    ]
    total = len(validations)
    leaks = sum(item.title_leaked or item.answer_label_leaked for item in validations)
    passed = sum(item.passed for item in validations)
    fallbacks = total - passed

    return {
        "evaluation_type": "offline_mock_safety_check",
        "disclaimer": "This does not measure real-world model accuracy or quality.",
        "sample_count": total,
        "leak_rate": leaks / total,
        "fallback_rate": fallbacks / total,
        "validation_pass_rate": passed / total,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional path for the JSON report")
    args = parser.parse_args()
    report = json.dumps(build_report(), indent=2)
    if args.output:
        args.output.write_text(f"{report}\n", encoding="utf-8")
    else:
        print(report)


if __name__ == "__main__":
    main()
