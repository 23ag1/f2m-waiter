from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from f2m_engine.domain.recommendation_settings import (
    dish_has_alcohol,
    dish_is_stop_listed,
    load_effective_dish_cache,
)


SUPPORTED_HARD_KEYS = (
    "gluten",
    "lactose",
    "nuts",
    "peanut",
    "egg",
    "soy",
    "fish_seafood",
    "mushroom",
    "onion",
    "pork",
    "offal",
    "spicy",
)


@dataclass(frozen=True)
class HardFilterResult:
    request_id: str
    venue: str
    candidate_count_before: int
    candidate_count_after: int
    blocked_count: int
    safe_dishes: list[dict[str, Any]]
    blocked_rows: list[dict[str, Any]]
    filter_decision_rows: list[dict[str, Any]]
    blocked_reasons_summary: dict[str, int]
    zero_safe_candidates_flag: bool


def build_dish_constraints(derived_dir: Path | str) -> list[dict[str, Any]]:
    base = Path(derived_dir)
    dish_cache_path = base / "dish_features_cache.json"
    if not dish_cache_path.exists():
        return []
    dishes, recommendation_settings = load_effective_dish_cache(base)
    constraints: list[dict[str, Any]] = []
    for dish in dishes:
        constraints.append(_build_single_dish_constraints(dish, recommendation_settings=recommendation_settings))
    _write_dish_constraints_csv(base, constraints)
    _write_dish_constraints_extraction_audit(base, constraints)
    return constraints


def select_prefilter_candidates(
    dish_constraints: list[dict[str, Any]],
    venue: str,
) -> list[dict[str, Any]]:
    venue_filtered = _filter_dishes_by_venue(dish_constraints, venue=venue)
    return [row for row in venue_filtered if _is_recommendable_candidate(row)]


def apply_questionnaire_hard_filter(
    request_id: str,
    venue: str,
    normalized_profile: dict[str, Any],
    dish_constraints: list[dict[str, Any]],
) -> HardFilterResult:
    prefilter_candidates = select_prefilter_candidates(dish_constraints=dish_constraints, venue=venue)
    before_count = len(prefilter_candidates)
    blocked_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    safe_dishes: list[dict[str, Any]] = []
    reason_counts: dict[str, int] = {}
    relevant_hard_keys = _collect_relevant_hard_keys(normalized_profile)
    relevant_dietary = set(normalized_profile.get("hard_constraints", {}).get("dietary_rules", []))
    for dish in prefilter_candidates:
        blocked_reason = _evaluate_dish_block_reason(dish=dish, relevant_hard_keys=relevant_hard_keys, dietary_rules=relevant_dietary)
        if blocked_reason is None:
            safe_dishes.append(dish)
            decision_rows.append(
                {
                    "request_id": request_id,
                    "dish_id": str(dish.get("dish_id", "")),
                    "dish_name": str(dish.get("dish_name", "")),
                    "hard_filter_pass": True,
                    "blocked_reasons": [],
                    "blocked_reason_type": "",
                    "parse_confidence": float(dish.get("parse_confidence", 0.0)),
                    "review_required": bool(dish.get("review_required", False)),
                    "survived": True,
                }
            )
            continue
        blocked_rows.append(
            {
                "request_id": request_id,
                "dish_id": str(dish.get("dish_id", "")),
                "dish_name": str(dish.get("dish_name", "")),
                "blocked_reason_key": blocked_reason["key"],
                "blocked_reason_type": blocked_reason["type"],
                "source_evidence": blocked_reason["source_evidence"],
            }
        )
        decision_rows.append(
            {
                "request_id": request_id,
                "dish_id": str(dish.get("dish_id", "")),
                "dish_name": str(dish.get("dish_name", "")),
                "hard_filter_pass": False,
                "blocked_reasons": [blocked_reason["key"]],
                "blocked_reason_type": blocked_reason["type"],
                "parse_confidence": float(dish.get("parse_confidence", 0.0)),
                "review_required": bool(dish.get("review_required", False)),
                "survived": False,
            }
        )
        reason_counts[blocked_reason["key"]] = reason_counts.get(blocked_reason["key"], 0) + 1
    after_count = len(safe_dishes)
    return HardFilterResult(
        request_id=request_id,
        venue=venue,
        candidate_count_before=before_count,
        candidate_count_after=after_count,
        blocked_count=len(blocked_rows),
        safe_dishes=safe_dishes,
        blocked_rows=blocked_rows,
        filter_decision_rows=decision_rows,
        blocked_reasons_summary=dict(sorted(reason_counts.items())),
        zero_safe_candidates_flag=(after_count == 0),
    )


