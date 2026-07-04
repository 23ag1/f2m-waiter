from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


LAYER_ORDER = {"explicit": 0, "long_term": 1, "short_term": 2}
GENERIC_INGREDIENT_KEYS = {
    "ingredient",
    "ingredients",
    "vegetables",
    "garnish",
    "sauce",
    "sauces",
    "additive",
    "protein",
    "fat",
    "vegetable",
}
BASE_EVENT_WEIGHT = 1.0
LONG_COEFF = 0.15
SHORT_COEFF = 0.60
LAMBDA_LONG = math.log(2) / 90.0
LAMBDA_SHORT = math.log(2) / 5.0
SYNTHETIC_BASE = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
SYNTHETIC_STEP = timedelta(hours=6)


@dataclass(frozen=True)
class RebuildStats:
    users: int
    feature_rows: int
    cache_rows: int
    time_is_synthetic: bool


def rebuild_profiles(
    derived_dir: Path | str,
    taxonomy_path: Path | str,
) -> RebuildStats:
    base = Path(derived_dir)
    audit_dir = base / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    _ = json.loads(Path(taxonomy_path).read_text(encoding="utf-8"))
    questionnaire_submissions = _read_jsonl(base / "questionnaire_submissions.jsonl")
    user_constraints = _read_jsonl(base / "user_constraints.jsonl")
    questionnaire_features = [
        row
        for row in _read_jsonl(base / "user_feature_values.jsonl")
        if row.get("profile_layer") == "explicit" and row.get("source") == "questionnaire"
    ]
    events = _read_jsonl(base / "events.jsonl")
    event_items = _read_jsonl(base / "event_items.jsonl")
    dish_rows = _read_jsonl(base / "dish_feature_values.jsonl")
    dish_cache = json.loads((base / "dish_features_cache.json").read_text(encoding="utf-8"))

    dish_features_by_id = _index_dish_rows(dish_rows)
    dish_name_to_id = {
        _norm(str(row.get("meta", {}).get("name", ""))): str(row["dish_id"])
        for row in dish_cache
        if row.get("meta", {}).get("name")
    }

    explicit_by_user = _build_explicit_layer(questionnaire_features)
    constraints_by_user = _group_constraints(user_constraints)
    event_items_by_key = {(row["source_system"], row["event_uuid"]): row for row in event_items}
    events_sorted = _sort_events_deterministically(events)

    long_state: dict[int, dict[tuple[str, str], float]] = {}
    short_state: dict[int, dict[tuple[str, str], float]] = {}
    last_seen_long: dict[int, datetime] = {}
    last_seen_short: dict[int, datetime] = {}
    context_rows: list[list[Any]] = []

    for event in events_sorted:
        if event.get("event_type") != "purchase_paid":
            continue
        user_id = int(event["user_id"])
        event_time = event["synthetic_occurred_at"]
        payload = event.get("payload_json") or {}
        item = event_items_by_key.get((event["source_system"], event["event_uuid"]), {})

        decomposed = _build_event_feature_vector(
            payload=payload,
            item=item,
            dish_features_by_id=dish_features_by_id,
            dish_name_to_id=dish_name_to_id,
        )
        if not decomposed:
            continue
        qty = int(item.get("qty", 1) or 1)
        signal = BASE_EVENT_WEIGHT * math.log(1 + qty)

        if user_id not in long_state:
            long_state[user_id] = {}
            short_state[user_id] = {}
            last_seen_long[user_id] = event_time
            last_seen_short[user_id] = event_time

        delta_days_long = (event_time - last_seen_long[user_id]).total_seconds() / 86400.0
        delta_days_short = (event_time - last_seen_short[user_id]).total_seconds() / 86400.0
        last_seen_long[user_id] = event_time
        last_seen_short[user_id] = event_time

        for key, feature_weight in decomposed.items():
            delta = signal * feature_weight
            old_long = long_state[user_id].get(key, 0.0)
            old_short = short_state[user_id].get(key, 0.0)
            new_long = _clip(
                old_long * math.exp(-LAMBDA_LONG * delta_days_long) + LONG_COEFF * delta,
                -1.0,
                1.0,
            )
            new_short = _clip(
                old_short * math.exp(-LAMBDA_SHORT * delta_days_short) + SHORT_COEFF * delta,
                -1.0,
                1.0,
            )
            long_state[user_id][key] = new_long
            short_state[user_id][key] = new_short

        parsed_context = _parse_context_tags(str(payload.get("context", "")))
        for tag in parsed_context:
            key = ("context", tag)
            short_state[user_id][key] = _clip(short_state[user_id].get(key, 0.0) + 0.25, -1.0, 1.0)
        context_rows.append(
            [
                user_id,
                event["event_uuid"],
                event_time.isoformat(),
                "|".join(parsed_context),
                True,
            ]
        )

    users = sorted(
        set(explicit_by_user.keys())
        | set(long_state.keys())
        | set(short_state.keys())
        | set(constraints_by_user.keys())
        | {int(row["user_id"]) for row in questionnaire_submissions}
    )

    out_rows = _materialize_user_feature_rows(explicit_by_user, long_state, short_state)
    cache_rows = _materialize_cache_rows(users, explicit_by_user, long_state, short_state, constraints_by_user)

    _write_jsonl(base / "user_feature_values.jsonl", out_rows)
    (base / "user_profiles_cache.json").write_text(
        json.dumps(cache_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_rebuild_audit(
        audit_dir=audit_dir,
        users=users,
        out_rows=out_rows,
        cache_rows=cache_rows,
        constraints_by_user=constraints_by_user,
        context_rows=context_rows,
    )

    return RebuildStats(
        users=len(users),
        feature_rows=len(out_rows),
        cache_rows=len(cache_rows),
        time_is_synthetic=True,
    )


def show_profile(derived_dir: Path | str, user_id: int) -> str:
    base = Path(derived_dir)
    cache_rows = json.loads((base / "user_profiles_cache.json").read_text(encoding="utf-8"))
    constraints = _group_constraints(_read_jsonl(base / "user_constraints.jsonl"))
    profile = next((row for row in cache_rows if int(row["user_id"]) == int(user_id)), None)
    if profile is None:
        return f"user {user_id} profile not found"

    long_features = _flatten_layer(profile.get("long_term", {}))
    short_features = _flatten_layer(profile.get("short_term", {}))
    explicit_features = _flatten_layer(profile.get("explicit", {}))

    def top(features: list[tuple[str, float]], positive: bool) -> list[str]:
        filtered = [item for item in features if (item[1] > 0 if positive else item[1] < 0)]
        sorted_items = sorted(filtered, key=lambda x: (-x[1] if positive else x[1], x[0]))[:6]
        return [f"{name}={round(value, 3)}" for name, value in sorted_items]

    hard = sorted({row["constraint_key"] for row in constraints.get(user_id, []) if row.get("scope") == "hard"})
    lines = [
        f"user_id={user_id}",
        f"hard_constraints={hard}",
        f"explicit_top_pos={top(explicit_features, True)}",
        f"explicit_top_neg={top(explicit_features, False)}",
        f"long_term_top_pos={top(long_features, True)}",
        f"long_term_top_neg={top(long_features, False)}",
        f"short_term_top_pos={top(short_features, True)}",
        f"short_term_top_neg={top(short_features, False)}",
    ]
    return "\n".join(lines)


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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file_obj:
        for row in rows:
            file_obj.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _norm(value: str) -> str:
    return value.lower().replace("ё", "е").strip()


def _index_dish_rows(rows: list[dict[str, Any]]) -> dict[str, dict[tuple[str, str], float]]:
    result: dict[str, dict[tuple[str, str], float]] = {}
    for row in rows:
        dish_id = str(row["dish_id"])
        axis = row["axis"]
        key = row["feature_key"]
        if str(row.get("source", "")).lower() in {"needs_review", "ambiguous"}:
            continue
        if axis == "restriction":
            continue
        if axis == "nutrition":
            continue
        if axis == "ingredient" and _norm(key) in GENERIC_INGREDIENT_KEYS:
            continue
        value = row.get("value_num")
        if value is None:
            continue
        result.setdefault(dish_id, {})[(axis, key)] = float(value)
    return result


def _build_explicit_layer(rows: list[dict[str, Any]]) -> dict[int, dict[tuple[str, str], float]]:
    result: dict[int, dict[tuple[str, str], float]] = {}
    for row in rows:
        user_id = int(row["user_id"])
        axis = str(row["axis"])
        key = str(row["feature_key"])
        if axis == "restriction" and key in {"peanut", "lactose", "soy", "egg", "fish_seafood"}:
            continue
        result.setdefault(user_id, {})[(axis, key)] = float(row["weight"])
    return result


def _group_constraints(rows: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    result: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        result.setdefault(int(row["user_id"]), []).append(row)
    return result


def _sort_events_deterministically(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in events:
        grouped.setdefault(int(row["user_id"]), []).append(dict(row))

    result: list[dict[str, Any]] = []
    for user_id in sorted(grouped):
        sorted_events = sorted(grouped[user_id], key=lambda row: (_event_order_key(str(row["event_uuid"])), str(row["event_uuid"])))
        for idx, event in enumerate(sorted_events):
            event["synthetic_occurred_at"] = SYNTHETIC_BASE + (idx * SYNTHETIC_STEP)
            result.append(event)
    return sorted(result, key=lambda row: (int(row["user_id"]), row["synthetic_occurred_at"], str(row["event_uuid"])))


def _event_order_key(event_uuid: str) -> tuple[int, int]:
    parts = event_uuid.split(".")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return int(parts[0]), int(parts[1])
    if event_uuid.isdigit():
        return int(event_uuid), 0
    return 10**9, 10**9


def _build_event_feature_vector(
    payload: dict[str, Any],
    item: dict[str, Any],
    dish_features_by_id: dict[str, dict[tuple[str, str], float]],
    dish_name_to_id: dict[str, str],
) -> dict[tuple[str, str], float]:
    event_name = _norm(str(payload.get("dish") or item.get("dish_name") or ""))
    dish_id = dish_name_to_id.get(event_name)
    vector: dict[tuple[str, str], float] = {}
    if dish_id and dish_id in dish_features_by_id:
        vector.update(dish_features_by_id[dish_id])
    else:
        vector.update(_fallback_features_from_payload(payload))

    context_tags = _parse_context_tags(str(payload.get("context", "")))
    for tag in context_tags:
        vector[("context", tag)] = max(vector.get(("context", tag), 0.0), 0.6)
    _apply_modifier_patch(vector, event_name)
    return vector


def _fallback_features_from_payload(payload: dict[str, Any]) -> dict[tuple[str, str], float]:
    vector: dict[tuple[str, str], float] = {}
    ingredients_text = _norm(str(payload.get("ingredients", "")))
    flavor = payload.get("flavor_profile") or {}

    alias_map = {
        "лосос": "salmon",
        "кревет": "shrimp",
        "тунец": "tuna",
        "куриц": "chicken",
        "говядин": "beef",
        "баранин": "lamb",
        "свинин": "pork",
        "нут": "chickpea",
        "чечевиц": "lentil",
        "соев": "soy_sauce",
        "терияк": "teriyaki",
        "рыбный соус": "fish_sauce",
    }
    for marker, canonical in alias_map.items():
        if marker in ingredients_text:
            vector[("ingredient", canonical)] = 0.9

    for taste_key in ("sweet", "salty", "sour", "spicy", "bitter", "umami"):
        value = flavor.get(taste_key)
        if value is None:
            continue
        vector[("taste", taste_key)] = float(value)

    cuisine_markers = {
        "asian": ("том-ям", "рамен", "кимчи", "соев", "терияк", "суш", "ролл"),
        "georgian_caucasian": ("хачапури", "хинкали", "лобио", "кебаб"),
        "russian_home": ("борщ", "пельмен", "сырник"),
        "fast_food": ("бургер", "фри", "баскет", "kfc"),
        "healthy": ("салат", "на пару", "су-вид"),
    }
    dish_name = _norm(str(payload.get("dish", "")))
    for cuisine, markers in cuisine_markers.items():
        if any(marker in dish_name for marker in markers):
            vector[("cuisine", cuisine)] = 0.8
    return vector


def _parse_context_tags(text: str) -> list[str]:
    value = _norm(text)
    mapping = [
        ("morning", ("утрен", "завтрак")),
        ("lunch", ("обед", "ланч")),
        ("evening", ("ужин", "вечер")),
        ("snack", ("перекус", "закуска", "стритфуд")),
        ("quick", ("быстр", "дефицит времени", "на бегу")),
        ("romantic", ("романтич",)),
        ("delivery_home", ("домашн", "дома")),
        ("company", ("компан", "дружеск", "банкет", "празднич")),
        ("recovery", ("восстанов",)),
    ]
    tags = [tag for tag, markers in mapping if any(marker in value for marker in markers)]
    return sorted(set(tags))


def _apply_modifier_patch(vector: dict[tuple[str, str], float], event_name: str) -> None:
    # TODO: repeated-modifier pattern learning is out of scope for this milestone.
    if "без соуса" not in event_name and "without sauce" not in event_name:
        return
    for key in [("ingredient", "soy_sauce"), ("ingredient", "teriyaki"), ("ingredient", "oyster_sauce"), ("ingredient", "fish_sauce")]:
        vector.pop(key, None)
    if ("format_texture", "creamy") in vector:
        vector[("format_texture", "creamy")] = max(0.0, vector[("format_texture", "creamy")] - 0.4)


def _materialize_user_feature_rows(
    explicit_by_user: dict[int, dict[tuple[str, str], float]],
    long_state: dict[int, dict[tuple[str, str], float]],
    short_state: dict[int, dict[tuple[str, str], float]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for user_id in sorted(set(explicit_by_user) | set(long_state) | set(short_state)):
        for layer, values in (
            ("explicit", explicit_by_user.get(user_id, {})),
            ("long_term", long_state.get(user_id, {})),
            ("short_term", short_state.get(user_id, {})),
        ):
            for (axis, key), weight in sorted(values.items(), key=lambda x: (x[0][0], x[0][1])):
                if abs(weight) < 1e-6:
                    continue
                rows.append(
                    {
                        "user_id": user_id,
                        "profile_layer": layer,
                        "axis": axis,
                        "feature_key": key,
                        "weight": round(float(weight), 6),
                        "source": "questionnaire" if layer == "explicit" else "event",
                        "confidence": 0.75 if layer == "explicit" else 0.9,
                    }
                )
    rows.sort(
        key=lambda row: (
            int(row["user_id"]),
            LAYER_ORDER[row["profile_layer"]],
            str(row["axis"]),
            str(row["feature_key"]),
        )
    )
    return rows


def _materialize_cache_rows(
    users: list[int],
    explicit_by_user: dict[int, dict[tuple[str, str], float]],
    long_state: dict[int, dict[tuple[str, str], float]],
    short_state: dict[int, dict[tuple[str, str], float]],
    constraints_by_user: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for user_id in users:
        row = {
            "user_id": user_id,
            "hard_constraints": sorted(
                {
                    c["constraint_key"]
                    for c in constraints_by_user.get(user_id, [])
                    if c.get("scope") == "hard"
                }
            ),
            "explicit": _to_layer_json(explicit_by_user.get(user_id, {})),
            "long_term": _to_layer_json(long_state.get(user_id, {})),
            "short_term": _to_layer_json(short_state.get(user_id, {})),
            "meta": {"feature_version": "runtime_v1", "time_is_synthetic": True},
        }
        rows.append(row)
    rows.sort(key=lambda item: int(item["user_id"]))
    return rows


def _to_layer_json(values: dict[tuple[str, str], float]) -> dict[str, dict[str, float]]:
    by_axis: dict[str, dict[str, float]] = {}
    for (axis, key), weight in sorted(values.items(), key=lambda x: (x[0][0], x[0][1])):
        if abs(weight) < 1e-6:
            continue
        by_axis.setdefault(axis, {})[key] = round(float(weight), 6)
    return by_axis


def _flatten_layer(layer: dict[str, dict[str, float]]) -> list[tuple[str, float]]:
    items: list[tuple[str, float]] = []
    for axis, tags in layer.items():
        for key, value in tags.items():
            items.append((f"{axis}:{key}", float(value)))
    return items


def _write_rebuild_audit(
    audit_dir: Path,
    users: list[int],
    out_rows: list[dict[str, Any]],
    cache_rows: list[dict[str, Any]],
    constraints_by_user: dict[int, list[dict[str, Any]]],
    context_rows: list[list[Any]],
) -> None:
    _write_summary(audit_dir, users, out_rows, cache_rows)
    _write_topn_by_user(audit_dir, cache_rows)
    _write_context_by_user(audit_dir, context_rows)
    _write_constraints_check(audit_dir, out_rows, constraints_by_user)


def _write_summary(audit_dir: Path, users: list[int], out_rows: list[dict[str, Any]], cache_rows: list[dict[str, Any]]) -> None:
    path = audit_dir / "profile_rebuild_summary.csv"
    features_hash = hashlib.sha256("\n".join(json.dumps(row, sort_keys=True, ensure_ascii=False) for row in out_rows).encode("utf-8")).hexdigest()
    cache_hash = hashlib.sha256(json.dumps(cache_rows, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(
            [
                "unique_users",
                "feature_rows",
                "cache_rows",
                "time_is_synthetic",
                "features_sha256",
                "cache_sha256",
            ]
        )
        writer.writerow([len(users), len(out_rows), len(cache_rows), True, features_hash, cache_hash])


def _write_topn_by_user(audit_dir: Path, cache_rows: list[dict[str, Any]]) -> None:
    path = audit_dir / "profile_feature_topn_by_user.csv"
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["user_id", "layer", "direction", "top_features"])
        for row in cache_rows:
            for layer_name in ("explicit", "long_term", "short_term"):
                features = _flatten_layer(row.get(layer_name, {}))
                pos = sorted([f for f in features if f[1] > 0], key=lambda x: (-x[1], x[0]))[:8]
                neg = sorted([f for f in features if f[1] < 0], key=lambda x: (x[1], x[0]))[:8]
                writer.writerow([row["user_id"], layer_name, "positive", "|".join(f"{k}={round(v,3)}" for k, v in pos)])
                writer.writerow([row["user_id"], layer_name, "negative", "|".join(f"{k}={round(v,3)}" for k, v in neg)])


def _write_context_by_user(audit_dir: Path, context_rows: list[list[Any]]) -> None:
    path = audit_dir / "profile_context_by_user.csv"
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["user_id", "event_uuid", "synthetic_occurred_at", "parsed_context_tags", "time_is_synthetic"])
        for row in sorted(context_rows, key=lambda x: (int(x[0]), str(x[2]), str(x[1]))):
            writer.writerow(row)


def _write_constraints_check(
    audit_dir: Path,
    out_rows: list[dict[str, Any]],
    constraints_by_user: dict[int, list[dict[str, Any]]],
) -> None:
    path = audit_dir / "profile_constraints_check.csv"
    hard_rows_in_preferences = [
        row
        for row in out_rows
        if row["axis"] == "restriction"
        and row["feature_key"] in {"peanut", "lactose", "fish_seafood", "egg", "soy", "mammalian_red_meat", "mammalian_broth_stock"}
    ]
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["user_id", "hard_constraints_count", "hard_constraints", "hard_rows_in_user_feature_values"])
        for user_id in sorted(constraints_by_user):
            hard = sorted(
                {
                    row["constraint_key"]
                    for row in constraints_by_user[user_id]
                    if row.get("scope") == "hard"
                }
            )
            leaks = [row for row in hard_rows_in_preferences if int(row["user_id"]) == int(user_id)]
            writer.writerow([user_id, len(hard), "|".join(hard), len(leaks)])


def _clip(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))
