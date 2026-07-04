from __future__ import annotations

import csv
import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from f2m_engine.pipelines.recommendation_dataset import log_recommendation_request


AXES = ("taste", "ingredient", "cuisine", "format_texture", "context")
AXIS_WEIGHTS = {
    "taste": 0.22,
    "ingredient": 0.26,
    "cuisine": 0.2,
    "format_texture": 0.17,
    "context": 0.15,
}
STRICT_ALLERGY_CONSTRAINTS = {"peanut", "lactose", "egg", "soy", "fish_seafood"}
MAMMALIAN_RED_MEAT_INGREDIENTS = {"beef", "pork", "lamb", "bacon", "veal"}
MAMMALIAN_BROTH_MARKERS = ("бульон", "broth", "stock")
VEGAN_FORBIDDEN_INGREDIENTS = {
    "beef",
    "pork",
    "lamb",
    "bacon",
    "chicken",
    "turkey",
    "fish_sauce",
    "oyster_sauce",
    "salmon",
    "tuna",
    "shrimp",
    "cheese",
    "milk",
    "cream",
    "butter",
    "egg",
    "honey",
}
HALAL_FORBIDDEN_INGREDIENTS = {"pork", "bacon", "offal", "liver", "tongue"}
HALAL_ALCOHOL_MARKERS = ("вино", "wine", "beer", "rum", "whiskey", "коньяк", "alcohol")


@dataclass(frozen=True)
class ScoringStats:
    user_id: int
    request_id: str
    survivors: int
    excluded: int
    top_k: int