def evaluate_questionnaire_block_reason(
    dish: dict[str, Any],
    normalized_profile: dict[str, Any],
) -> dict[str, str] | None:
    return _evaluate_dish_block_reason(
        dish=dish,
        relevant_hard_keys=_collect_relevant_hard_keys(normalized_profile),
        dietary_rules=set(normalized_profile.get("hard_constraints", {}).get("dietary_rules", [])),
    )


def write_questionnaire_filter_runtime_artifacts(
    derived_dir: Path | str,
    result: HardFilterResult,
) -> None:
    base = Path(derived_dir)
    audit_dir = base / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    trace_path = audit_dir / "questionnaire_candidate_filter_trace.csv"
    blocked_path = audit_dir / "questionnaire_blocked_dishes_sample.csv"
    _append_trace_row(
        path=trace_path,
        headers=[
            "request_id",
            "venue",
            "candidate_count_before",
            "candidate_count_after",
            "blocked_count",
            "zero_safe_candidates_flag",
        ],
        row=[
            result.request_id,
            result.venue,
            result.candidate_count_before,
            result.candidate_count_after,
            result.blocked_count,
            result.zero_safe_candidates_flag,
        ],
    )
    _append_rows(
        path=blocked_path,
        headers=[
            "request_id",
            "dish_id",
            "dish_name",
            "blocked_reason_key",
            "blocked_reason_type",
            "source_evidence",
        ],
        rows=[
            [
                row["request_id"],
                row["dish_id"],
                row["dish_name"],
                row["blocked_reason_key"],
                row["blocked_reason_type"],
                row["source_evidence"],
            ]
            for row in result.blocked_rows[:200]
        ],
    )


