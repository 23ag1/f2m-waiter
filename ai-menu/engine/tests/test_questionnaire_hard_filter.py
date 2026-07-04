import json
from pathlib import Path

import pytest

from app.pipelines.questionnaire_engine import QuestionnaireNoSafeCandidates
from app.pipelines.recommend_router import route_recommendation


def test_explicit_hard_conflicts_blocked_before_scoring(tmp_path: Path) -> None:
    _write_dish_cache(
        tmp_path,
        [
            {
                "dish_id": "100",
                "ingredient": {"wheat": 1.0, "mushroom": 1.0},
                "hard_flags": {},
                "meta": {"name": "Mushroom pasta", "restaurant": "gc", "category": "main"},
            },
            {
                "dish_id": "101",
                "ingredient": {"chicken": 1.0, "rice": 1.0},
                "hard_flags": {},
                "meta": {"name": "Chicken rice", "restaurant": "gc", "category": "main"},
            },
        ],
    )
    routed = route_recommendation(
        derived_dir=tmp_path,
        user_id=1,
        top_k=10,
        request_context={"venue": "gc"},
        questionnaire_raw={"dislikes": ["аллергия на глютен", "категорически не ем грибы"]},
        explicit_mode="questionnaire_only",
        environ={"RECOMMENDER_DEFAULT_MODE": "questionnaire_only", "ALLOW_ORDER_FALLBACK": "false"},
    )
    debug = json.loads((tmp_path / "audit" / "questionnaire_normalized_profile_debug.json").read_text(encoding="utf-8"))
    summary = debug["candidate_filter_summary"]
    assert int(summary["candidate_count_before"]) == 2
    assert int(summary["candidate_count_after"]) == 1
    assert int(summary["blocked_count"]) == 1
    assert routed.scoring_stats is not None
    ranked_rows = [json.loads(line) for line in (tmp_path / "recommendation_scores.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    ranked_ids = {row["dish_id"] for row in ranked_rows}
    assert "100" not in ranked_ids
    assert "101" in ranked_ids


def test_zero_safe_candidates_path_explicit_and_no_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_dish_cache(
        tmp_path,
        [
            {
                "dish_id": "200",
                "ingredient": {"wheat": 1.0},
                "hard_flags": {},
                "meta": {"name": "Bread bowl", "restaurant": "gc", "category": "main"},
            }
        ],
    )

    def _unexpected_score_call(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("Order scorer must not be called")

    monkeypatch.setattr("app.pipelines.recommend_router.score_dishes_for_user", _unexpected_score_call)
    with pytest.raises(QuestionnaireNoSafeCandidates) as exc_info:
        route_recommendation(
            derived_dir=tmp_path,
            user_id=2,
            top_k=10,
            request_context={"venue": "gc"},
            questionnaire_raw={"dislikes": ["аллергия на глютен"]},
            explicit_mode="questionnaire_only",
            environ={"RECOMMENDER_DEFAULT_MODE": "questionnaire_only", "ALLOW_ORDER_FALLBACK": "false"},
        )
    assert exc_info.value.candidate_count_before == 1
    assert exc_info.value.candidate_count_after == 0


def test_halal_like_blocks_explicit_pork_alcohol_offal_only(tmp_path: Path) -> None:
    _write_dish_cache(
        tmp_path,
        [
            {
                "dish_id": "300",
                "ingredient": {"pork": 1.0},
                "hard_flags": {},
                "meta": {"name": "Pork grill", "restaurant": "gc", "category": "main"},
            },
            {
                "dish_id": "301",
                "ingredient": {"chicken": 1.0},
                "hard_flags": {},
                "meta": {"name": "Chicken rice", "restaurant": "gc", "category": "main"},
            },
        ],
    )
    route_recommendation(
        derived_dir=tmp_path,
        user_id=3,
        top_k=10,
        request_context={"venue": "gc"},
        questionnaire_raw={"dislikes": ["соблюдаю халяль"]},
        explicit_mode="questionnaire_only",
        environ={"RECOMMENDER_DEFAULT_MODE": "questionnaire_only", "ALLOW_ORDER_FALLBACK": "false"},
    )
    debug = json.loads((tmp_path / "audit" / "questionnaire_normalized_profile_debug.json").read_text(encoding="utf-8"))
    summary = debug["candidate_filter_summary"]
    assert int(summary["candidate_count_before"]) == 2
    assert int(summary["candidate_count_after"]) == 1


def test_non_recommendable_items_not_in_top_output(tmp_path: Path) -> None:
    _write_dish_cache(
        tmp_path,
        [
            {
                "dish_id": "400",
                "ingredient": {"chicken": 1.0},
                "hard_flags": {},
                "meta": {"name": "Chicken bowl", "restaurant": "gc", "category": "main"},
            },
            {
                "dish_id": "401",
                "ingredient": {"garlic": 1.0},
                "hard_flags": {},
                "meta": {"name": "Соус чесночный", "restaurant": "gc", "category": "sauce"},
            },
            {
                "dish_id": "402",
                "ingredient": {"salt": 1.0},
                "hard_flags": {},
                "meta": {"name": "Service add-on", "restaurant": "gc", "category": "service"},
            },
        ],
    )
    route_recommendation(
        derived_dir=tmp_path,
        user_id=4,
        top_k=10,
        request_context={"venue": "gc"},
        questionnaire_raw={"likes": ["люблю мясо"]},
        explicit_mode="questionnaire_only",
        environ={"RECOMMENDER_DEFAULT_MODE": "questionnaire_only", "ALLOW_ORDER_FALLBACK": "false"},
    )
    ranked_rows = [json.loads(line) for line in (tmp_path / "recommendation_scores.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    ranked_ids = [row["dish_id"] for row in ranked_rows]
    assert ranked_ids == ["400"]


def _write_dish_cache(base: Path, rows: list[dict]) -> None:
    (base / "dish_features_cache.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
