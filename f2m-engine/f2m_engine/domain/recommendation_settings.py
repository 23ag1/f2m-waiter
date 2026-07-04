from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from f2m_engine.config.taxonomy import DEFAULT_TAXONOMY_PATH, TaxonomyError, load_runtime_taxonomy


RECOMMENDATION_SETTINGS_FILENAME = "recommendation_settings.json"
RECOMMENDATION_SETTINGS_VERSION = "recommendation_settings_v1"
MANUAL_TAG_AXES = {"taste", "ingredient", "cuisine", "format_texture", "context", "nutrition"}
MANUAL_TAG_ACTIONS = {"add", "remove"}
DEFAULT_PRIORITY_BOOST = 0.12
MAX_PRIORITY_BOOST = 0.5
DEFAULT_PRIORITY_LIMIT = 5

INGREDIENT_ALIASES: dict[str, str] = {
    "chicken": "chicken",
    "poultry": "chicken",
    "\u043a\u0443\u0440\u0438\u0446\u0430": "chicken",
    "\u043a\u0443\u0440\u0438\u043d\u043e\u0435": "chicken",
    "\u043a\u0443\u0440\u0438\u043d\u044b\u0439": "chicken",
    "\u0446\u044b\u043f\u043b\u0435\u043d\u043e\u043a": "chicken",
    "beef": "beef",
    "\u0433\u043e\u0432\u044f\u0434\u0438\u043d\u0430": "beef",
    "\u0433\u043e\u0432\u044f\u0436\u044c\u0435": "beef",
    "pork": "pork",
    "bacon": "bacon",
    "\u0441\u0432\u0438\u043d\u0438\u043d\u0430": "pork",
    "\u0441\u0432\u0438\u043d\u043e\u0435": "pork",
    "\u0431\u0435\u043a\u043e\u043d": "bacon",
    "fish": "fish_seafood",
    "seafood": "fish_seafood",
    "\u0440\u044b\u0431\u0430": "fish_seafood",
    "\u0440\u044b\u0431\u043d\u043e\u0435": "fish_seafood",
    "\u043c\u043e\u0440\u0435\u043f\u0440\u043e\u0434\u0443\u043a\u0442\u044b": "fish_seafood",
    "salmon": "salmon",
    "\u043b\u043e\u0441\u043e\u0441\u044c": "salmon",
    "\u0441\u0435\u043c\u0433\u0430": "salmon",
    "tuna": "tuna",
    "\u0442\u0443\u043d\u0435\u0446": "tuna",
    "shrimp": "shrimp",
    "\u043a\u0440\u0435\u0432\u0435\u0442\u043a\u0430": "shrimp",
    "\u043a\u0440\u0435\u0432\u0435\u0442\u043a\u0438": "shrimp",
    "cheese": "cheese",
    "\u0441\u044b\u0440": "cheese",
    "mushroom": "mushroom",
    "\u0433\u0440\u0438\u0431": "mushroom",
    "\u0433\u0440\u0438\u0431\u044b": "mushroom",
    "tomato": "tomato",
    "\u0442\u043e\u043c\u0430\u0442": "tomato",
    "\u043f\u043e\u043c\u0438\u0434\u043e\u0440": "tomato",
}

ALCOHOL_MARKERS = (
    "alcohol",
    "beer",
    "wine",
    "vodka",
    "whiskey",
    "whisky",
    "rum",
    "gin",
    "tequila",
    "cocktail",
    "liqueur",
    "\u0430\u043b\u043a\u043e\u0433\u043e\u043b",
    "\u0432\u0438\u043d\u043e",
    "\u0432\u0438\u043d\u0430",
    "\u043f\u0438\u0432\u043e",
    "\u0432\u043e\u0434\u043a",
    "\u0440\u043e\u043c",
    "\u0432\u0438\u0441\u043a",
    "\u0434\u0436\u0438\u043d",
    "\u043a\u043e\u043d\u044c\u044f\u043a",
    "\u043a\u043e\u043a\u0442\u0435\u0439\u043b",
)


