from __future__ import annotations

import json
from typing import Any


def score_questionnaire_candidates(
    request_id: str,
    user_id: int,
    normalized_profile: dict[str, Any],
    safe_candidates: list[dict[str, Any]],
    request_context: dict[str, Any] | None,
    top_k: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _ = top_k
    context = request_context or {}
    eligible_candidates = safe_candidates
    scored: list[dict[str, Any]] = []
    for dish in sorted(eligible_candidates, key=lambda row: (str(row.get("dish_id", "")), str(row.get("dish_name", "")))):
        component = _score_single_candidate(normalized_profile=normalized_profile, dish=dish, request_context=context)
        scored.append(
            {
                "request_id": request_id,
                "user_id": int(user_id),
                "dish_id": str(dish.get("dish_id", "")),
                "dish_name": str(dish.get("dish_name", "")),
                "hard_filter_pass": True,
                "blocked_reasons": [],
                **component,
            }
        )

    scored.sort(key=lambda row: (-float(row["final_score_base"]), str(row["dish_name"]), str(row["dish_id"])))
    seen_signatures: set[str] = set()
    for row in scored:
        signature = _signature_for_diversity(row)
        diversity_bonus = 0.05 if signature not in seen_signatures else 0.0
        seen_signatures.add(signature)
        row["diversity_bonus"] = round(diversity_bonus, 6)
        row["final_score"] = round(float(row["final_score_base"]) + diversity_bonus, 6)

    scored.sort(key=lambda row: (-float(row["final_score"]), str(row["dish_name"]), str(row["dish_id"])))
    for idx, row in enumerate(scored, start=1):
        row["rank"] = idx
        row["score"] = row["final_score"]
        row["explanation"] = _explain_row(row)
        row.pop("final_score_base", None)
    trace = {
        "request_id": request_id,
        "candidate_count_before_filter": int(context.get("candidate_count_before_filter", 0)),
        "candidate_count_after_filter": int(context.get("candidate_count_after_filter", len(safe_candidates))),
        "ranked_candidate_count": len(scored),
        "top_1_dish_id": scored[0]["dish_id"] if scored else "",
        "top_1_score": scored[0]["final_score"] if scored else 0.0,
        "top_5_ids": "|".join(row["dish_id"] for row in scored[:5]),
    }
    return scored, trace


def _score_single_candidate(
    normalized_profile: dict[str, Any],
    dish: dict[str, Any],
    request_context: dict[str, Any],
) -> dict[str, float]:
    desired_content_match = _desired_content_match(normalized_profile=normalized_profile, dish=dish)
    satiety_match = _satiety_match(normalized_profile=normalized_profile, dish=dish)
    nutrition_match = _nutrition_match(normalized_profile=normalized_profile, dish=dish)
    cuisine_match = _cuisine_match(normalized_profile=normalized_profile, dish=dish)
    familiarity_novelty_match = _familiarity_novelty_match(normalized_profile=normalized_profile, dish=dish)
    soft_negative_penalty = _soft_negative_penalty(normalized_profile=normalized_profile, dish=dish)
    venue_boost = _venue_boost(request_context=request_context, dish=dish)
    final_score_base = (
        desired_content_match
        + satiety_match
        + nutrition_match
        + cuisine_match
        + familiarity_novelty_match
        - soft_negative_penalty
        + venue_boost
    )
    return {
        "desired_content_match": round(desired_content_match, 6),
        "satiety_match": round(satiety_match, 6),
        "nutrition_match": round(nutrition_match, 6),
        "cuisine_match": round(cuisine_match, 6),
        "familiarity_novelty_match": round(familiarity_novelty_match, 6),
        "soft_negative_penalty": round(soft_negative_penalty, 6),
        "diversity_bonus": 0.0,
        "venue_boost": round(venue_boost, 6),
        "final_score_base": round(final_score_base, 6),
    }


def _desired_content_match(normalized_profile: dict[str, Any], dish: dict[str, Any]) -> float:
    desired = normalized_profile.get("soft_preferences", {}).get("desired_content", {}) or {}
    want_now = normalized_profile.get("request_context", {}).get("want_now", []) or []
    keys = sorted(set([*desired.keys(), *[str(v) for v in want_now]]))
    if not keys:
        return 0.0
    points = 0.0
    for key in keys:
        weight = max(float(desired.get(key, 0.0)), 1.0 if key in want_now else 0.0)
        points += weight * _dish_content_signal(dish=dish, key=key)
    return 0.9 * points / max(1, len(keys))


def _dish_content_signal(dish: dict[str, Any], key: str) -> float:
    ingredients = dish.get("ingredient_features", {}) or {}
    flags = dish.get("constraint_flags", {}) or {}
    format_texture = dish.get("format_texture_features", {}) or {}
    taste = dish.get("taste_features", {}) or {}
    dish_name = _norm(str(dish.get("dish_name", "")))
    if key == "fish_seafood":
        return 1.0 if bool(flags.get("fish_seafood")) else 0.0
    if key == "meat":
        return 1.0 if any(k in ingredients for k in ("beef", "lamb", "chicken", "turkey", "pork", "bacon")) else 0.0
    if key == "soup":
        return max(float(format_texture.get("soup", 0.0)), 1.0 if "суп" in dish_name else 0.0)
    if key == "sweet":
        return max(float(taste.get("sweet", 0.0)), 1.0 if "десерт" in dish_name else 0.0)
    if key == "vegetables":
        veg_tokens = ("tomato", "cucumber", "broccoli", "greens", "vegetable")
        return 1.0 if any(token in ingredients for token in veg_tokens) else 0.0
    if key == "spicy":
        return 1.0 if bool(flags.get("spicy")) else float(taste.get("spicy", 0.0))
    return 0.0


def _satiety_match(normalized_profile: dict[str, Any], dish: dict[str, Any]) -> float:
    satiety = str(normalized_profile.get("request_context", {}).get("satiety", "") or "")
    if not satiety:
        return 0.0
    satiety_class = str((dish.get("nutrition_features", {}) or {}).get("satiety_class", "") or "")
    if not satiety_class:
        return 0.0
    mapping = {"snack": "snack", "light_meal": "light", "full_meal": "hearty"}
    return 0.7 if mapping.get(satiety, "") == satiety_class else 0.0


def _nutrition_match(normalized_profile: dict[str, Any], dish: dict[str, Any]) -> float:
    targets = normalized_profile.get("soft_preferences", {}).get("nutrition", {}) or {}
    if not targets:
        return 0.0
    nutrition = dish.get("nutrition_features", {}) or {}
    ingredients = dish.get("ingredient_features", {}) or {}
    kcal = _safe_float(nutrition.get("kcal_per_portion"))
    protein = _safe_float(nutrition.get("protein_per_100g"))
    carbs = _safe_float(nutrition.get("carb_per_100g"))
    has_added_sugar = "sugar" in ingredients
    weighted_points = 0.0
    total_weight = 0.0
    for key, pref in targets.items():
        weight = max(0.0, float(pref))
        if weight <= 0.0:
            continue
        total_weight += weight
        point = 0.0
        if key == "low_calorie":
            bool_bonus = 0.45 if bool(nutrition.get("low_calorie")) else 0.0
            kcal_bonus = _bounded((450.0 - kcal) / 350.0) * 0.55
            point = bool_bonus + kcal_bonus
        elif key == "high_protein":
            bool_bonus = 0.4 if bool(nutrition.get("high_protein")) else 0.0
            protein_bonus = _bounded(protein / 30.0) * 0.6
            point = bool_bonus + protein_bonus
        elif key == "no_sugar":
            if has_added_sugar:
                point = 0.0
            else:
                carb_bonus = _bounded((12.0 - carbs) / 12.0) * 0.5
                point = 0.5 + carb_bonus
        weighted_points += weight * min(1.0, point)
    if total_weight <= 0.0:
        return 0.0
    return 0.9 * (weighted_points / total_weight)


def _cuisine_match(normalized_profile: dict[str, Any], dish: dict[str, Any]) -> float:
    prefs = normalized_profile.get("soft_preferences", {}).get("cuisine", {}) or {}
    if not prefs:
        return 0.0
    cuisine = dish.get("cuisine_features", {}) or {}
    score = 0.0
    for key, pref in prefs.items():
        score += float(pref) * float(cuisine.get(key, 0.0))
    return 0.5 * score


def _familiarity_novelty_match(normalized_profile: dict[str, Any], dish: dict[str, Any]) -> float:
    prefs = normalized_profile.get("soft_preferences", {}).get("familiarity_novelty", {}) or {}
    if not prefs:
        return 0.0
    cuisine = dish.get("cuisine_features", {}) or {}
    adventurous_proxy = max(float(cuisine.get("author_style", 0.0)), float(cuisine.get("asian", 0.0)))
    familiar_proxy = max(float(cuisine.get("home_style", 0.0)), float(cuisine.get("russian_home", 0.0)))
    score = 0.0
    score += float(prefs.get("adventurous_food", 0.0)) * adventurous_proxy
    score += float(prefs.get("familiar_food", 0.0)) * familiar_proxy
    return 0.35 * score


def _soft_negative_penalty(normalized_profile: dict[str, Any], dish: dict[str, Any]) -> float:
    negatives = normalized_profile.get("soft_preferences", {}).get("soft_negative_ingredients", {}) or {}
    if not negatives:
        return 0.0
    ingredients = dish.get("ingredient_features", {}) or {}
    flags = dish.get("constraint_flags", {}) or {}
    penalty = 0.0
    for key, weight in negatives.items():
        hit = False
        if key in ingredients:
            hit = True
        if key == "onion" and bool(flags.get("onion")):
            hit = True
        if key == "mushroom" and bool(flags.get("mushroom")):
            hit = True
        if key in ("spicy_ingredients", "spicy") and bool(flags.get("spicy")):
            hit = True
        if key == "offal" and bool(flags.get("offal")):
            hit = True
        if hit:
            penalty += 0.4 * float(weight)
    return penalty


def _venue_boost(request_context: dict[str, Any], dish: dict[str, Any]) -> float:
    requested = _norm(str(request_context.get("venue", "") or request_context.get("store_id", "") or ""))
    if not requested:
        return 0.0
    dish_venue = _norm(str(dish.get("venue", "")))
    return 0.2 if requested and dish_venue and requested in dish_venue else 0.0


def _signature_for_diversity(row: dict[str, Any]) -> str:
    payload = {
        "cuisine": row.get("cuisine_match", 0.0),
        "satiety": row.get("satiety_match", 0.0),
        "desired": row.get("desired_content_match", 0.0),
    }
    return json.dumps(payload, sort_keys=True)


def _is_recommendable_candidate(dish: dict[str, Any]) -> bool:
    category = _norm(str(dish.get("category", "")))
    name = _norm(str(dish.get("dish_name", "")))
    merged = f"{category} {name}"
    banned_tokens = (
        "ingredient",
        "ингредиент",
        "semi_finished",
        "полуфабрикат",
        "service",
        "сервис",
        "addon",
        "add-on",
        "добавк",
        "соус",
        "sauce",
        "condiment",
        "соль",
        "перец",
        "drink",
        "beverage",
        "напит",
        "cola",
        "fanta",
        "sprite",
        "лимонад",
        "мохито",
        "coffee",
        "кофе",
        "tea",
        "чай",
        "сок",
        "juice",
    )
    return not any(token in merged for token in banned_tokens)


def _explain_row(row: dict[str, Any]) -> str:
    parts = [
        f"desired={row['desired_content_match']}",
        f"satiety={row['satiety_match']}",
        f"nutrition={row['nutrition_match']}",
        f"cuisine={row['cuisine_match']}",
        f"novelty={row['familiarity_novelty_match']}",
        f"soft_neg=-{row['soft_negative_penalty']}",
        f"diversity={row['diversity_bonus']}",
    ]
    return " | ".join(parts)


def _norm(value: str) -> str:
    return str(value or "").lower().replace("ё", "е").strip()


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _bounded(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
