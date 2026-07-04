from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from f2m_engine.domain.cvp import scoring_profile_from_cvp
from f2m_engine.domain.recommendation_settings import (
    apply_business_priority_boost,
    apply_effective_dish_tags,
    apply_margin_boost,
    apply_sets_boost,
    normalize_recommendation_settings,
    system_exclusion_reasons_for_dish,
)


@dataclass(frozen=True)
class RecommendationEngineResult:
    candidates: list[dict[str, Any]]
    hard_filter_status_by_dish: dict[str, dict[str, Any]]
    constraint_audit_rows: list[list[Any]]
    status: str
    requested_top_k: int
    available_count: int


def rank_dishes_for_cvp(
    *,
    cvp_profile: dict[str, Any],
    dish_cache: list[dict[str, Any]],
    dish_ingredient_evidence: dict[str, set[str]],
    request_tags: list[str],
    recent_counts: dict[str, int],
    top_k: int,
    recommendation_settings: dict[str, Any] | None = None,
    request_context: dict[str, Any] | None = None,
) -> RecommendationEngineResult:
    # Import here to keep the public engine contract small while the legacy
    # scorer is being split into explicit modules.
    from f2m_engine.pipelines.scoring_deterministic import (  # noqa: PLC0415
        _apply_hard_filters,
        _debug_explanation,
        _dish_snapshot_id,
        _dish_sort_key,
        _score_single_dish,
        _user_explanation,
    )

    profile = scoring_profile_from_cvp(cvp_profile)
    constraints = sorted(profile.get("hard_constraints", []))
    user_id = int(cvp_profile["user_id"])
    settings = normalize_recommendation_settings(recommendation_settings)
    effective_dish_cache = apply_effective_dish_tags(dish_cache=dish_cache, settings=settings)
    dishes_by_id = {str(dish.get("dish_id")): dish for dish in effective_dish_cache}
    effective_ingredient_evidence = {
        str(dish.get("dish_id")): set((dish.get("ingredient") or {}).keys())
        for dish in effective_dish_cache
    }
    survivors: list[dict[str, Any]] = []
    constraint_audit_rows: list[list[Any]] = []
    hard_filter_status_by_dish: dict[str, dict[str, Any]] = {}

    for dish in sorted(effective_dish_cache, key=lambda item: _dish_sort_key(item.get("dish_id"))):
        dish_id = str(dish.get("dish_id"))
        system_reasons = system_exclusion_reasons_for_dish(
            dish=dish,
            settings=settings,
            request_context=request_context or {},
        )
        if system_reasons:
            excluded = True
            reasons = system_reasons
            compliance_unknown = False
        else:
            excluded, reasons, compliance_unknown = _apply_hard_filters(
                constraints=constraints,
                dish=dish,
                ingredient_evidence=effective_ingredient_evidence.get(
                    dish_id,
                    dish_ingredient_evidence.get(dish_id, set()),
                ),
            )
        hard_filter_status_by_dish[dish_id] = {
            "excluded": excluded,
            "reasons": reasons,
            "compliance_unknown": compliance_unknown,
        }
        constraint_audit_rows.append(
            [
                user_id,
                dish_id,
                dish.get("meta", {}).get("name", ""),
                excluded,
                "|".join(reasons),
                compliance_unknown,
            ]
        )
        if excluded:
            continue

        breakdown = _score_single_dish(
            profile=profile,
            dish=dish,
            request_tags=request_tags,
            recent_repeat_count=recent_counts.get(dish_id, 0),
        )
        survivors.append(
            {
                "user_id": user_id,
                "dish_id": dish_id,
                "dish_name": dish.get("meta", {}).get("name", ""),
                "score": round(breakdown["score"], 6),
                "score_breakdown": breakdown,
                "user_explanation": _user_explanation(dish=dish, breakdown=breakdown),
                "debug_explanation": _debug_explanation(dish=dish, breakdown=breakdown),
                "compliance_unknown": compliance_unknown,
                "dish_feature_snapshot_id": _dish_snapshot_id(dish),
                "dish_feature_version": dish.get("meta", {}).get("feature_version", "runtime_v1"),
            }
        )

    apply_business_priority_boost(
        rows=survivors,
        dishes_by_id=dishes_by_id,
        settings=settings,
        score_key="score",
    )
    apply_margin_boost(
        rows=survivors,
        dishes_by_id=dishes_by_id,
        settings=settings,
        score_key="score",
    )
    apply_sets_boost(
        rows=survivors,
        dishes_by_id=dishes_by_id,
        settings=settings,
        score_key="score",
        request_context=request_context or {},
    )

    for row in survivors:
        boost = round(float(row.get("business_priority_boost", 0.0)), 6)
        reasons = row.get("business_priority_reasons", [])
        margin_boost = round(float(row.get("margin_boost", 0.0)), 6)
        sets_boost = round(float(row.get("sets_boost", 0.0)), 6)
        row["score_breakdown"]["business_priority_boost"] = boost
        row["score_breakdown"]["margin_boost"] = margin_boost
        row["score_breakdown"]["sets_boost"] = sets_boost
        row["score_breakdown"]["score"] = round(float(row["score"]), 6)
        row["business_adjustments"] = {
            "priority_boost": boost,
            "priority_reasons": reasons,
            "priority_skipped_by_limit": bool(row.get("business_priority_skipped_by_limit", False)),
            "margin_boost": margin_boost,
            "sets_boost": sets_boost,
            "sets_boost_reasons": row.get("sets_boost_reasons", []),
        }
        extras = []
        if boost:
            extras.append(f"business_priority={boost}")
        if margin_boost:
            extras.append(f"margin={margin_boost}")
        if sets_boost:
            extras.append(f"sets={sets_boost}")
        if extras:
            row["debug_explanation"] = row["debug_explanation"] + " | " + " | ".join(extras)

    survivors.sort(key=lambda row: (-float(row["score"]), _dish_sort_key(row["dish_id"])))
    for idx, row in enumerate(survivors, start=1):
        row["rank"] = idx
        row["rank_position"] = idx
        row["frontend_order_contract"] = "backend_order"

    status = recommendation_status(available_count=len(survivors), requested_top_k=top_k)
    return RecommendationEngineResult(
        candidates=survivors,
        hard_filter_status_by_dish=hard_filter_status_by_dish,
        constraint_audit_rows=constraint_audit_rows,
        status=status,
        requested_top_k=int(top_k),
        available_count=len(survivors),
    )


def recommendation_status(available_count: int, requested_top_k: int) -> str:
    if int(available_count) <= 0:
        return "empty"
    if int(available_count) < int(requested_top_k):
        return "partial"
    return "ok"
