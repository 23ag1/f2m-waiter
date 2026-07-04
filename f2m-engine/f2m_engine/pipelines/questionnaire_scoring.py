from __future__ import annotations

import json
from typing import Any

from f2m_engine.domain.explanation_guard import filter_supported_display_tags
from f2m_engine.domain.recommendation_settings import apply_business_priority_boost
from f2m_engine.domain.tag_localization import localize_tag


SOFT_NEGATIVE_PENALTY_WEIGHT = 2.5
SOFT_NEGATIVE_CONTENT_KEYS = frozenset({"vegetables", "meat", "fish_seafood", "soup", "spicy", "sweet", "hot", "cold"})


def score_questionnaire_candidates(
    request_id: str,
    user_id: int,
    normalized_profile: dict[str, Any],
    safe_candidates: list[dict[str, Any]],
    request_context: dict[str, Any] | None,
    top_k: int,
    recommendation_settings: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _ = top_k
    context = request_context or {}
    eligible_candidates = [row for row in safe_candidates if _is_recommendable_candidate(row)]
    dishes_by_id = {str(row.get("dish_id", "")): row for row in eligible_candidates}
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

    _neutralize_request_constant_components(scored)
    for row in scored:
        row["active_signal_count"] = int(
            sum(
                1
                for key in (
                    "desired_content_match",
                    "satiety_match",
                    "nutrition_match",
                    "cuisine_match",
                    "familiarity_novelty_match",
                    "temperature_match",
                )
                if float(row.get(key, 0.0)) > 0.000001
            )
        )
    scored.sort(key=_rank_sort_key("final_score_base"))
    seen_signatures: set[str] = set()
    for row in scored:
        signature = _signature_for_diversity(row)
        diversity_bonus = 0.05 if signature not in seen_signatures else 0.0
        seen_signatures.add(signature)
        row["diversity_bonus"] = round(diversity_bonus, 6)
        row["intent_coverage_bonus"] = 0.0
        row["final_score"] = round(float(row["final_score_base"]) + diversity_bonus, 6)

    _apply_intent_coverage_bonus(scored, normalized_profile=normalized_profile, top_k=top_k)
    apply_business_priority_boost(
        rows=scored,
        dishes_by_id=dishes_by_id,
        settings=recommendation_settings,
        score_key="final_score",
    )
    scored.sort(key=_rank_sort_key("final_score"))
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
    temperature_match = _temperature_match(normalized_profile=normalized_profile, dish=dish)
    soft_negative_penalty = _soft_negative_penalty(normalized_profile=normalized_profile, dish=dish)
    soft_negative_hit_keys = _soft_negative_hit_keys(normalized_profile=normalized_profile, dish=dish)
    dietary_penalty = _dietary_soft_penalty(normalized_profile=normalized_profile, dish=dish)
    reason_tags = _build_reason_tags(normalized_profile=normalized_profile, dish=dish)
    warning_tags = _build_warning_tags(normalized_profile=normalized_profile, dish=dish, reason_tags=reason_tags)
    display_tags = _build_display_tags(
        normalized_profile=normalized_profile,
        dish=dish,
        reason_tags=reason_tags,
        warning_tags=warning_tags,
    )
    venue_boost = _venue_boost(request_context=request_context, dish=dish)
    matched_intent_keys = _matched_desired_intent_keys(normalized_profile=normalized_profile, dish=dish)
    final_score_base = (
        desired_content_match
        + satiety_match
        + nutrition_match
        + cuisine_match
        + familiarity_novelty_match
        + temperature_match
        - soft_negative_penalty
        - dietary_penalty
        + venue_boost
    )
    serving_temperature = _serving_temperature(dish)
    return {
        "desired_content_match": round(desired_content_match, 6),
        "satiety_match": round(satiety_match, 6),
        "nutrition_match": round(nutrition_match, 6),
        "cuisine_match": round(cuisine_match, 6),
        "familiarity_novelty_match": round(familiarity_novelty_match, 6),
        "temperature_match": round(temperature_match, 6),
        "soft_negative_penalty": round(soft_negative_penalty, 6),
        "soft_negative_hit_key": soft_negative_hit_keys[0] if soft_negative_hit_keys else "",
        "soft_negative_hit_keys": soft_negative_hit_keys,
        "soft_negative_hit_count": len(soft_negative_hit_keys),
        "soft_negative_rank_group": 1 if soft_negative_hit_keys else 0,
        "dietary_penalty": round(dietary_penalty, 6),
        "reason_tags": reason_tags,
        "warning_tags": warning_tags,
        "display_tags": display_tags,
        "matched_intent_keys": matched_intent_keys,
        "menu_section": "food_recommendations",
        "diversity_bonus": 0.0,
        "intent_coverage_bonus": 0.0,
        "venue_boost": round(venue_boost, 6),
        "sweet_signal": round(_sweet_signal(dish=dish), 6),
        "serving_temperature": serving_temperature,
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
    return 2.0 * points / max(1, len(keys))


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
        return _sweet_signal(dish=dish)
    if key == "hot":
        return 1.0 if _serving_temperature(dish=dish) == "hot" else 0.0
    if key == "cold":
        return 1.0 if _serving_temperature(dish=dish) == "cold" else 0.0
    if key == "vegetables":
        vegetable_tokens = (
            "tomato",
            "cucumber",
            "broccoli",
            "greens",
            "vegetable",
            "cabbage",
            "zucchini",
            "eggplant",
            "pepper",
            "carrot",
            "pumpkin",
            "beet",
            "potato",
            "salad",
        )
        protein_tokens = (
            "beef",
            "lamb",
            "chicken",
            "turkey",
            "pork",
            "bacon",
            "ham",
            "fish",
            "salmon",
            "tuna",
            "shrimp",
            "seafood",
        )
        vegetable_mass = sum(_safe_float(ingredients.get(token, 0.0)) for token in vegetable_tokens)
        protein_mass = sum(_safe_float(ingredients.get(token, 0.0)) for token in protein_tokens)
        if vegetable_mass <= 0.0:
            return 0.0
        if protein_mass <= 0.0:
            return 1.0
        dominance = vegetable_mass / max(0.000001, vegetable_mass + protein_mass)
        return _bounded(dominance)
    if key == "spicy":
        return 1.0 if bool(flags.get("spicy")) else float(taste.get("spicy", 0.0))
    return 0.0


def _satiety_match(normalized_profile: dict[str, Any], dish: dict[str, Any]) -> float:
    satiety = str(normalized_profile.get("request_context", {}).get("satiety", "") or "")
    if not satiety:
        return 0.0
    satiety_class = _effective_satiety_class(dish=dish)
    if not satiety_class:
        return 0.0
    if satiety == satiety_class:
        return 0.7
    neighbor_pairs = {
        ("snack", "light_meal"),
        ("light_meal", "snack"),
        ("light_meal", "full_meal"),
        ("full_meal", "light_meal"),
    }
    if (satiety, satiety_class) in neighbor_pairs:
        return 0.3
    return 0.0


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


def _temperature_match(normalized_profile: dict[str, Any], dish: dict[str, Any]) -> float:
    requested = _requested_temperature(normalized_profile=normalized_profile)
    if requested == "neutral":
        return 0.0
    actual = _serving_temperature(dish=dish)
    if requested == actual:
        return 0.35
    if actual == "neutral":
        return 0.1
    return -0.05


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
    penalty = 0.0
    for key, weight in negatives.items():
        if _soft_negative_hits_dish(dish=dish, key=str(key)):
            penalty += SOFT_NEGATIVE_PENALTY_WEIGHT * max(0.0, float(weight))
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
        "temperature": row.get("temperature_match", 0.0),
    }
    return json.dumps(payload, sort_keys=True)


def _rank_sort_key(score_key: str):
    return lambda row: (
        _soft_negative_rank_group(row),
        -float(row[score_key]),
        -int(row["active_signal_count"]),
        str(row["dish_name"]),
        str(row["dish_id"]),
    )


def _soft_negative_rank_group(row: dict[str, Any]) -> int:
    if int(row.get("soft_negative_hit_count", 0)) > 0:
        return 1
    if float(row.get("soft_negative_penalty", 0.0)) > 0.0:
        return 1
    return 0


def _desired_intent_keys(normalized_profile: dict[str, Any]) -> list[str]:
    desired = normalized_profile.get("soft_preferences", {}).get("desired_content", {}) or {}
    want_now = normalized_profile.get("request_context", {}).get("want_now", []) or []
    keys = {str(key) for key, value in desired.items() if float(value) > 0.0}
    keys.update(str(key) for key in want_now)
    return sorted(key for key in keys if key)


def _matched_desired_intent_keys(normalized_profile: dict[str, Any], dish: dict[str, Any]) -> list[str]:
    matched: list[str] = []
    for key in _desired_intent_keys(normalized_profile):
        if _dish_content_signal(dish=dish, key=key) > 0.25:
            matched.append(key)
    return matched


def _apply_intent_coverage_bonus(
    rows: list[dict[str, Any]],
    normalized_profile: dict[str, Any],
    top_k: int,
) -> None:
    intent_keys = _desired_intent_keys(normalized_profile)
    if len(intent_keys) < 2 or not rows or top_k <= 1:
        return
    top_limit = min(int(top_k), len(rows))
    if top_limit <= 0:
        return

    rows.sort(key=_rank_sort_key("final_score"))
    for _ in intent_keys:
        represented = {
            key
            for row in rows[:top_limit]
            for key in row.get("matched_intent_keys", [])
            if key in intent_keys
        }
        missing = [key for key in intent_keys if key not in represented]
        if not missing:
            return

        threshold = float(rows[top_limit - 1].get("final_score", 0.0))
        promoted = False
        for key in missing:
            candidate = next(
                (
                    row
                    for row in rows[top_limit:]
                    if key in row.get("matched_intent_keys", [])
                ),
                None,
            )
            if candidate is None:
                continue
            gap = max(0.02, threshold - float(candidate.get("final_score", 0.0)) + 0.02)
            bonus = min(0.9, gap)
            candidate["intent_coverage_bonus"] = round(
                float(candidate.get("intent_coverage_bonus", 0.0)) + bonus,
                6,
            )
            candidate["final_score"] = round(float(candidate.get("final_score", 0.0)) + bonus, 6)
            promoted = True
            break
        if not promoted:
            return
        rows.sort(key=_rank_sort_key("final_score"))


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
        "алког",
        "alcohol",
        "beer",
        "wine",
        "whiskey",
        "vodka",
        "tonic",
        "energy",
        "энергет",
        "тоник",
        "вина",
        "пиво",
        "смузи",
        "коктейл",
    )
    banned_categories = ("вода", "вина", "игристые", "пиво", "смузи", "коктейл", "соки", "добавить к заказу")
    if any(bc in category for bc in banned_categories):
        return False
    return not any(token in merged for token in banned_tokens)


