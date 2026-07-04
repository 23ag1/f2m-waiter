from pathlib import Path

import json
import pytest

from app.pipelines.questionnaire_normalizer import QuestionnaireNormalizationError
from app.pipelines.recommend_router import route_recommendation, resolve_mode
from app.pipelines.scoring_deterministic import ScoringStats


def test_resolve_mode_prefers_explicit_mode_over_env_default() -> None:
    resolution = resolve_mode(
        explicit_mode="orders_only",
        environ={
            "RECOMMENDER_DEFAULT_MODE": "questionnaire_only",
            "ALLOW_ORDER_FALLBACK": "false",
        },
    )
    assert resolution.resolved_mode == "orders_only"
    assert resolution.engine_selected == "orders_engine"
    assert resolution.mode_resolution_source == "explicit_request_mode"
    assert resolution.fallback_used is False


def test_questionnaire_only_routes_to_stub_without_order_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _unexpected_score_call(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("Order scorer must not be called for questionnaire_only mode")

    monkeypatch.setattr("app.pipelines.recommend_router.score_dishes_for_user", _unexpected_score_call)
    with pytest.raises(QuestionnaireNormalizationError):
        route_recommendation(
            derived_dir=tmp_path,
            user_id=1,
            top_k=5,
            request_context={},
            explicit_mode="questionnaire_only",
            environ={
                "RECOMMENDER_DEFAULT_MODE": "questionnaire_only",
                "ALLOW_ORDER_FALLBACK": "false",
            },
        )


def test_questionnaire_only_returns_ranked_results_after_scoring(tmp_path: Path) -> None:
    _write_minimal_dish_cache(tmp_path)
    routed = route_recommendation(
        derived_dir=tmp_path,
        user_id=1,
        top_k=5,
        request_context={"hunger_level": "full"},
        questionnaire_raw={"likes": ["люблю рыбу"], "dislikes": ["аллергия на глютен"]},
        explicit_mode="questionnaire_only",
        environ={
            "RECOMMENDER_DEFAULT_MODE": "questionnaire_only",
            "ALLOW_ORDER_FALLBACK": "false",
        },
    )
    assert routed.mode_resolution.engine_selected == "questionnaire_engine"
    assert routed.mode_resolution.fallback_used is False
    assert routed.scoring_stats is not None
    assert routed.scoring_stats.survivors >= 0


def test_orders_only_uses_existing_order_engine(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _fake_score_call(*args, **kwargs):  # type: ignore[no-untyped-def]
        return ScoringStats(user_id=7, request_id="req_test", survivors=3, excluded=1, top_k=5)

    monkeypatch.setattr("app.pipelines.recommend_router.score_dishes_for_user", _fake_score_call)
    routed = route_recommendation(
        derived_dir=tmp_path,
        user_id=7,
        top_k=5,
        request_context={},
        explicit_mode="orders_only",
        environ={
            "RECOMMENDER_DEFAULT_MODE": "questionnaire_only",
            "ALLOW_ORDER_FALLBACK": "false",
        },
    )
    assert routed.scoring_stats is not None
    assert routed.scoring_stats.request_id == "req_test"
    assert routed.mode_resolution.engine_selected == "orders_engine"
    assert routed.mode_resolution.fallback_used is False


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