def default_recommendation_settings() -> dict[str, Any]:
    return {
        "settings_version": RECOMMENDATION_SETTINGS_VERSION,
        "source": "defaults",
        "manual_tag_overrides": [],
        "stop_list_dish_ids": [],
        "priority_dish_ids": [],
        "priority_ingredients": [],
        "priority_boost": DEFAULT_PRIORITY_BOOST,
        "max_priority_boosted_items": DEFAULT_PRIORITY_LIMIT,
        "allow_alcohol": False,
        "business_goals": {
            "sets": [],
            "margin": {},
            "upsells": [],
            "modifiers": [],
        },
        "context_scenarios": {},
        "scenario_config": {},
        "validation_warnings": [],
    }


def load_recommendation_settings(derived_dir: Path | str) -> dict[str, Any]:
    path = Path(derived_dir) / RECOMMENDATION_SETTINGS_FILENAME
    if not path.exists():
        return default_recommendation_settings()
    raw = json.loads(path.read_text(encoding="utf-8"))
    settings = normalize_recommendation_settings(raw)
    settings["source"] = str(path)
    return settings


def normalize_recommendation_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    source = raw or {}
    settings = default_recommendation_settings()
    settings["settings_version"] = str(source.get("settings_version") or RECOMMENDATION_SETTINGS_VERSION)
    settings["manual_tag_overrides"] = _normalize_manual_tag_overrides(source.get("manual_tag_overrides", []))
    settings["stop_list_dish_ids"] = sorted(_normalize_id_set(source.get("stop_list_dish_ids", [])))
    settings["priority_dish_ids"] = sorted(_normalize_id_set(source.get("priority_dish_ids", [])))
    settings["priority_ingredients"] = sorted(
        {
            normalize_ingredient_key(value)
            for value in source.get("priority_ingredients", [])
            if normalize_ingredient_key(value)
        }
    )
    settings["priority_boost"] = _bounded_float(
        source.get("priority_boost", DEFAULT_PRIORITY_BOOST),
        default=DEFAULT_PRIORITY_BOOST,
        minimum=0.0,
        maximum=MAX_PRIORITY_BOOST,
    )
    settings["max_priority_boosted_items"] = max(
        0,
        int(_safe_float(source.get("max_priority_boosted_items", DEFAULT_PRIORITY_LIMIT), DEFAULT_PRIORITY_LIMIT)),
    )
    settings["allow_alcohol"] = _truthy(source.get("allow_alcohol", False))
    settings["business_goals"] = dict(source.get("business_goals") or settings["business_goals"])
    settings["context_scenarios"] = dict(source.get("context_scenarios") or {})
    settings["scenario_config"] = dict(source.get("scenario_config") or {})
    settings["validation_warnings"] = []
    return settings


