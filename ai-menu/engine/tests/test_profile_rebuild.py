import json
from pathlib import Path

from app.pipelines.profile_rebuild import rebuild_profiles, show_profile


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file_obj:
        for row in rows:
            file_obj.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_rebuild_is_deterministic_and_keeps_constraints_separate(tmp_path: Path) -> None:
    derived = tmp_path / "derived"
    _write_jsonl(
        derived / "questionnaire_submissions.jsonl",
        [
            {
                "user_id": 1,
                "questionnaire_type": "seed_json",
                "raw_answers_json": {"likes": ["люблю острое"], "dislikes": ["аллергия на арахис"]},
                "extracted_json": {"likes": ["люблю острое"], "dislikes": ["аллергия на арахис"]},
            }
        ],
    )
    _write_jsonl(
        derived / "user_constraints.jsonl",
        [
            {
                "user_id": 1,
                "constraint_key": "peanut",
                "scope": "hard",
                "source": "seed_json",
                "reason_text": "allergy",
                "confidence": 0.9,
            }
        ],
    )
    _write_jsonl(
        derived / "user_feature_values.jsonl",
        [
            {
                "user_id": 1,
                "profile_layer": "explicit",
                "axis": "taste",
                "feature_key": "spicy",
                "weight": 0.7,
                "source": "questionnaire",
                "confidence": 0.75,
            }
        ],
    )
    _write_jsonl(
        derived / "events.jsonl",
        [
            {
                "source_system": "cust_json",
                "event_uuid": "1.1",
                "user_id": 1,
                "event_type": "purchase_paid",
                "payload_json": {"dish": "Острый суп", "context": "Обед"},
            }
        ],
    )
    _write_jsonl(
        derived / "event_items.jsonl",
        [
            {
                "source_system": "cust_json",
                "event_uuid": "1.1",
                "line_no": 1,
                "dish_name": "Острый суп",
                "qty": 1,
                "modifiers_json": {},
            }
        ],
    )
    _write_jsonl(
        derived / "dish_feature_values.jsonl",
        [
            {"dish_id": "d1", "axis": "taste", "feature_key": "spicy", "value_num": 0.8, "source": "rule"},
            {"dish_id": "d1", "axis": "cuisine", "feature_key": "asian", "value_num": 0.7, "source": "rule"},
            {"dish_id": "d1", "axis": "restriction", "feature_key": "peanut", "value_bool": False, "source": "rule"},
        ],
    )
    (derived / "dish_features_cache.json").write_text(
        json.dumps(
            [
                {
                    "dish_id": "d1",
                    "meta": {"name": "Острый суп"},
                    "ingredient": {},
                    "taste": {"spicy": 0.8},
                    "cuisine": {"asian": 0.7},
                    "format_texture": {"soup": 1.0},
                    "context": {},
                    "hard_flags": {},
                    "nutrition": {},
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    stats1 = rebuild_profiles(derived_dir=derived, taxonomy_path=Path("docs/runtime_taxonomy_resolved_v1.json"))
    first_jsonl = (derived / "user_feature_values.jsonl").read_text(encoding="utf-8")
    first_cache = (derived / "user_profiles_cache.json").read_text(encoding="utf-8")
    stats2 = rebuild_profiles(derived_dir=derived, taxonomy_path=Path("docs/runtime_taxonomy_resolved_v1.json"))
    second_jsonl = (derived / "user_feature_values.jsonl").read_text(encoding="utf-8")
    second_cache = (derived / "user_profiles_cache.json").read_text(encoding="utf-8")

    assert stats1.time_is_synthetic is True
    assert stats2.time_is_synthetic is True
    assert first_jsonl == second_jsonl
    assert first_cache == second_cache
    assert "peanut" not in first_jsonl


def test_show_profile_outputs_constraints(tmp_path: Path) -> None:
    derived = tmp_path / "derived"
    (derived / "user_profiles_cache.json").parent.mkdir(parents=True, exist_ok=True)
    (derived / "user_profiles_cache.json").write_text(
        json.dumps(
            [
                {
                    "user_id": 1,
                    "hard_constraints": ["peanut"],
                    "explicit": {"taste": {"spicy": 0.7}},
                    "long_term": {"cuisine": {"asian": 0.3}},
                    "short_term": {"context": {"lunch": 0.5}},
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
        [{"user_id": 1, "constraint_key": "peanut", "scope": "hard"}],
    )
    output = show_profile(derived_dir=derived, user_id=1)
    assert "hard_constraints=['peanut']" in output
