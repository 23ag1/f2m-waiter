from __future__ import annotations

from typing import Any


def filter_supported_display_tags(dish: dict[str, Any], tags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [tag for tag in tags if display_tag_is_supported(dish=dish, tag=tag)]


def display_tag_is_supported(dish: dict[str, Any], tag: dict[str, Any]) -> bool:
    kind = str(tag.get("kind", ""))
    axis = str(tag.get("axis", ""))
    key = str(tag.get("key", ""))
    if kind == "warning" and axis == "taste" and key == "spicy":
        return _spicy_supported(dish)
    if kind == "nutrition":
        nutrition = dish.get("nutrition_features", {}) or dish.get("nutrition", {}) or {}
        return bool(nutrition.get(key))
    if kind == "cuisine":
        cuisine = dish.get("cuisine_features", {}) or dish.get("cuisine", {}) or {}
        return _safe_float(cuisine.get(key)) > 0.0
    if kind == "violation":
        dietary = dish.get("dietary_conflicts", {}) or {}
        return (
            (key == "vegetarian" and bool(dietary.get("vegetarian_conflict")))
            or (key == "vegan" and bool(dietary.get("vegan_conflict")))
            or (key == "pork" and bool(dietary.get("no_pork_conflict")))
        )
    if kind == "satiety":
        return True
    return True


def unsupported_display_tag_keys(dish: dict[str, Any], tags: list[dict[str, Any]]) -> list[str]:
    return [
        f"{tag.get('kind')}:{tag.get('axis')}:{tag.get('key')}"
        for tag in tags
        if not display_tag_is_supported(dish=dish, tag=tag)
    ]


def _spicy_supported(dish: dict[str, Any]) -> bool:
    flags = dish.get("constraint_flags", {}) or dish.get("hard_flags", {}) or {}
    taste = dish.get("taste_features", {}) or dish.get("taste", {}) or {}
    return bool(flags.get("spicy")) or _safe_float(taste.get("spicy")) >= 0.35


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
