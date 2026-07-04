from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


QUESTIONNAIRE_CONFIG_FILENAME = "questionnaire_config.json"
QUESTIONNAIRE_CONFIG_VERSION = "questionnaire_config_v1"
DEFAULT_PUBLISHED_VERSION = "v1"


def default_questionnaire_payload() -> dict[str, Any]:
    return {
        "version_id": DEFAULT_PUBLISHED_VERSION,
        "title": "Food2Mood questionnaire",
        "steps": [
            {
                "id": "food_desires",
                "type": "preference",
                "question": "Что бы вы хотели поесть?",
                "hint": "",
                "mode": "want",
                "allow_multiple": True,
                "options": [
                    {
                        "id": "vegetables",
                        "label": "Больше овощей",
                        "tag": "vegetables",
                        "axis": "ingredient",
                        "mode": "want",
                        "icon": "",
                        "enabled": True,
                    },
                    {
                        "id": "meat",
                        "label": "Мясо",
                        "tag": "meat",
                        "axis": "ingredient",
                        "mode": "want",
                        "icon": "",
                        "enabled": True,
                    },
                    {
                        "id": "fish",
                        "label": "Рыба и морепродукты",
                        "tag": "fish_seafood",
                        "axis": "ingredient",
                        "mode": "want",
                        "icon": "",
                        "enabled": True,
                    },
                    {
                        "id": "soup",
                        "label": "Суп",
                        "tag": "soup",
                        "axis": "format_texture",
                        "mode": "want",
                        "icon": "",
                        "enabled": True,
                    },
                    {
                        "id": "spicy",
                        "label": "Острое блюдо",
                        "tag": "spicy",
                        "axis": "taste",
                        "mode": "want",
                        "icon": "",
                        "enabled": True,
                    },
                    {
                        "id": "sweet",
                        "label": "Сладкое",
                        "tag": "sweet",
                        "axis": "taste",
                        "mode": "want",
                        "icon": "",
                        "enabled": True,
                    },
                    {
                        "id": "light",
                        "label": "Легкое",
                        "tag": "light",
                        "axis": "nutrition",
                        "mode": "want",
                        "icon": "",
                        "enabled": True,
                    },
                    {
                        "id": "hot",
                        "label": "Горячее",
                        "tag": "hot",
                        "axis": "format_texture",
                        "mode": "want",
                        "icon": "",
                        "enabled": True,
                    },
                ],
            },
            {
                "id": "visit_context",
                "type": "event",
                "question": "Как вы сегодня?",
                "hint": "",
                "scenarios": [
                    {
                        "id": "time_sensitive",
                        "label": "Time-sensitive",
                        "enabled": True,
                        "time_windows": [
                            {
                                "id": "morning",
                                "label": "Утро",
                                "from_hour": 6,
                                "to_hour": 11,
                                "priority_tags": ["breakfast", "light", "hot"],
                            },
                            {
                                "id": "day",
                                "label": "День",
                                "from_hour": 11,
                                "to_hour": 16,
                                "priority_tags": ["soup", "salad", "meat"],
                            },
                            {
                                "id": "evening",
                                "label": "Вечер",
                                "from_hour": 16,
                                "to_hour": 23,
                                "priority_tags": ["meat", "fish_seafood", "snack"],
                            },
                        ],
                    },
                    {
                        "id": "participants",
                        "label": "Состав участников",
                        "enabled": True,
                        "options": [
                            {"id": "solo", "label": "Соло", "icon": "", "enabled": True},
                            {"id": "date", "label": "Свидание", "icon": "", "enabled": True},
                            {"id": "friends", "label": "С друзьями", "icon": "", "enabled": True},
                            {"id": "family", "label": "С семьей", "icon": "", "enabled": True},
                        ],
                    },
                    {
                        "id": "occasion",
                        "label": "Повод",
                        "enabled": False,
                        "options": [
                            {"id": "celebration", "label": "Праздник", "icon": "", "enabled": True},
                            {"id": "post_workout", "label": "После тренировки", "icon": "", "enabled": True},
                            {"id": "regular", "label": "Обычный день", "icon": "", "enabled": True},
                        ],
                    },
                ],
            },
        ],
    }


def default_questionnaire_config() -> dict[str, Any]:
    now = _now_iso()
    published = default_questionnaire_payload()
    published["created_at"] = now
    published["updated_at"] = now
    return {
        "schema_version": QUESTIONNAIRE_CONFIG_VERSION,
        "published_version": DEFAULT_PUBLISHED_VERSION,
        "draft": copy.deepcopy(published),
        "versions": {DEFAULT_PUBLISHED_VERSION: published},
        "audit_log": [
            {
                "action": "seed",
                "version_id": DEFAULT_PUBLISHED_VERSION,
                "actor": "system",
                "reason": "default questionnaire config",
                "created_at": now,
            }
        ],
    }