def _explain_row(row: dict[str, Any]) -> str:
    parts = []
    for key, label in (
        ("desired_content_match", "desired"),
        ("satiety_match", "satiety"),
        ("nutrition_match", "nutrition"),
        ("cuisine_match", "cuisine"),
        ("familiarity_novelty_match", "novelty"),
        ("temperature_match", "temperature"),
    ):
        value = float(row.get(key, 0.0))
        if abs(value) > 0.000001:
            parts.append(f"{label}={value}")
    parts.append(f"soft_neg=-{row['soft_negative_penalty']}")
    parts.append(f"diversity={row['diversity_bonus']}")
    parts.append(f"intent_coverage={row.get('intent_coverage_bonus', 0.0)}")
    parts.append(f"business_priority={row.get('business_priority_boost', 0.0)}")
    parts.append(f"signals={row.get('active_signal_count', 0)}")
    return " | ".join(parts)


def _dietary_soft_penalty(normalized_profile: dict[str, Any], dish: dict[str, Any]) -> float:
    dietary_rules = set(normalized_profile.get("hard_constraints", {}).get("dietary_rules", []))
    if not dietary_rules:
        return 0.0
    dietary = dish.get("dietary_conflicts", {}) or {}
    penalty = 0.0
    if "vegetarian" in dietary_rules and bool(dietary.get("vegetarian_conflict")):
        penalty += 2.0
    if "vegan" in dietary_rules and bool(dietary.get("vegan_conflict")):
        penalty += 2.0
    if "no_pork" in dietary_rules and bool(dietary.get("no_pork_conflict")):
        penalty += 2.0
    return penalty


