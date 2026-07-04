import json
from pathlib import Path

from app.pipelines.dish_constraints import apply_questionnaire_hard_filter, build_dish_constraints


def test_dish_constraints_extract_explicit_flags(tmp_path: Path) -> None:
    _write_dish_cache(
        tmp_path,
        [
            {
                "dish_id": "10",
                "ingredient": {"wheat": 1.0, "mushroom": 1.0, "onion": 1.0},
                "hard_flags": {},
                "meta": {"name": "Mushroom wheat soup", "restaurant": "gc", "category": "main"},
            }
        ],
    )
    constraints = build_dish_constraints(tmp_path)
    assert len(constraints) == 1
    row = constraints[0]
    assert row["constraint_flags"]["gluten"] is True
    assert row["constraint_flags"]["mushroom"] is True
    assert row["constraint_flags"]["onion"] is True


def test_dietary_conflicts_include_halal_like_explicit_only(tmp_path: Path) -> None:
    _write_dish_cache(
        tmp_path,
        [
            {
                "dish_id": "20",
                "ingredient": {"pork": 1.0, "onion": 1.0},
                "hard_flags": {},
                "meta": {"name": "Pork stew", "restaurant": "gc", "category": "main"},
            },
            {
                "dish_id": "21",
                "ingredient": {"chicken": 1.0, "rice": 1.0},
                "hard_flags": {},
                "meta": {"name": "Chicken rice", "restaurant": "gc", "category": "main"},
            },
        ],
    )
    constraints = build_dish_constraints(tmp_path)
    lookup = {row["dish_id"]: row for row in constraints}
    assert lookup["20"]["dietary_conflicts"]["halal_like_conflict"] is True
    assert lookup["21"]["dietary_conflicts"]["halal_like_conflict"] is False


def test_unresolved_relevant_safety_is_blocked_fail_closed(tmp_path: Path) -> None:
    _write_dish_cache(
        tmp_path,
        [
            {
                "dish_id": "30",
                "ingredient": {},
                "hard_flags": {},
                "meta": {"name": "Unknown composition dish", "restaurant": "gc", "category": "main"},
            }
        ],
    )
    constraints = build_dish_constraints(tmp_path)
    normalized = {
        "hard_constraints": {
            "allergens": ["gluten"],
            "intolerances": [],
            "ingredient_excludes": [],
            "dietary_rules": [],
            "unknown_or_needs_review": [],
        }
    }
    result = apply_questionnaire_hard_filter(
        request_id="req1",
        venue="gc",
        normalized_profile=normalized,
        dish_constraints=constraints,
    )
    assert result.candidate_count_before == 1
    assert result.candidate_count_after == 0
    assert result.zero_safe_candidates_flag is True
    assert result.blocked_rows[0]["blocked_reason_type"] in {"unresolved", "review_required"}


def _write_dish_cache(base: Path, rows: list[dict]) -> None:
    (base / "dish_features_cache.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