def load_questionnaire_config(derived_dir: Path | str) -> dict[str, Any]:
    path = Path(derived_dir) / QUESTIONNAIRE_CONFIG_FILENAME
    if not path.exists():
        return default_questionnaire_config()
    raw = json.loads(path.read_text(encoding="utf-8"))
    return normalize_questionnaire_config(raw)


def save_questionnaire_config(derived_dir: Path | str, config: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_questionnaire_config(config)
    base = Path(derived_dir)
    base.mkdir(parents=True, exist_ok=True)
    path = base / QUESTIONNAIRE_CONFIG_FILENAME
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return normalized


def normalize_questionnaire_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return default_questionnaire_config()

    config = default_questionnaire_config()
    config["schema_version"] = str(raw.get("schema_version") or QUESTIONNAIRE_CONFIG_VERSION)
    versions = raw.get("versions")
    if isinstance(versions, dict) and versions:
        config["versions"] = {
            str(version_id): normalize_questionnaire_payload(payload, version_id=str(version_id))
            for version_id, payload in versions.items()
            if isinstance(payload, dict)
        }
    if not config["versions"]:
        config["versions"] = default_questionnaire_config()["versions"]

    published_version = str(raw.get("published_version") or "")
    if not published_version or published_version not in config["versions"]:
        published_version = _latest_version_id(config["versions"])
    config["published_version"] = published_version

    draft = raw.get("draft")
    if isinstance(draft, dict):
        config["draft"] = normalize_questionnaire_payload(draft, version_id=str(draft.get("version_id") or "draft"))
    else:
        config["draft"] = copy.deepcopy(config["versions"][published_version])

    audit_log = raw.get("audit_log")
    config["audit_log"] = _normalize_audit_log(audit_log)
    return config


def normalize_questionnaire_payload(payload: dict[str, Any], *, version_id: str) -> dict[str, Any]:
    base = default_questionnaire_payload()
    source = payload if isinstance(payload, dict) else {}
    normalized = {
        "version_id": str(source.get("version_id") or version_id),
        "title": str(source.get("title") or base["title"]),
        "steps": _normalize_steps(source.get("steps") if isinstance(source.get("steps"), list) else base["steps"]),
        "created_at": str(source.get("created_at") or _now_iso()),
        "updated_at": str(source.get("updated_at") or _now_iso()),
    }
    if source.get("published_at"):
        normalized["published_at"] = str(source["published_at"])
    return normalized


def get_published_questionnaire(config: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_questionnaire_config(config)
    return copy.deepcopy(normalized["versions"][normalized["published_version"]])


def get_draft_questionnaire(config: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(normalize_questionnaire_config(config)["draft"])


def update_draft_questionnaire(
    config: dict[str, Any],
    payload: dict[str, Any],
    *,
    actor: str = "admin",
    reason: str = "",
) -> dict[str, Any]:
    normalized = normalize_questionnaire_config(config)
    draft = normalize_questionnaire_payload(payload, version_id=str(payload.get("version_id") or "draft"))
    now = _now_iso()
    draft["updated_at"] = now
    normalized["draft"] = draft
    normalized["audit_log"].append(_audit_row("draft_update", draft["version_id"], actor=actor, reason=reason, at=now))
    return normalized


def publish_draft_questionnaire(
    config: dict[str, Any],
    *,
    actor: str = "admin",
    reason: str = "",
) -> dict[str, Any]:
    normalized = normalize_questionnaire_config(config)
    now = _now_iso()
    version_id = _next_version_id(normalized)
    published = normalize_questionnaire_payload(normalized["draft"], version_id=version_id)
    published["version_id"] = version_id
    published["published_at"] = now
    published["updated_at"] = now
    normalized["versions"][version_id] = published
    normalized["published_version"] = version_id
    normalized["draft"] = copy.deepcopy(published)
    normalized["audit_log"].append(_audit_row("publish", version_id, actor=actor, reason=reason, at=now))
    return normalized


def rollback_questionnaire(
    config: dict[str, Any],
    *,
    version_id: str,
    actor: str = "admin",
    reason: str = "",
) -> dict[str, Any]:
    normalized = normalize_questionnaire_config(config)
    if version_id not in normalized["versions"]:
        raise ValueError(f"Unknown questionnaire version: {version_id}")
    now = _now_iso()
    normalized["published_version"] = version_id
    normalized["draft"] = copy.deepcopy(normalized["versions"][version_id])
    normalized["audit_log"].append(_audit_row("rollback", version_id, actor=actor, reason=reason, at=now))
    return normalized


def published_questionnaire_step_options(
    *,
    config: dict[str, Any] | None,
    step_id: str,
    fallback_options: list[dict[str, Any]],
) -> list[dict[str, str]]:
    questionnaire = get_published_questionnaire(config or default_questionnaire_config())
    options = _step_options(questionnaire, step_id=step_id)
    if not options:
        options = fallback_options
    return _public_options(options)


def _normalize_steps(raw_steps: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_steps, list):
        return []
    steps: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_steps):
        if not isinstance(raw, dict):
            continue
        step_type = str(raw.get("type") or "preference")
        step = {
            "id": str(raw.get("id") or f"step_{index + 1}"),
            "type": step_type,
            "question": str(raw.get("question") or ""),
            "hint": str(raw.get("hint") or ""),
        }
        if step_type == "event":
            step["scenarios"] = _normalize_scenarios(raw.get("scenarios", []))
        else:
            step["mode"] = str(raw.get("mode") or "want")
            step["allow_multiple"] = bool(raw.get("allow_multiple", True))
            step["options"] = _normalize_options(raw.get("options", []))
        steps.append(step)
    return steps


def _normalize_options(raw_options: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_options, list):
        return []
    options: list[dict[str, Any]] = []
    for raw in raw_options:
        if not isinstance(raw, dict):
            continue
        option_id = str(raw.get("id") or "").strip()
        label = str(raw.get("label") or "").strip()
        if not option_id or not label:
            continue
        options.append(
            {
                "id": option_id,
                "label": label,
                "tag": str(raw.get("tag") or option_id),
                "axis": str(raw.get("axis") or ""),
                "mode": str(raw.get("mode") or "want"),
                "icon": str(raw.get("icon") or ""),
                "enabled": bool(raw.get("enabled", True)),
            }
        )
    return options


def _normalize_scenarios(raw_scenarios: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_scenarios, list):
        return []
    scenarios: list[dict[str, Any]] = []
    for raw in raw_scenarios:
        if not isinstance(raw, dict):
            continue
        scenario = {
            "id": str(raw.get("id") or ""),
            "label": str(raw.get("label") or ""),
            "enabled": bool(raw.get("enabled", False)),
        }
        if raw.get("time_windows") is not None:
            scenario["time_windows"] = raw.get("time_windows") if isinstance(raw.get("time_windows"), list) else []
        if raw.get("options") is not None:
            scenario["options"] = _normalize_options(raw.get("options", []))
        if scenario["id"] and scenario["label"]:
            scenarios.append(scenario)
    return scenarios


def _step_options(questionnaire: dict[str, Any], *, step_id: str) -> list[dict[str, Any]]:
    aliases = {step_id, "want_now" if step_id == "food_desires" else step_id}
    for step in questionnaire.get("steps", []):
        if not isinstance(step, dict) or str(step.get("id")) not in aliases:
            continue
        return [option for option in step.get("options", []) if isinstance(option, dict) and option.get("enabled", True)]
    return []


def _public_options(raw_options: list[dict[str, Any]]) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for raw in raw_options:
        option_id = str(raw.get("id", "")).strip()
        label = str(raw.get("label", "")).strip()
        if option_id and label:
            options.append({"id": option_id, "label": label})
    return options


def _normalize_audit_log(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    rows: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "action": str(item.get("action") or ""),
                "version_id": str(item.get("version_id") or ""),
                "actor": str(item.get("actor") or ""),
                "reason": str(item.get("reason") or ""),
                "created_at": str(item.get("created_at") or ""),
            }
        )
    return rows


def _audit_row(action: str, version_id: str, *, actor: str, reason: str, at: str) -> dict[str, str]:
    return {
        "action": action,
        "version_id": version_id,
        "actor": actor or "admin",
        "reason": reason or "",
        "created_at": at,
    }


def _next_version_id(config: dict[str, Any]) -> str:
    versions = set(config.get("versions", {}).keys())
    numeric = [
        int(version[1:])
        for version in versions
        if isinstance(version, str) and version.startswith("v") and version[1:].isdigit()
    ]
    return f"v{(max(numeric) if numeric else 0) + 1}"


def _latest_version_id(versions: dict[str, Any]) -> str:
    numeric = [
        (int(version[1:]), version)
        for version in versions.keys()
        if isinstance(version, str) and version.startswith("v") and version[1:].isdigit()
    ]
    if numeric:
        return max(numeric, key=lambda item: item[0])[1]
    return sorted(versions.keys())[-1]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