def score_dishes_for_user(
    derived_dir: Path | str,
    user_id: int,
    top_k: int = 10,
    request_context: dict[str, str] | None = None,
) -> ScoringStats:
    base = Path(derived_dir)
    audit_dir = base / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    user_profiles = json.loads((base / "user_profiles_cache.json").read_text(encoding="utf-8"))
    user_feature_rows = _read_jsonl(base / "user_feature_values.jsonl")
    dish_feature_rows = _read_jsonl(base / "dish_feature_values.jsonl")
    dish_cache = json.loads((base / "dish_features_cache.json").read_text(encoding="utf-8"))
    constraints_rows = _read_jsonl(base / "user_constraints.jsonl")
    events_rows = _read_jsonl(base / "events.jsonl")
    taxonomy = json.loads((Path("docs/runtime_taxonomy_resolved_v1.json")).read_text(encoding="utf-8"))
    _ = taxonomy["version"]

    profile = next((row for row in user_profiles if int(row["user_id"]) == int(user_id)), None)
    if profile is None:
        raise ValueError(f"user_id={user_id} not found in user_profiles_cache")
    profile_from_rows = _profile_from_rows(user_feature_rows=user_feature_rows, user_id=user_id)
    if any(profile_from_rows[layer] for layer in ("explicit", "long_term", "short_term")):
        profile = {
            **profile,
            "explicit": profile_from_rows["explicit"],
            "long_term": profile_from_rows["long_term"],
            "short_term": profile_from_rows["short_term"],
        }
    dish_ingredient_evidence = _dish_ingredient_evidence_from_rows(dish_feature_rows)

    constraints = sorted(
        {
            row["constraint_key"]
            for row in constraints_rows
            if int(row["user_id"]) == int(user_id) and row.get("scope") == "hard"
        }
    )
    recent_counts = _build_recent_repeat_counts(events_rows, user_id=user_id)
    request_tags = _context_tags_from_request(request_context or {})
    if not request_tags:
        request_tags = sorted(
            [
                tag
                for tag, value in profile.get("short_term", {}).get("context", {}).items()
                if float(value) > 0
            ]
        )[:4]

    survivors: list[dict[str, Any]] = []
    constraint_audit_rows: list[list[Any]] = []
    hard_filter_status_by_dish: dict[str, dict[str, Any]] = {}
    for dish in sorted(dish_cache, key=lambda x: _dish_sort_key(x.get("dish_id"))):
        dish_id = str(dish.get("dish_id"))
        excluded, reasons, compliance_unknown = _apply_hard_filters(
            constraints=constraints,
            dish=dish,
            ingredient_evidence=dish_ingredient_evidence.get(dish_id, set()),
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
            recent_repeat_count=recent_counts.get(str(dish.get("dish_id")), 0),
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

    survivors.sort(key=lambda row: (-float(row["score"]), _dish_sort_key(row["dish_id"])))
    shown_candidates = survivors[:top_k]
    user_profile_snapshot_id = hashlib.sha256(
        json.dumps(profile, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    request_id = log_recommendation_request(
        derived_dir=base,
        user_id=user_id,
        context_snapshot={"request_context_tags": request_tags, "raw_request_context": request_context or {}},
        user_profile_snapshot_id=user_profile_snapshot_id,
        profile_version=profile.get("meta", {}).get("feature_version", "runtime_v1"),
        shown_candidates=shown_candidates,
        hard_filter_status_by_dish=hard_filter_status_by_dish,
    )
    for row in survivors:
        row["recommendation_request_id"] = request_id
    _write_outputs(
        base=base,
        audit_dir=audit_dir,
        scored_rows=survivors,
        top_k=top_k,
        constraint_audit_rows=constraint_audit_rows,
    )
    return ScoringStats(
        user_id=user_id,
        request_id=request_id,
        survivors=len(survivors),
        excluded=len(constraint_audit_rows) - len(survivors),
        top_k=top_k,
    )


def explain_dish_for_user(
    derived_dir: Path | str,
    user_id: int,
    dish_id: str,
    request_context: dict[str, str] | None = None,
) -> str:
    base = Path(derived_dir)
    scores = _read_jsonl(base / "recommendation_scores.jsonl")
    row = next((item for item in scores if int(item["user_id"]) == int(user_id) and str(item["dish_id"]) == str(dish_id)), None)
    if row is None:
        # Recompute one pass if scores file missing this dish.
        score_dishes_for_user(derived_dir=base, user_id=user_id, top_k=50, request_context=request_context)
        scores = _read_jsonl(base / "recommendation_scores.jsonl")
        row = next((item for item in scores if int(item["user_id"]) == int(user_id) and str(item["dish_id"]) == str(dish_id)), None)
        if row is None:
            return f"dish_id={dish_id} not available for user_id={user_id}"
    lines = [
        f"user_id={user_id}",
        f"dish_id={dish_id}",
        f"dish_name={row['dish_name']}",
        f"score={row['score']}",
        f"user_explanation={row['user_explanation']}",
        f"debug_explanation={row['debug_explanation']}",
    ]
    return "\n".join(lines)


def _score_single_dish(
    profile: dict[str, Any],
    dish: dict[str, Any],
    request_tags: list[str],
    recent_repeat_count: int,
) -> dict[str, Any]:
    explicit_pos, explicit_neg = _layer_match(profile.get("explicit", {}), dish)
    long_pos, long_neg = _layer_match(profile.get("long_term", {}), dish)
    short_pos, short_neg = _layer_match(profile.get("short_term", {}), dish)

    explicit_match = explicit_pos
    explicit_negative_penalty = explicit_neg
    long_term_match = long_pos - (0.35 * long_neg)
    short_term_match = short_pos - (0.25 * short_neg)
    context_match = _request_context_match(request_tags=request_tags, dish=dish)
    novelty_bonus = 0.06 if recent_repeat_count == 0 else 0.0
    recent_repeat_penalty = 0.15 * recent_repeat_count

    score = (
        explicit_match
        + long_term_match
        + short_term_match
        + context_match
        + novelty_bonus
        - explicit_negative_penalty
        - recent_repeat_penalty
    )
    positives = _top_contributors(profile=profile, dish=dish, positive=True)
    negatives = _top_contributors(profile=profile, dish=dish, positive=False)

    return {
        "explicit_match": round(explicit_match, 6),
        "long_term_match": round(long_term_match, 6),
        "short_term_match": round(short_term_match, 6),
        "context_match": round(context_match, 6),
        "novelty_bonus": round(novelty_bonus, 6),
        "explicit_negative_penalty": round(explicit_negative_penalty, 6),
        "recent_repeat_penalty": round(recent_repeat_penalty, 6),
        "score": round(score, 6),
        "top_positive_contributors": positives,
        "top_negative_contributors": negatives,
    }


def _layer_match(layer_profile: dict[str, dict[str, float]], dish: dict[str, Any]) -> tuple[float, float]:
    positive_sum = 0.0
    negative_sum = 0.0
    for axis in AXES:
        user_axis = layer_profile.get(axis, {})
        dish_axis = dish.get(axis, {})
        if not user_axis:
            continue
        axis_pos = 0.0
        axis_neg = 0.0
        denominator = max(1, len(user_axis))
        for key, weight in user_axis.items():
            dish_weight = float(dish_axis.get(key, 0.0))
            if dish_weight <= 0:
                continue
            if float(weight) >= 0:
                axis_pos += float(weight) * dish_weight
            else:
                axis_neg += abs(float(weight)) * dish_weight
        axis_pos = (axis_pos / denominator) * AXIS_WEIGHTS[axis]
        axis_neg = (axis_neg / denominator) * AXIS_WEIGHTS[axis]
        positive_sum += axis_pos
        negative_sum += axis_neg
    return positive_sum, negative_sum


def _request_context_match(request_tags: list[str], dish: dict[str, Any]) -> float:
    if not request_tags:
        return 0.0
    dish_context = dish.get("context", {})
    score = sum(float(dish_context.get(tag, 0.0)) for tag in request_tags)
    return round(0.28 * score / max(1, len(request_tags)), 6)


def _top_contributors(profile: dict[str, Any], dish: dict[str, Any], positive: bool) -> list[str]:
    pairs: list[tuple[str, float]] = []
    for layer_name in ("explicit", "long_term", "short_term"):
        layer = profile.get(layer_name, {})
        for axis in AXES:
            user_axis = layer.get(axis, {})
            dish_axis = dish.get(axis, {})
            for key, user_weight in user_axis.items():
                d_weight = float(dish_axis.get(key, 0.0))
                if d_weight <= 0:
                    continue
                contribution = float(user_weight) * d_weight
                if positive and contribution > 0:
                    pairs.append((f"{layer_name}:{axis}:{key}", contribution))
                if not positive and contribution < 0:
                    pairs.append((f"{layer_name}:{axis}:{key}", contribution))
    pairs.sort(key=lambda x: (-x[1], x[0]) if positive else (x[1], x[0]))
    return [f"{name}={round(value, 4)}" for name, value in pairs[:5]]


def _apply_hard_filters(
    constraints: list[str],
    dish: dict[str, Any],
    ingredient_evidence: set[str],
) -> tuple[bool, list[str], bool]:
    hard_flags = dish.get("hard_flags", {})
    ingredients = set((dish.get("ingredient") or {}).keys()) | set(ingredient_evidence)
    name = _norm(str(dish.get("meta", {}).get("name", "")))
    excluded = False
    reasons: list[str] = []
    compliance_unknown = False

    for constraint in constraints:
        normalized_constraint = _constraint_alias(constraint)
        if normalized_constraint in STRICT_ALLERGY_CONSTRAINTS:
            if bool(hard_flags.get(normalized_constraint)) or normalized_constraint in ingredients:
                excluded = True
                reasons.append(f"hard_{normalized_constraint}")
        elif normalized_constraint == "mammalian_red_meat":
            if ingredients & MAMMALIAN_RED_MEAT_INGREDIENTS:
                excluded = True
                reasons.append("hard_mammalian_red_meat")
        elif normalized_constraint == "mammalian_broth_stock":
            if any(marker in name for marker in MAMMALIAN_BROTH_MARKERS):
                excluded = True
                reasons.append("hard_mammalian_broth_stock")
        elif normalized_constraint == "vegan":
            if ingredients & VEGAN_FORBIDDEN_INGREDIENTS:
                excluded = True
                reasons.append("hard_vegan_animal_product")
        elif normalized_constraint == "halal":
            if (ingredients & HALAL_FORBIDDEN_INGREDIENTS) or any(marker in name for marker in HALAL_ALCOHOL_MARKERS):
                excluded = True
                reasons.append("hard_halal_forbidden")
            elif ingredients & MAMMALIAN_RED_MEAT_INGREDIENTS:
                compliance_unknown = True

    return excluded, sorted(set(reasons)), compliance_unknown


def _user_explanation(dish: dict[str, Any], breakdown: dict[str, Any]) -> str:
    positives = breakdown.get("top_positive_contributors", [])[:2]
    negatives = breakdown.get("top_negative_contributors", [])[:1]
    pos_text = ", ".join(positives) if positives else "no strong positive tags"
    neg_text = f"; watch-outs: {', '.join(negatives)}" if negatives else ""
    return f"Matches your profile via {pos_text}{neg_text}"


def _debug_explanation(dish: dict[str, Any], breakdown: dict[str, Any]) -> str:
    parts = [
        f"explicit={breakdown['explicit_match']}",
        f"long={breakdown['long_term_match']}",
        f"short={breakdown['short_term_match']}",
        f"context={breakdown['context_match']}",
        f"novelty={breakdown['novelty_bonus']}",
        f"explicit_neg_penalty={breakdown['explicit_negative_penalty']}",
        f"repeat_penalty={breakdown['recent_repeat_penalty']}",
    ]
    return " | ".join(parts)


def _build_recent_repeat_counts(events: list[dict[str, Any]], user_id: int) -> dict[str, int]:
    # Seed events refer to historical purchases; without dish_id in event_items
    # we default to no repeat penalties unless a dish_id is explicitly present.
    counts: dict[str, int] = {}
    for row in events:
        if int(row.get("user_id", -1)) != int(user_id):
            continue
        object_id = row.get("object_id")
        if object_id and str(object_id).isdigit():
            counts[str(object_id)] = counts.get(str(object_id), 0) + 1
    return counts


def _context_tags_from_request(request_context: dict[str, str]) -> list[str]:
    tags: list[str] = []
    time_of_day = _norm(request_context.get("time_of_day", ""))
    hunger = _norm(request_context.get("hunger_level", ""))
    venue = _norm(request_context.get("venue_type", ""))
    situation = _norm(request_context.get("situation", ""))

    time_map = {
        "morning": "morning",
        "breakfast": "morning",
        "lunch": "lunch",
        "day": "lunch",
        "evening": "evening",
        "dinner": "evening",
        "night": "night",
    }
    if time_of_day in time_map:
        tags.append(time_map[time_of_day])
    hunger_map = {
        "snack": "snack",
        "light": "quick",
        "quick": "quick",
        "full": "hearty",
        "hearty": "hearty",
    }
    if hunger in hunger_map:
        tags.append(hunger_map[hunger])
    venue_map = {
        "home": "delivery_home",
        "office": "delivery_office",
        "dine_in": "dine_in",
    }
    if venue in venue_map:
        tags.append(venue_map[venue])

    situation_markers = [
        ("romantic", "romantic"),
        ("party", "company"),
        ("company", "company"),
        ("recovery", "recovery"),
        ("quick", "quick"),
        ("home", "delivery_home"),
    ]
    for marker, tag in situation_markers:
        if marker in situation:
            tags.append(tag)
    return sorted(set(tags))


def _write_outputs(
    base: Path,
    audit_dir: Path,
    scored_rows: list[dict[str, Any]],
    top_k: int,
    constraint_audit_rows: list[list[Any]],
) -> None:
    _write_jsonl(base / "recommendation_scores.jsonl", scored_rows)
    top = scored_rows[:top_k]

    with (base / "recommendation_topk_sample.csv").open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["rank", "user_id", "dish_id", "dish_name", "score"])
        for idx, row in enumerate(top, start=1):
            writer.writerow([idx, row["user_id"], row["dish_id"], row["dish_name"], row["score"]])

    with (base / "recommendation_explanations_sample.csv").open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["user_id", "dish_id", "dish_name", "score", "user_explanation", "debug_explanation"])
        for row in top:
            writer.writerow(
                [
                    row["user_id"],
                    row["dish_id"],
                    row["dish_name"],
                    row["score"],
                    row["user_explanation"],
                    row["debug_explanation"],
                ]
            )

    with (base / "recommendation_constraint_audit.csv").open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["user_id", "dish_id", "dish_name", "excluded", "reasons", "compliance_unknown"])
        for row in constraint_audit_rows:
            writer.writerow(row)


