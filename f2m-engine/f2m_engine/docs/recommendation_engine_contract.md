# Recommendation Engine Contract

Date: 2026-06-13

## Purpose

The recommendation engine is the deterministic runtime layer that consumes:

- `cvp_profile` from the CVP layer;
- dish tags/features from `dish_features_cache.json`;
- request context tags.

It does not own CVP semantics and does not write profile features.

## Input

```json
{
  "cvp_profile": {"cvp_version": "cvp_v1", "...": "..."},
  "dish_features": [{"dish_id": "1", "taste": {}, "ingredient": {}, "hard_flags": {}}],
  "request_context": {"time_of_day": "lunch", "venue": "gc"},
  "top_k": 10
}
```

## Runtime Order

1. Read optional `recommendation_settings.json`.
2. Apply admin manual tag overrides to build effective dish tags.
3. Apply system hard rules: POS stop-list and alcohol-without-explicit-request.
4. Read hard constraints from `cvp_profile.hard_constraints`.
5. Exclude unsafe dishes before scoring.
6. Score only survivors.
7. Apply bounded business priority boosts only to survivors.
8. Sort by backend score and deterministic tie-breakers.
9. Return backend order as authoritative.

Frontend must render the received order and must not resort by `final_score` or `score`.

## Output Fields

Every candidate returned by the order-history engine includes:

- `rank` and `rank_position`;
- `frontend_order_contract = "backend_order"`;
- `recommendation_status`;
- `score_breakdown`;
- deterministic `user_explanation` and `debug_explanation`.

`recommendation_state.json` is written with:

```json
{
  "status": "ok | partial | empty",
  "requested_top_k": 10,
  "available_count": 7,
  "partial_state": true,
  "empty_state": false,
  "backend_order_contract": "backend_order"
}
```

## Empty And Partial States

- `empty`: no safe candidates remain after hard filtering.
- `partial`: safe candidates exist, but fewer than requested `top_k`.
- `ok`: at least `top_k` safe candidates are available.

The engine must not fill empty slots with hard-filtered or unsafe dishes.

## Recommendation Settings

The runtime can read `recommendation_settings.json` from the same `derived_dir` as the dish cache.

Supported MVP fields:

```json
{
  "manual_tag_overrides": [
    {"dish_id": "42", "axis": "format_texture", "key": "fried", "action": "remove"}
  ],
  "stop_list_dish_ids": ["42"],
  "priority_dish_ids": ["17"],
  "priority_ingredients": ["chicken", "курица"],
  "priority_boost": 0.12,
  "max_priority_boosted_items": 5,
  "allow_alcohol": false,
  "context_scenarios": {
    "business_lunch": {"context_tags": ["work_lunch", "quick"]}
  },
  "business_goals": {"sets": [], "margin": {}, "upsells": [], "modifiers": []}
}
```

Notes:

- manual tag overrides accept only closed taxonomy axes; ingredient aliases normalize to canonical ingredient keys;
- POS stop-list excludes dishes from recommendations, but the app can still render them in the general menu;
- priority boosts are bounded and cannot bypass system hard rules or CVP hard constraints;
- alcohol is excluded unless settings or request context explicitly allow/request it;
- margin, sets, upsells, and modifiers are reserved as config fields, but not scored until POS data and product rules are finalized.

## Implementation

- Public contract: `f2m_engine.pipelines.recommendation_engine.rank_dishes_for_cvp`.
- Adapter: `app.domain.cvp.scoring_profile_from_cvp`.
- Current CLI/API path: `score-dishes` and `POST /recommendations/score`.

## Out Of Scope

- ML reranking.
- Runtime LLM comments.
- Unbounded admin boosts.
- Margin/set/upsell/modifier optimization until POS coverage and product rules are agreed.