def _build_reason_tags(normalized_profile: dict[str, Any], dish: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    dietary_rules = set(normalized_profile.get("hard_constraints", {}).get("dietary_rules", []))
    dietary = dish.get("dietary_conflicts", {}) or {}
    if "vegetarian" in dietary_rules and bool(dietary.get("vegetarian_conflict")):
        tags.append("vegetarian_conflict")
    if "vegan" in dietary_rules and bool(dietary.get("vegan_conflict")):
        tags.append("vegan_conflict")
    if "no_pork" in dietary_rules and bool(dietary.get("no_pork_conflict")):
        tags.append("no_pork_conflict")
    return tags


def _build_warning_tags(
    normalized_profile: dict[str, Any],
    dish: dict[str, Any],
    reason_tags: list[str],
) -> list[str]:
    tags: list[str] = []
    for tag in reason_tags:
        _append_unique(tags, tag)

    flags = dish.get("constraint_flags", {}) or {}
    taste = dish.get("taste_features", {}) or {}
    if bool(flags.get("spicy")) or _safe_float(taste.get("spicy")) >= 0.35:
        _append_unique(tags, "spicy")

    for key in _soft_negative_hit_keys(normalized_profile=normalized_profile, dish=dish):
        _append_unique(tags, key)
    return tags


def _build_display_tags(
    normalized_profile: dict[str, Any],
    dish: dict[str, Any],
    reason_tags: list[str],
    warning_tags: list[str],
) -> list[dict[str, Any]]:
    tags: list[dict[str, Any]] = []

    violation_labels = {
        "vegetarian_conflict": ("restriction", "vegetarian", "Не подходит вегетарианцу"),
        "vegan_conflict": ("restriction", "vegan", "Не подходит вегану"),
        "no_pork_conflict": ("restriction", "pork", "Есть свинина"),
    }
    for reason_tag in reason_tags:
        axis, key, label = violation_labels.get(reason_tag, ("restriction", reason_tag, reason_tag))
        tags.append(_display_tag(axis=axis, key=key, label=label, kind="violation", priority=10))

    if "spicy" in warning_tags:
        tags.append(_display_tag(axis="taste", key="spicy", label="", kind="warning", priority=20))

    nutrition = dish.get("nutrition_features", {}) or {}
    for key in ("low_calorie", "high_protein", "low_fat", "high_carb"):
        if bool(nutrition.get(key)):
            tags.append(_display_tag(axis="nutrition", key=key, label="", kind="nutrition", priority=30))

    cuisine = dish.get("cuisine_features", {}) or {}
    for key, _value in sorted(cuisine.items(), key=lambda item: (-_safe_float(item[1]), str(item[0]))):
        if _safe_float(cuisine.get(key)) <= 0.0:
            continue
        label = localize_tag(axis="cuisine", key=str(key))
        if label != str(key):
            tags.append(_display_tag(axis="cuisine", key=str(key), label=label, kind="cuisine", priority=40))
            break

    satiety_key, satiety_label = _display_satiety(dish=dish)
    if satiety_key:
        tags.append(_display_tag(axis="nutrition", key=satiety_key, label=satiety_label, kind="satiety", priority=50))

    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for tag in sorted(tags, key=lambda item: (int(item["priority"]), str(item["key"]))):
        dedupe_key = (str(tag["kind"]), str(tag["axis"]), str(tag["key"]))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        result.append(tag)
    return filter_supported_display_tags(dish=dish, tags=result)


def _display_tag(axis: str, key: str, label: str, kind: str, priority: int) -> dict[str, Any]:
    return {
        "axis": axis,
        "key": key,
        "label": label or localize_tag(axis=axis, key=key),
        "kind": kind,
        "priority": int(priority),
    }


def _display_satiety(dish: dict[str, Any]) -> tuple[str, str]:
    satiety = _effective_satiety_class(dish=dish)
    if satiety == "full_meal":
        return "hearty", "Сытное"
    if satiety == "light_meal":
        return "light", "Легкое"
    if satiety == "snack":
        return "snack", "Перекус"
    return "", ""


def _soft_negative_hit_keys(normalized_profile: dict[str, Any], dish: dict[str, Any]) -> list[str]:
    negatives = normalized_profile.get("soft_preferences", {}).get("soft_negative_ingredients", {}) or {}
    hits: list[str] = []
    for key in sorted(negatives.keys()):
        normalized_key = "spicy" if key in ("spicy_ingredients", "spicy") else str(key)
        if _soft_negative_hits_dish(dish=dish, key=str(key)):
            _append_unique(hits, normalized_key)
    return hits


def _soft_negative_hits_dish(dish: dict[str, Any], key: str) -> bool:
    normalized_key = "spicy" if key in ("spicy_ingredients", "spicy") else str(key)
    ingredients = dish.get("ingredient_features", {}) or {}
    flags = dish.get("constraint_flags", {}) or {}
    taste = dish.get("taste_features", {}) or {}
    if key in ingredients:
        return True
    if normalized_key in SOFT_NEGATIVE_CONTENT_KEYS and _dish_content_signal(dish=dish, key=normalized_key) > 0.25:
        return True
    if key == "onion" and bool(flags.get("onion")):
        return True
    if key == "mushroom" and bool(flags.get("mushroom")):
        return True
    if normalized_key == "spicy" and (bool(flags.get("spicy")) or _safe_float(taste.get("spicy")) >= 0.35):
        return True
    if key == "offal" and bool(flags.get("offal")):
        return True
    return normalized_key == "fish_seafood" and bool(flags.get("fish_seafood"))


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _norm(value: str) -> str:
    return str(value or "").lower().replace("ё", "е").strip()


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _bounded(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _sweet_signal(dish: dict[str, Any]) -> float:
    taste = dish.get("taste_features", {}) or {}
    ingredients = dish.get("ingredient_features", {}) or {}
    format_texture = dish.get("format_texture_features", {}) or {}
    name = _norm(str(dish.get("dish_name", "")))
    category = _norm(str(dish.get("category", "")))
    taste_sweet = float(taste.get("sweet", 0.0))
    dessert_markers = ("десерт", "чизкейк", "торт", "морож", "пирож", "панкейк", "блин", "круассан", "пончик", "waffle")
    sweet_drink_markers = ("какао", "раф", "латте", "карамел", "молочн коктейл", "hot chocolate", "фраппе")
    savory_markers = ("суп", "борщ", "паста", "стейк", "гриль", "жар", "салат", "поке", "тар-тар", "карпаччо")
    seasoning_like = {"sugar", "honey", "syrup", "vinegar", "salt", "pepper", "soy_sauce", "fish_sauce", "oyster_sauce"}
    has_explicit_dessert = any(marker in name or marker in category for marker in dessert_markers)
    has_explicit_sweet_drink = any(marker in name for marker in sweet_drink_markers)
    savory_protein_tokens = {"beef", "lamb", "chicken", "turkey", "pork", "bacon", "ham",
                             "fish", "salmon", "tuna", "shrimp", "seafood", "cod", "trout", "sea_bass"}
    has_savory_protein = bool(set(ingredients.keys()) & savory_protein_tokens)
    savory_context = (
        bool(format_texture.get("soup", 0.0))
        or bool(format_texture.get("salad", 0.0))
        or has_savory_protein
        or any(marker in name or marker in category for marker in savory_markers)
    )
    if has_explicit_dessert and not savory_context:
        return max(taste_sweet, 0.85)
    if has_explicit_sweet_drink:
        return max(taste_sweet, 0.75)
    non_seasoning_ingredients = [key for key in ingredients if key not in seasoning_like]
    if savory_context:
        return min(0.15, taste_sweet * 0.3)
    if taste_sweet > 0.0 and non_seasoning_ingredients:
        return min(0.7, taste_sweet)
    return min(0.1, taste_sweet * 0.2)


def _requested_temperature(normalized_profile: dict[str, Any]) -> str:
    context = normalized_profile.get("request_context", {}) or {}
    tags = {str(value) for value in context.get("session_tags", [])}
    want = {str(value) for value in context.get("want_now", [])}
    merged = tags | want
    if "hot" in merged:
        return "hot"
    if "cold" in merged:
        return "cold"
    return "neutral"


def _serving_temperature(dish: dict[str, Any]) -> str:
    name = _norm(str(dish.get("dish_name", "")))
    category = _norm(str(dish.get("category", "")))
    format_texture = dish.get("format_texture_features", {}) or {}
    if bool(format_texture.get("soup", 0.0)):
        return "hot"
    if any(float(format_texture.get(key, 0.0)) > 0.0 for key in ("grilled", "fried", "baked")):
        return "hot"
    if bool(format_texture.get("salad", 0.0)):
        return "cold"
    if any(marker in name or marker in category for marker in ("суп", "горяч", "паста", "гриль", "жарен", "запеч")):
        return "hot"
    if any(marker in name or marker in category for marker in ("салат", "поке", "тар-тар", "карпаччо", "холод")):
        return "cold"
    return "neutral"


def _effective_satiety_class(dish: dict[str, Any]) -> str:
    nutrition = dish.get("nutrition_features", {}) or {}
    raw_class = _norm(str(nutrition.get("satiety_class", "")))
    mapping = {
        "snack": "snack",
        "light": "light_meal",
        "light_meal": "light_meal",
        "hearty": "full_meal",
        "full_meal": "full_meal",
    }
    base_class = mapping.get(raw_class, "")
    kcal = _safe_float(nutrition.get("kcal_per_portion"))
    protein = _safe_float(nutrition.get("protein_per_100g"))
    fat = _safe_float(nutrition.get("fat_per_100g"))
    format_texture = dish.get("format_texture_features", {}) or {}
    category = _norm(str(dish.get("category", "")))
    satiety_score = 0.0
    satiety_score += _bounded(kcal / 700.0) * 0.45
    satiety_score += _bounded((protein + fat) / 30.0) * 0.35
    if bool(format_texture.get("soup", 0.0)):
        satiety_score += 0.08
    if any(float(format_texture.get(key, 0.0)) > 0.0 for key in ("grilled", "fried", "baked")):
        satiety_score += 0.12
    if "горяч" in category or "основ" in category or "горячее" in category:
        satiety_score += 0.1
    satiety_score = _bounded(satiety_score)
    proxy = "snack"
    if satiety_score >= 0.55:
        proxy = "full_meal"
    elif satiety_score >= 0.3:
        proxy = "light_meal"
    satiety_order = {"snack": 0, "light_meal": 1, "full_meal": 2}
    if base_class and proxy:
        return base_class if satiety_order[base_class] >= satiety_order[proxy] else proxy
    return base_class or proxy


def _neutralize_request_constant_components(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    component_keys = (
        "desired_content_match",
        "satiety_match",
        "nutrition_match",
        "cuisine_match",
        "familiarity_novelty_match",
        "temperature_match",
        "venue_boost",
    )
    neutralized: set[str] = set()
    for key in component_keys:
        values = [float(row.get(key, 0.0)) for row in rows]
        if not values:
            continue
        if max(values) - min(values) < 0.0001:
            neutralized.add(key)
    for row in rows:
        for key in neutralized:
            row[key] = 0.0
        row["constant_components_neutralized"] = "|".join(sorted(neutralized))
        row["final_score_base"] = round(
            float(row.get("desired_content_match", 0.0))
            + float(row.get("satiety_match", 0.0))
            + float(row.get("nutrition_match", 0.0))
            + float(row.get("cuisine_match", 0.0))
            + float(row.get("familiarity_novelty_match", 0.0))
            + float(row.get("temperature_match", 0.0))
            - float(row.get("soft_negative_penalty", 0.0))
            - float(row.get("dietary_penalty", 0.0))
            + float(row.get("venue_boost", 0.0)),
            6,
        )