def _profile_from_rows(user_feature_rows: list[dict[str, Any]], user_id: int) -> dict[str, dict[str, dict[str, float]]]:
    profile = {"explicit": {}, "long_term": {}, "short_term": {}}
    for row in user_feature_rows:
        if int(row.get("user_id", -1)) != int(user_id):
            continue
        layer = str(row.get("profile_layer"))
        if layer not in profile:
            continue
        axis = str(row.get("axis"))
        key = str(row.get("feature_key"))
        weight = float(row.get("weight", 0.0))
        profile[layer].setdefault(axis, {})[key] = weight
    return profile


def _dish_ingredient_evidence_from_rows(rows: list[dict[str, Any]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for row in rows:
        if row.get("axis") != "ingredient":
            continue
        dish_id = str(row.get("dish_id"))
        key = str(row.get("feature_key"))
        result.setdefault(dish_id, set()).add(key)
    return result


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file_obj:
        for row in rows:
            file_obj.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    result: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file_obj:
        for line in file_obj:
            stripped = line.strip()
            if stripped:
                result.append(json.loads(stripped))
    return result


def _dish_sort_key(dish_id: Any) -> tuple[int, str]:
    text = str(dish_id)
    if text.isdigit():
        return int(text), text
    return 10**9, text


def _norm(value: str) -> str:
    return value.lower().replace("ё", "е").strip()


def _constraint_alias(key: str) -> str:
    mapping = {
        "peanut_allergy": "peanut",
    }
    return mapping.get(key, key)


def _dish_snapshot_id(dish: dict[str, Any]) -> str:
    payload = {
        "dish_id": str(dish.get("dish_id")),
        "taste": dish.get("taste", {}),
        "ingredient": dish.get("ingredient", {}),
        "cuisine": dish.get("cuisine", {}),
        "format_texture": dish.get("format_texture", {}),
        "context": dish.get("context", {}),
        "hard_flags": dish.get("hard_flags", {}),
        "nutrition": dish.get("nutrition", {}),
        "feature_version": dish.get("meta", {}).get("feature_version", "runtime_v1"),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
