from __future__ import annotations

from typing import Any


CVP_VERSION = "cvp_v1"
PROFILE_LAYERS = ("explicit", "long_term", "short_term")


def build_cvp_profile(
    profile_cache_row: dict[str, Any],
    constraint_rows: list[dict[str, Any]] | None = None,
    max_features: int = 6,
) -> dict[str, Any]:
    """Build the standalone digital taste profile contract from serving-cache data."""
    user_id = int(profile_cache_row["user_id"])
    explicit = _clean_layer(profile_cache_row.get("explicit", {}))
    long_term = _clean_layer(profile_cache_row.get("long_term", {}))
    short_term = _clean_layer(profile_cache_row.get("short_term", {}))

    cvp_profile = {
        "cvp_version": CVP_VERSION,
        "user_id": user_id,
        "hard_constraints": _normalize_hard_constraints(
            user_id=user_id,
            profile_hard_constraints=profile_cache_row.get("hard_constraints", []),
            constraint_rows=constraint_rows or [],
        ),
        "soft_preferences": {
            "explicit": _layer_preferences(explicit, max_features=max_features),
            "long_term": _layer_preferences(long_term, max_features=max_features),
            "short_term": _layer_preferences(short_term, max_features=max_features),
        },
        "feature_layers": {
            "explicit": explicit,
            "long_term": long_term,
            "short_term": short_term,
        },
        "history_aggregates": {
            "long_term": long_term,
            "short_term": short_term,
            "top_long_term": _top_features(long_term, positive=True, limit=max_features),
            "top_short_term": _top_features(short_term, positive=True, limit=max_features),
        },
        "meta": {
            **dict(profile_cache_row.get("meta", {})),
            "cvp_schema": CVP_VERSION,
            "cvp_source": "user_profiles_cache",
        },
    }
    cvp_profile["human_readable_description"] = describe_cvp_profile(cvp_profile)
    return cvp_profile


def scoring_profile_from_cvp(cvp_profile: dict[str, Any]) -> dict[str, Any]:
    feature_layers = cvp_profile.get("feature_layers", {}) or {}
    history = cvp_profile.get("history_aggregates", {}) or {}
    return {
        "user_id": int(cvp_profile["user_id"]),
        "hard_constraints": [
            row["constraint_key"]
            for row in cvp_profile.get("hard_constraints", [])
            if row.get("scope") == "hard" and row.get("constraint_key")
        ],
        "explicit": _clean_layer(feature_layers.get("explicit", {})),
        "long_term": _clean_layer(feature_layers.get("long_term") or history.get("long_term", {})),
        "short_term": _clean_layer(feature_layers.get("short_term") or history.get("short_term", {})),
        "meta": dict(cvp_profile.get("meta", {})),
    }


def build_cvp_dw_export_row(cvp_profile: dict[str, Any]) -> dict[str, Any]:
    hard_keys = [
        row["constraint_key"]
        for row in cvp_profile.get("hard_constraints", [])
        if row.get("scope") == "hard" and row.get("constraint_key")
    ]
    soft = cvp_profile.get("soft_preferences", {})
    history = cvp_profile.get("history_aggregates", {})
    return {
        "user_id": int(cvp_profile["user_id"]),
        "cvp_version": str(cvp_profile.get("cvp_version", CVP_VERSION)),
        "hard_constraints": sorted(hard_keys),
        "explicit_positive_top": soft.get("explicit", {}).get("positive", []),
        "explicit_negative_top": soft.get("explicit", {}).get("negative", []),
        "long_term_top": history.get("top_long_term", []),
        "short_term_top": history.get("top_short_term", []),
        "human_readable_description": str(cvp_profile.get("human_readable_description", "")),
        "payload_json": cvp_profile,
    }


