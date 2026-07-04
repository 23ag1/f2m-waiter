import json
from pathlib import Path

import pytest

from app.pipelines.questionnaire_engine import QuestionnaireNoSafeCandidates, recommend_questionnaire_only
from app.pipelines.questionnaire_normalizer import QuestionnaireNormalizationError
from app.pipelines.recommend_router import route_recommendation


def test_questionnaire_engine_normalizes_filters_and_scores(tmp_path: Path) -> None:
    _write_minimal_dish_cache(tmp_path)
    stats = recommend_questionnaire_only(
        derived_dir=tmp_path,
        user_id=5,
        top_k=10,
        request_context={"hunger_level": "full"},
        mode_resolution_source="explicit_request_mode",
        questionnaire_raw={"likes": ["люблю рыбу и суп"], "dislikes": ["аллергия на лактозу"]},
    )
    assert stats.request_id.startswith("qreq_")
    assert stats.survivors >= 1
    debug_path = tmp_path / "audit" / "questionnaire_normalized_profile_debug.json"
    assert debug_path.exists()
    payload = json.loads(debug_path.read_text(encoding="utf-8"))
    assert payload["user_id"] == 5


def test_questionnaire_engine_requires_raw_questionnaire(tmp_path: Path) -> None:
    with pytest.raises(QuestionnaireNormalizationError):
        recommend_questionnaire_only(
            derived_dir=tmp_path,
            user_id=5,
            top_k=10,
            request_context=None,
            mode_resolution_source="explicit_request_mode",
            questionnaire_raw=None,
        )


def test_questionnaire_only_route_never_calls_order_scorer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_minimal_dish_cache(tmp_path)
    def _unexpected_score_call(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("Order scorer must not be called in questionnaire_only mode")

    monkeypatch.setattr("app.pipelines.recommend_router.score_dishes_for_user", _unexpected_score_call)
    routed = route_recommendation(
        derived_dir=tmp_path,
        user_id=9,
        top_k=5,
        request_context={"hunger_level": "light"},
        questionnaire_raw={"likes": ["люблю рыбу"], "dislikes": ["аллергия на глютен"]},
        explicit_mode="questionnaire_only",
        environ={
            "RECOMMENDER_DEFAULT_MODE": "questionnaire_only",
            "ALLOW_ORDER_FALLBACK": "false",
        },
    )
    assert routed.scoring_stats is not None


def test_questionnaire_engine_returns_no_safe_candidates_when_all_blocked(tmp_path: Path) -> None:
    payload = [
        {
            "dish_id": "1",
            "ingredient": {"wheat": 1.0, "mushroom": 1.0},
            "hard_flags": {},
            "meta": {"name": "Mushroom pasta", "restaurant": "gc", "category": "main"},
        }
    ]
    (tmp_path / "dish_features_cache.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(QuestionnaireNoSafeCandidates) as exc_info:
        recommend_questionnaire_only(
            derived_dir=tmp_path,
            user_id=7,
            top_k=10,
            request_context=None,
            mode_resolution_source="explicit_request_mode",
            questionnaire_raw={"dislikes": ["аллергия на глютен", "категорически не ем грибы"]},
        )
    assert exc_info.value.candidate_count_before == 1
    assert exc_info.value.candidate_count_after == 0


def _write_minimal_dish_cache(base: Path) -> None:
    payload = [
        {
            "dish_id": "1",
            "ingredient": {"chicken": 1.0, "rice": 1.0},
            "hard_flags": {},
            "meta": {"name": "Chicken rice", "restaurant": "gc", "category": "main"},
        }
    ]
    (base / "dish_features_cache.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
