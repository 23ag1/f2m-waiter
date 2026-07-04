import json
from pathlib import Path

from app.pipelines.scoring_deterministic import explain_dish_for_user, score_dishes_for_user


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file_obj:
        for row in rows:
            file_obj.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_scoring_is_deterministic_and_hard_filtered(tmp_path: Path) -> None:
    derived = tmp_path / "derived"
    derived.mkdir(parents=True, exist_ok=True)
    (derived / "user_profiles_cache.json").write_text(
        json.dumps(
            [
                {
                    "user_id": 5,
                    "hard_constraints": ["vegan"],
                    "explicit": {"cuisine": {"asian": 0.7}},
                    "long_term": {},
                    "short_term": {},
                    "meta": {"time_is_synthetic": True},
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_jsonl(
        derived / "user_constraints.jsonl",
        [{"user_id": 5, "constraint_key": "vegan", "scope": "hard"}],
    )
    _write_jsonl(derived / "events.jsonl", [])
    (derived / "dish_features_cache.json").write_text(
        json.dumps(
            [
                {
                    "dish_id": "1",
                    "taste": {},
                    "ingredient": {"chicken": 1.0},
                    "cuisine": {"asian": 1.0},
                    "format_texture": {},
                    "context": {},
                    "hard_flags": {},
                    "nutrition": {},
                    "meta": {"name": "Chicken bowl", "restaurant": "X", "category": "Y"},
                },
                {
                    "dish_id": "2",
                    "taste": {},
                    "ingredient": {"tofu": 1.0},
                    "cuisine": {"asian": 1.0},
                    "format_texture": {},
                    "context": {},
                    "hard_flags": {},
                    "nutrition": {},
                    "meta": {"name": "Tofu bowl", "restaurant": "X", "category": "Y"},
                },
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_jsonl(derived / "dish_feature_values.jsonl", [])
    _write_jsonl(derived / "user_feature_values.jsonl", [])

    score_dishes_for_user(derived_dir=derived, user_id=5, top_k=5, request_context={})
    first_rows = [json.loads(line) for line in (derived / "recommendation_scores.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    score_dishes_for_user(derived_dir=derived, user_id=5, top_k=5, request_context={})
    second_rows = [json.loads(line) for line in (derived / "recommendation_scores.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

    for row in first_rows:
        row.pop("recommendation_request_id", None)
    for row in second_rows:
        row.pop("recommendation_request_id", None)
    assert first_rows == second_rows
    serialized = json.dumps(second_rows, ensure_ascii=False)
    assert '"dish_id": "1"' not in serialized
    assert '"dish_id": "2"' in serialized


def test_explain_dish_stable_output(tmp_path: Path) -> None:
    derived = tmp_path / "derived"
    derived.mkdir(parents=True, exist_ok=True)
    _write_jsonl(
        derived / "recommendation_scores.jsonl",
        [
            {
                "user_id": 1,
                "dish_id": "9",
                "dish_name": "Dish",
                "score": 1.2,
                "user_explanation": "ok",
                "debug_explanation": "dbg",
            }
        ],
    )
    text = explain_dish_for_user(derived_dir=derived, user_id=1, dish_id="9")
    assert "dish_id=9" in text
    assert "score=1.2" in text