def describe_cvp_profile(cvp_profile: dict[str, Any]) -> str:
    user_id = int(cvp_profile["user_id"])
    hard_keys = [row["constraint_key"] for row in cvp_profile.get("hard_constraints", [])]
    soft = cvp_profile.get("soft_preferences", {})
    explicit = soft.get("explicit", {})
    long_term = soft.get("long_term", {})
    short_term = soft.get("short_term", {})

    lines = [f"ЦВП пользователя {user_id}."]
    if hard_keys:
        lines.append(f"Строгие ограничения: {', '.join(hard_keys)}.")
    else:
        lines.append("Строгие ограничения не зафиксированы.")

    explicit_positive = _format_feature_list(explicit.get("positive", [])[:3])
    explicit_negative = _format_feature_list(explicit.get("negative", [])[:3])
    long_positive = _format_feature_list(long_term.get("positive", [])[:3])
    short_positive = _format_feature_list(short_term.get("positive", [])[:3])

    if explicit_positive:
        lines.append(f"Явные предпочтения: {explicit_positive}.")
    if explicit_negative:
        lines.append(f"Явные нежелательные признаки: {explicit_negative}.")
    if long_positive:
        lines.append(f"Устойчивые вкусовые сигналы: {long_positive}.")
    if short_positive:
        lines.append(f"Недавний контекст/агрегаты: {short_positive}.")
    if len(lines) == 2:
        lines.append("Мягкие предпочтения пока разреженные.")
    return " ".join(lines)


def _normalize_hard_constraints(
    user_id: int,
    profile_hard_constraints: list[Any],
    constraint_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for key in profile_hard_constraints:
        if not key:
            continue
        normalized_key = str(key)
        by_key[normalized_key] = {
            "constraint_key": normalized_key,
            "scope": "hard",
            "source": "profile_cache",
            "reason_text": None,
            "confidence": None,
        }

    for row in constraint_rows:
        if int(row.get("user_id", -1)) != int(user_id):
            continue
        if row.get("scope") != "hard":
            continue
        key = str(row.get("constraint_key", ""))
        if not key:
            continue
        by_key[key] = {
            "constraint_key": key,
            "scope": "hard",
            "source": row.get("source", ""),
            "reason_text": row.get("reason_text"),
            "confidence": row.get("confidence"),
        }
    return [by_key[key] for key in sorted(by_key)]


def _layer_preferences(layer: dict[str, dict[str, float]], max_features: int) -> dict[str, list[dict[str, Any]]]:
    return {
        "positive": _top_features(layer, positive=True, limit=max_features),
        "negative": _top_features(layer, positive=False, limit=max_features),
    }


def _top_features(
    layer: dict[str, dict[str, float]],
    positive: bool,
    limit: int,
) -> list[dict[str, Any]]:
    rows = []
    for axis, values in layer.items():
        for feature_key, weight in values.items():
            numeric_weight = float(weight)
            if positive and numeric_weight <= 0:
                continue
            if not positive and numeric_weight >= 0:
                continue
            rows.append(
                {
                    "axis": str(axis),
                    "feature_key": str(feature_key),
                    "weight": round(numeric_weight, 6),
                }
            )
    rows.sort(
        key=lambda row: (
            -float(row["weight"]) if positive else float(row["weight"]),
            str(row["axis"]),
            str(row["feature_key"]),
        )
    )
    return rows[: max(0, int(limit))]


def _clean_layer(layer: dict[str, Any]) -> dict[str, dict[str, float]]:
    clean: dict[str, dict[str, float]] = {}
    for axis, values in sorted((layer or {}).items(), key=lambda item: str(item[0])):
        if not isinstance(values, dict):
            continue
        clean_values = {
            str(feature_key): round(float(weight), 6)
            for feature_key, weight in sorted(values.items(), key=lambda item: str(item[0]))
            if abs(float(weight)) > 1e-6
        }
        if clean_values:
            clean[str(axis)] = clean_values
    return clean


def _format_feature_list(rows: list[dict[str, Any]]) -> str:
    return ", ".join(
        f"{row['axis']}:{row['feature_key']}={round(float(row['weight']), 3)}"
        for row in rows
    )