def load_effective_dish_cache(derived_dir: Path | str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base = Path(derived_dir)
    dish_cache_path = base / "dish_features_cache.json"
    if not dish_cache_path.exists():
        return [], load_recommendation_settings(base)
    dish_cache = json.loads(dish_cache_path.read_text(encoding="utf-8"))
    settings = load_recommendation_settings(base)
    return apply_effective_dish_tags(dish_cache=dish_cache, settings=settings), settings


def apply_effective_dish_tags(
    *,
    dish_cache: list[dict[str, Any]],
    settings: dict[str, Any] | None,
    taxonomy_path: Path | str = DEFAULT_TAXONOMY_PATH,
) -> list[dict[str, Any]]:
    normalized_settings = normalize_recommendation_settings(settings)
    effective = [copy.deepcopy(dish) for dish in dish_cache]
    by_dish_id = {str(dish.get("dish_id")): dish for dish in effective}
    taxonomy = load_runtime_taxonomy(Path(taxonomy_path))
    ingredient_keys = _ingredient_keys_from_cache(effective)

    for override in normalized_settings.get("manual_tag_overrides", []):
        dish = by_dish_id.get(str(override.get("dish_id")))
        if dish is None:
            continue
        axis = str(override.get("axis", ""))
        action = str(override.get("action", ""))
        raw_key = str(override.get("key", ""))
        key = _canonical_tag_key(
            axis=axis,
            key=raw_key,
            taxonomy=taxonomy,
            known_ingredient_keys=ingredient_keys,
        )
        if not key:
            continue
        axis_values = dish.setdefault(axis, {})
        if not isinstance(axis_values, dict):
            continue
        if action == "remove":
            axis_values.pop(key, None)
        elif action == "add":
            axis_values[key] = _bounded_float(override.get("weight", 1.0), default=1.0, minimum=0.0, maximum=1.0)
        meta = dish.setdefault("meta", {})
        applied = meta.setdefault("manual_tag_overrides_applied", [])
        if isinstance(applied, list):
            applied.append(
                {
                    "axis": axis,
                    "key": key,
                    "action": action,
                    "source": str(override.get("source", "admin")),
                }
            )
    return effective


def system_exclusion_reasons_for_dish(
    *,
    dish: dict[str, Any],
    settings: dict[str, Any] | None,
    request_context: dict[str, Any] | None = None,
) -> list[str]:
    normalized_settings = normalize_recommendation_settings(settings)
    reasons: list[str] = []
    if dish_is_stop_listed(dish=dish, settings=normalized_settings):
        reasons.append("system_pos_stop_list")
    if dish_has_alcohol(dish) and not alcohol_is_allowed(settings=normalized_settings, request_context=request_context):
        reasons.append("system_alcohol_without_request")
    return reasons


def dish_is_stop_listed(*, dish: dict[str, Any], settings: dict[str, Any] | None) -> bool:
    normalized_settings = normalize_recommendation_settings(settings)
    dish_id = str(dish.get("dish_id", ""))
    return dish_id in set(normalized_settings.get("stop_list_dish_ids", []))


def dish_has_alcohol(dish: dict[str, Any]) -> bool:
    parts = [
        str(dish.get("dish_id", "")),
        str(dish.get("dish_name", "")),
        str(dish.get("category", "")),
        str(dish.get("venue", "")),
        str(dish.get("meta", {}).get("name", "")),
        str(dish.get("meta", {}).get("category", "")),
    ]
    ingredients = _feature_keys(dish, "ingredient", "ingredient_features")
    hard_flags = dish.get("hard_flags", {}) or dish.get("constraint_flags", {}) or {}
    if bool(hard_flags.get("alcohol")) or "alcohol" in ingredients:
        return True
    merged = _normalize_text(" ".join(parts))
    return any(marker in merged for marker in ALCOHOL_MARKERS)


def alcohol_is_allowed(
    *,
    settings: dict[str, Any] | None,
    request_context: dict[str, Any] | None,
) -> bool:
    normalized_settings = normalize_recommendation_settings(settings)
    if _truthy(normalized_settings.get("allow_alcohol")):
        return True
    context = request_context or {}
    for key in ("allow_alcohol", "alcohol_requested", "explicit_alcohol_request"):
        if _truthy(context.get(key)):
            return True
    merged = _normalize_text(" ".join(str(value) for value in _flatten_values(context)))
    return any(marker in merged for marker in ALCOHOL_MARKERS)


def business_priority_reasons_for_dish(
    *,
    dish: dict[str, Any],
    settings: dict[str, Any] | None,
) -> list[str]:
    normalized_settings = normalize_recommendation_settings(settings)
    dish_id = str(dish.get("dish_id", ""))
    reasons: list[str] = []
    if dish_id in set(normalized_settings.get("priority_dish_ids", [])):
        reasons.append(f"dish:{dish_id}")

    priority_ingredients = set(normalized_settings.get("priority_ingredients", []))
    if priority_ingredients:
        dish_ingredients = {
            normalize_ingredient_key(key)
            for key in _feature_keys(dish, "ingredient", "ingredient_features")
            if normalize_ingredient_key(key)
        }
        for key in sorted(dish_ingredients & priority_ingredients):
            reasons.append(f"ingredient:{key}")
    return reasons


def apply_business_priority_boost(
    *,
    rows: list[dict[str, Any]],
    dishes_by_id: dict[str, dict[str, Any]],
    settings: dict[str, Any] | None,
    score_key: str,
) -> None:
    normalized_settings = normalize_recommendation_settings(settings)
    boost = float(normalized_settings.get("priority_boost", 0.0))
    limit = int(normalized_settings.get("max_priority_boosted_items", 0))
    if boost <= 0.0 or limit <= 0 or not rows:
        for row in rows:
            row.setdefault("business_priority_boost", 0.0)
            row.setdefault("business_priority_reasons", [])
        return

    matches: list[tuple[float, str, dict[str, Any], list[str]]] = []
    for row in rows:
        dish_id = str(row.get("dish_id", ""))
        reasons = business_priority_reasons_for_dish(dish=dishes_by_id.get(dish_id, row), settings=normalized_settings)
        row["business_priority_reasons"] = reasons
        row["business_priority_boost"] = 0.0
        if reasons:
            matches.append((-float(row.get(score_key, 0.0)), dish_id, row, reasons))
    matches.sort(key=lambda item: (item[0], item[1]))
    boosted_ids = {str(row.get("dish_id", "")) for _score, _dish_id, row, _reasons in matches[:limit]}

    for row in rows:
        dish_id = str(row.get("dish_id", ""))
        if dish_id not in boosted_ids:
            if row.get("business_priority_reasons"):
                row["business_priority_skipped_by_limit"] = True
            continue
        row["business_priority_boost"] = round(boost, 6)
        row[score_key] = round(float(row.get(score_key, 0.0)) + boost, 6)


def context_tags_from_settings(
    *,
    settings: dict[str, Any] | None,
    request_context: dict[str, Any] | None,
    taxonomy_path: Path | str = DEFAULT_TAXONOMY_PATH,
) -> list[str]:
    normalized_settings = normalize_recommendation_settings(settings)
    context = request_context or {}
    scenarios = normalized_settings.get("context_scenarios", {}) or {}
    if not isinstance(scenarios, dict):
        return []

    scenario_keys = {
        str(context.get("scenario_id", "")),
        str(context.get("scenario_label", "")),
        str(context.get("occasion", "")),
        str(context.get("participants", "")),
        str(context.get("time_sensitive", "")),
    }
    taxonomy = load_runtime_taxonomy(Path(taxonomy_path))
    tags: set[str] = set()
    for key in scenario_keys:
        if not key or key not in scenarios:
            continue
        scenario = scenarios.get(key) or {}
        for tag in scenario.get("context_tags", []):
            try:
                tags.add(taxonomy.resolve_tag("context", str(tag)))
            except TaxonomyError:
                continue
    return sorted(tags)


def published_questionnaire_step_options(
    *,
    settings: dict[str, Any] | None,
    step_id: str,
    fallback_options: list[dict[str, Any]],
) -> list[dict[str, str]]:
    normalized_settings = normalize_recommendation_settings(settings)
    scenario_config = normalized_settings.get("scenario_config", {}) or {}
    questionnaire = scenario_config.get("questionnaire", {}) if isinstance(scenario_config, dict) else {}
    if not isinstance(questionnaire, dict):
        return _normalize_questionnaire_options(fallback_options)

    published_version = str(questionnaire.get("published_version") or questionnaire.get("active_version") or "")
    versions = questionnaire.get("versions", {}) or {}
    published = versions.get(published_version, {}) if published_version and isinstance(versions, dict) else {}
    if not isinstance(published, dict) or not published:
        published = questionnaire.get("published", {}) if isinstance(questionnaire.get("published", {}), dict) else {}
    if not published:
        published = questionnaire

    options = _step_options_from_questionnaire_config(published=published, step_id=step_id)
    if not options:
        return _normalize_questionnaire_options(fallback_options)
    return _normalize_questionnaire_options(options)


def apply_margin_boost(
    *,
    rows: list[dict[str, Any]],
    dishes_by_id: dict[str, dict[str, Any]],
    settings: dict[str, Any],
    score_key: str,
) -> None:
    goals = settings.get('business_goals') or {}
    margin_cfg = goals.get('margin') or {}
    margin_enabled = _truthy(goals.get('margin_mode')) or (
        isinstance(margin_cfg, dict) and _truthy(margin_cfg.get('enabled'))
    )
    if not margin_enabled:
        for row in rows:
            row.setdefault('margin_boost', 0.0)
        return

    # Build margin map: margin = price - cost_price (only dishes with both values known)
    margin_map: dict[str, float] = {}
    for row in rows:
        dish_id = str(row.get('dish_id', ''))
        meta = (dishes_by_id.get(dish_id) or {}).get('meta', {})
        price = _safe_float(meta.get('price'), 0.0)
        cost_price = _safe_float(meta.get('cost_price'), None)
        if price > 0 and cost_price is not None and cost_price >= 0:
            margin = price - cost_price
            if margin > 0:
                margin_map[dish_id] = margin

    if not margin_map:
        for row in rows:
            row.setdefault('margin_boost', 0.0)
        return

    min_m = min(margin_map.values())
    max_m = max(margin_map.values())
    spread = max_m - min_m or 1.0
    MAX_BOOST = 0.08

    for row in rows:
        dish_id = str(row.get('dish_id', ''))
        margin = margin_map.get(dish_id)
        if margin is None:
            row['margin_boost'] = 0.0
            continue
        boost = round(((margin - min_m) / spread) * MAX_BOOST, 6)
        row['margin_boost'] = boost
        row[score_key] = round(float(row.get(score_key, 0.0)) + boost, 6)


def apply_sets_boost(
    *,
    rows: list[dict[str, Any]],
    dishes_by_id: dict[str, dict[str, Any]],
    settings: dict[str, Any],
    score_key: str,
    request_context: dict[str, Any] | None,
) -> None:
    goals = settings.get('business_goals') or {}
    active_sets = [s for s in (goals.get('sets') or []) if _truthy(s.get('active', True))]

    for row in rows:
        row.setdefault('sets_boost', 0.0)
        row.setdefault('sets_boost_reasons', [])

    if not active_sets:
        return

    context = request_context or {}
    raw = context.get('basket_categories') or []
    if isinstance(raw, str):
        raw = [c.strip() for c in raw.split(',') if c.strip()]
    basket_cats = {str(c).strip() for c in raw}

    SET_BOOST = 0.10

    for row in rows:
        dish_id = str(row.get('dish_id', ''))
        dish = dishes_by_id.get(dish_id) or {}
        dish_cat = str(dish.get('meta', {}).get('category', '')).strip()
        if not dish_cat:
            continue

        total = 0.0
        reasons: list[str] = []
        for s in active_sets:
            cats = [str(c).strip() for c in (s.get('categories') or []) if str(c).strip()]
            if not cats:
                continue
            missing = [c for c in cats if c not in basket_cats]
            if not missing:
                continue
            if dish_cat in missing:
                total += SET_BOOST
                reasons.append('set:' + str(s.get('id') or s.get('name') or ''))

        row['sets_boost'] = round(total, 6)
        row['sets_boost_reasons'] = reasons
        if total > 0:
            row[score_key] = round(float(row.get(score_key, 0.0)) + total, 6)



def _normalize_manual_tag_overrides(raw_rows: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_rows, list):
        return []
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        dish_id = str(raw.get("dish_id", "")).strip()
        action = str(raw.get("action", "")).strip().lower()
        axis = str(raw.get("axis", "")).strip()
        key = str(raw.get("key", "")).strip()
        if not dish_id or action not in MANUAL_TAG_ACTIONS or axis not in MANUAL_TAG_AXES or not key:
            continue
        rows.append(
            {
                "dish_id": dish_id,
                "action": action,
                "axis": axis,
                "key": key,
                "weight": _bounded_float(raw.get("weight", 1.0), default=1.0, minimum=0.0, maximum=1.0),
                "source": str(raw.get("source", "admin")),
            }
        )
    return rows


def _step_options_from_questionnaire_config(*, published: dict[str, Any], step_id: str) -> list[dict[str, Any]]:
    direct_key_candidates = (step_id, f"{step_id}_options", "food_options")
    for key in direct_key_candidates:
        value = published.get(key)
        if isinstance(value, list):
            return value

    steps = published.get("steps", [])
    if not isinstance(steps, list):
        return []
    aliases = {
        step_id,
        "want_now" if step_id == "food_desires" else step_id,
        "food_desires" if step_id == "want_now" else step_id,
    }
    for step in steps:
        if not isinstance(step, dict):
            continue
        if str(step.get("id", "")) not in aliases:
            continue
        options = step.get("options", [])
        return options if isinstance(options, list) else []
    return []


def _normalize_questionnaire_options(raw_options: list[dict[str, Any]]) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for raw in raw_options:
        if not isinstance(raw, dict):
            continue
        option_id = str(raw.get("id", "")).strip()
        label = str(raw.get("label", "")).strip()
        if not option_id or not label:
            continue
        options.append({"id": option_id, "label": label})
    return options


def _canonical_tag_key(
    *,
    axis: str,
    key: str,
    taxonomy: Any,
    known_ingredient_keys: set[str],
) -> str:
    if axis == "ingredient":
        normalized = normalize_ingredient_key(key)
        if not known_ingredient_keys:
            return normalized
        return normalized if normalized in known_ingredient_keys or normalized in set(INGREDIENT_ALIASES.values()) else ""
    try:
        return taxonomy.resolve_tag(axis=axis, tag=key)
    except TaxonomyError:
        return ""


def normalize_ingredient_key(value: Any) -> str:
    normalized = _normalize_text(str(value or ""))
    normalized = re.sub(r"[\s\-]+", "_", normalized)
    normalized = re.sub(r"[^0-9a-z_\u0400-\u04ff]+", "", normalized)
    return INGREDIENT_ALIASES.get(normalized, normalized)


def _feature_keys(dish: dict[str, Any], *axis_names: str) -> set[str]:
    result: set[str] = set()
    for axis_name in axis_names:
        values = dish.get(axis_name, {}) or {}
        if isinstance(values, dict):
            result.update(str(key) for key, value in values.items() if _safe_float(value, 0.0) > 0.0 or value is True)
    return result


def _ingredient_keys_from_cache(dishes: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for dish in dishes:
        keys.update(normalize_ingredient_key(key) for key in _feature_keys(dish, "ingredient", "ingredient_features"))
    keys.update(INGREDIENT_ALIASES.values())
    return {key for key in keys if key}


def _normalize_id_set(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {str(value).strip() for value in values if str(value).strip()}


def _flatten_values(value: Any) -> list[Any]:
    if isinstance(value, dict):
        result: list[Any] = []
        for nested in value.values():
            result.extend(_flatten_values(nested))
        return result
    if isinstance(value, (list, tuple, set)):
        result = []
        for nested in value:
            result.extend(_flatten_values(nested))
        return result
    return [value]


def _normalize_text(value: str) -> str:
    return str(value or "").lower().replace("\u0451", "\u0435").strip()


def _bounded_float(value: Any, *, default: float, minimum: float, maximum: float) -> float:
    return round(max(minimum, min(maximum, _safe_float(value, default))), 6)


def _safe_float(value: Any, default: float | None = 0.0) -> float | None:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "allow", "allowed"}