def _build_single_dish_constraints(
    dish: dict[str, Any],
    recommendation_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dish_id = str(dish.get("dish_id", ""))
    dish_name = str(dish.get("meta", {}).get("name", ""))
    name_norm = _norm(dish_name)
    ingredients = set(str(key) for key in (dish.get("ingredient", {}) or {}).keys())
    hard_flags = dish.get("hard_flags", {}) or {}
    source_fields_used: list[str] = []
    if ingredients:
        source_fields_used.append("ingredient")
    if hard_flags:
        source_fields_used.append("hard_flags")
    if dish_name:
        source_fields_used.append("dish_name")

    contains_gluten = _flag_any(ingredients, hard_flags, "gluten", {"wheat", "noodles", "pasta"}, name_norm, ("паста", "лапша", "тесто", "булочк", "хлеб", "тортилья", "лаваш", "бургер", "сэндвич", "панини", "чиабатт", "панировк", "gluten"))
    contains_lactose = _flag_any(ingredients, hard_flags, "lactose", {"milk", "cream", "cheese", "butter"}, name_norm, ("сыр", "сливоч", "молоч", "сметан", "йогурт"))
    contains_nuts = _flag_any(ingredients, hard_flags, "nuts", {"nuts", "almond", "cashew", "walnut", "pistachio"}, name_norm, ("орех",))
    contains_peanut = _flag_any(ingredients, hard_flags, "peanut", {"peanut"}, name_norm, ("арахис",))
    contains_egg = _flag_any(ingredients, hard_flags, "egg", {"egg"}, name_norm, ("яйц",))
    contains_soy = _flag_any(ingredients, hard_flags, "soy", {"soy", "soy_sauce", "teriyaki", "tofu"}, name_norm, ("соев", "тофу", "терияк"))
    contains_fish_seafood = _flag_any(
        ingredients,
        hard_flags,
        "fish_seafood",
        {
            "salmon", "tuna", "shrimp", "fish", "seafood", "fish_sauce", "oyster_sauce",
            "crab", "mussel", "squid", "cod", "sea_bass", "trout", "mackerel",
            "herring", "anchovy", "carp", "fish_roe", "nori",
        },
        name_norm,
        ("рыб", "морепроду", "кревет", "лосос", "тунц", "семг", "форел", "горбуш",
         "краб", "мидии", "кальмар", "треск", "дорадо", "сибас", "скумбр", "сельд",
         "анчоус", "икра", "онигири", "поке", "суши", "ролл", "сашими"),
    )
    contains_mushroom = _flag_contains(ingredients, {"mushroom"}) or ("гриб" in name_norm)
    contains_onion = _flag_contains(ingredients, {"onion"}) or ("лук" in name_norm)
    _padded = " " + name_norm + " "
    _contains_salo = " сало " in _padded or " сала " in _padded or " салом " in _padded
    contains_pork = _flag_any(ingredients, hard_flags, "pork", {"pork", "bacon", "ham"}, name_norm, ("свинин", "свиной", "свиных", "бекон", "буженин", "карбонад")) or _contains_salo
    contains_offal = _flag_contains(ingredients, {"offal", "liver", "tongue", "kidney", "heart"}) or any(
        token in name_norm for token in ("печен", "язык", "почки", "сердц", "субпроду")
    )
    contains_spicy = _flag_contains(ingredients, {"chili", "curry", "pepper"}) or any(
        token in name_norm for token in ("остр", "кимчи", "чили", "аджик", "харисс", "пикант")
    )
    contains_alcohol_sauce = any(token in name_norm for token in ("вино", "wine", "beer", "ром", "whiskey", "коньяк", "алкогол"))

    contains_meat_or_poultry = _contains_meat_or_poultry(ingredients=ingredients, name_norm=name_norm)
    vegetarian_conflict = any(
        [
            contains_fish_seafood,
            contains_pork,
            contains_offal,
            contains_meat_or_poultry,
        ]
    )
    vegan_conflict = vegetarian_conflict or contains_lactose or contains_egg
    no_pork_conflict = contains_pork
    halal_like_conflict = contains_pork or contains_offal or contains_alcohol_sauce

    unresolved_constraint_keys = sorted(_detect_unresolved_keys(ingredients=ingredients, hard_flags=hard_flags))
    parse_confidence = _parse_confidence(ingredients=ingredients, unresolved_constraint_keys=unresolved_constraint_keys)
    review_required = bool(unresolved_constraint_keys) or parse_confidence < 0.75
    return {
        "dish_id": dish_id,
        "dish_name": dish_name,
        "venue": str(dish.get("meta", {}).get("restaurant", "") or ""),
        "category": str(dish.get("meta", {}).get("category", "") or ""),
        "ingredient_features": dict(dish.get("ingredient", {}) or {}),
        "cuisine_features": dict(dish.get("cuisine", {}) or {}),
        "nutrition_features": dict(dish.get("nutrition", {}) or {}),
        "format_texture_features": dict(dish.get("format_texture", {}) or {}),
        "context_features": dict(dish.get("context", {}) or {}),
        "taste_features": dict(dish.get("taste", {}) or {}),
        "constraint_flags": {
            "gluten": contains_gluten,
            "lactose": contains_lactose,
            "nuts": contains_nuts,
            "peanut": contains_peanut,
            "egg": contains_egg,
            "soy": contains_soy,
            "fish_seafood": contains_fish_seafood,
            "mushroom": contains_mushroom,
            "onion": contains_onion,
            "pork": contains_pork,
            "offal": contains_offal,
            "spicy": contains_spicy,
        },
        "dietary_conflicts": {
            "vegetarian_conflict": vegetarian_conflict,
            "vegan_conflict": vegan_conflict,
            "no_pork_conflict": no_pork_conflict,
            "halal_like_conflict": halal_like_conflict,
        },
        "system_flags": {
            "pos_stop_list": dish_is_stop_listed(dish=dish, settings=recommendation_settings),
            "alcohol_detected": dish_has_alcohol(dish),
        },
        "parse_confidence": parse_confidence,
        "review_required": review_required,
        "source_fields_used": sorted(source_fields_used),
        "unresolved_constraint_keys": unresolved_constraint_keys,
    }


def _evaluate_dish_block_reason(
    dish: dict[str, Any],
    relevant_hard_keys: set[str],
    dietary_rules: set[str],
) -> dict[str, str] | None:
    system_flags = dish.get("system_flags", {}) or {}
    if bool(system_flags.get("pos_stop_list", False)):
        return {
            "key": "system_pos_stop_list",
            "type": "system_hard_rule",
            "source_evidence": "recommendation_settings",
        }

    flags = dish.get("constraint_flags", {})
    dietary = dish.get("dietary_conflicts", {})
    unresolved = set(dish.get("unresolved_constraint_keys", []))
    review_required = bool(dish.get("review_required", False))
    parse_confidence = float(dish.get("parse_confidence", 0.0))

    for key in sorted(relevant_hard_keys):
        flag_key = "spicy" if key == "spicy_ingredients" else key
        if bool(flags.get(flag_key, False)):
            return {
                "key": f"hard_{flag_key}",
                "type": "explicit_conflict",
                "source_evidence": "constraint_flags",
            }
        if flag_key in unresolved or parse_confidence < 0.75:
            return {
                "key": f"hard_{flag_key}_unknown",
                "type": "unresolved",
                "source_evidence": "unresolved_constraint_keys_or_low_confidence",
            }
        if review_required:
            return {
                "key": f"hard_{flag_key}_review_required",
                "type": "review_required",
                "source_evidence": "review_required",
            }

    if "halal_like" in dietary_rules:
        if bool(dietary.get("halal_like_conflict", False)):
            return {"key": "hard_halal_like_conflict", "type": "explicit_conflict", "source_evidence": "dietary_conflicts"}
        if any(key in unresolved for key in ("pork", "offal", "alcohol")) or review_required:
            return {"key": "hard_halal_like_unknown", "type": "unresolved", "source_evidence": "review_required_or_unresolved"}

    return None


def _collect_relevant_hard_keys(normalized_profile: dict[str, Any]) -> set[str]:
    hard = normalized_profile.get("hard_constraints", {})
    keys: set[str] = set()
    keys.update(str(value) for value in hard.get("allergens", []))
    keys.update(str(value) for value in hard.get("intolerances", []))
    keys.update(str(value) for value in hard.get("ingredient_excludes", []))
    return keys


def _filter_dishes_by_venue(dishes: list[dict[str, Any]], venue: str) -> list[dict[str, Any]]:
    venue_norm = _norm(venue)
    if not venue_norm:
        return sorted(dishes, key=lambda row: (str(row.get("dish_id", "")), str(row.get("dish_name", ""))))
    result = [row for row in dishes if venue_norm in _norm(str(row.get("venue", "")))]
    if result:
        return sorted(result, key=lambda row: (str(row.get("dish_id", "")), str(row.get("dish_name", ""))))
    return sorted(dishes, key=lambda row: (str(row.get("dish_id", "")), str(row.get("dish_name", ""))))


def _detect_unresolved_keys(ingredients: set[str], hard_flags: dict[str, Any]) -> set[str]:
    unresolved: set[str] = set()
    if ingredients:
        return unresolved
    for key in SUPPORTED_HARD_KEYS:
        if key not in hard_flags:
            unresolved.add(key)
    unresolved.update({"vegetarian_conflict", "vegan_conflict", "no_pork_conflict", "halal_like_conflict", "alcohol"})
    return unresolved


def _parse_confidence(ingredients: set[str], unresolved_constraint_keys: list[str]) -> float:
    if ingredients:
        if unresolved_constraint_keys:
            return 0.8
        return 0.95
    if unresolved_constraint_keys:
        return 0.35
    return 0.6


def _flag_any(
    ingredients: set[str],
    hard_flags: dict[str, Any],
    hard_flag_key: str,
    ingredient_markers: set[str],
    name_norm: str,
    text_markers: tuple[str, ...],
) -> bool:
    text_hit = any(marker in name_norm for marker in text_markers)
    if hard_flag_key == "gluten":
        text_hit = text_hit or any(token in name_norm for token in ("хлеб", "bread", "булоч", "гренк", "круассан", "тост"))
    return bool(_flag_contains(ingredients, ingredient_markers) or bool(hard_flags.get(hard_flag_key, False)) or text_hit)


def _flag_contains(ingredients: set[str], markers: set[str]) -> bool:
    return bool(ingredients & markers)


def _contains_meat_or_poultry(ingredients: set[str], name_norm: str) -> bool:
    meat_ingredient_markers = {
        "beef", "veal", "lamb", "mutton", "chicken", "turkey",
        "duck", "goose", "ham", "bacon", "sausage", "meat", "minced_meat",
    }
    if _flag_contains(ingredients, meat_ingredient_markers):
        return True
    meat_name_markers = (
        "говя", "говяжи", "ростбиф", "теля", "баран", "ягнен",
        "куриц", "курин", "куриной", "куриных", "цыплен", "цыплён",
        "индейк", "утк", "гус",
        "колбас", "сосиск", "ветчин", "бекон",
        "свиной", "свиных", "свинин", "буженин", "карбонад",
        "мяс", "фарш", "котлет", "шницел", "стейк",
    )
    if any(token in name_norm for token in meat_name_markers):
        return True
    _padded = " " + name_norm + " "
    return " сало " in _padded or " сала " in _padded or " салом " in _padded


def _write_dish_constraints_csv(base: Path, constraints: list[dict[str, Any]]) -> None:
    path = base / "dish_constraints.csv"
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(
            [
                "dish_id",
                "dish_name",
                "contains_gluten",
                "contains_lactose",
                "contains_nuts",
                "contains_peanut",
                "contains_egg",
                "contains_soy",
                "contains_fish_seafood",
                "contains_mushroom",
                "contains_onion",
                "contains_pork",
                "contains_offal",
                "contains_spicy",
                "vegetarian_conflict",
                "vegan_conflict",
                "no_pork_conflict",
                "halal_like_conflict",
                "parse_confidence",
                "review_required",
            ]
        )
        for row in constraints:
            flags = row["constraint_flags"]
            dietary = row["dietary_conflicts"]
            writer.writerow(
                [
                    row["dish_id"],
                    row["dish_name"],
                    flags["gluten"],
                    flags["lactose"],
                    flags["nuts"],
                    flags["peanut"],
                    flags["egg"],
                    flags["soy"],
                    flags["fish_seafood"],
                    flags["mushroom"],
                    flags["onion"],
                    flags["pork"],
                    flags["offal"],
                    flags["spicy"],
                    dietary["vegetarian_conflict"],
                    dietary["vegan_conflict"],
                    dietary["no_pork_conflict"],
                    dietary["halal_like_conflict"],
                    row["parse_confidence"],
                    row["review_required"],
                ]
            )


def _write_dish_constraints_extraction_audit(base: Path, constraints: list[dict[str, Any]]) -> None:
    path = base / "dish_constraints_extraction_audit.csv"
    total = len(constraints)
    missing_sources = len([row for row in constraints if "ingredient" not in row.get("source_fields_used", [])])
    review_required = len([row for row in constraints if bool(row.get("review_required", False))])
    unresolved_total = sum(len(row.get("unresolved_constraint_keys", [])) for row in constraints)
    rows = [
        ["metric", "value"],
        ["dishes_total", total],
        ["dishes_missing_composition_source", missing_sources],
        ["review_required_true", review_required],
        ["unresolved_hard_keys_total", unresolved_total],
        ["source_coverage_ratio", round((total - missing_sources) / max(1, total), 6)],
    ]
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        for row in rows:
            writer.writerow(row)


def _append_trace_row(path: Path, headers: list[str], row: list[Any]) -> None:
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        if not exists:
            writer.writerow(headers)
        writer.writerow(row)


def _append_rows(path: Path, headers: list[str], rows: list[list[Any]]) -> None:
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        if not exists:
            writer.writerow(headers)
        for row in rows:
            writer.writerow(row)


def _norm(value: str) -> str:
    return str(value or "").lower().replace("ё", "е").strip()


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
    )
    return not any(token in merged for token in banned_tokens)
