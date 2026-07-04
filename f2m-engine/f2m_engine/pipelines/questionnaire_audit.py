from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path


REQUIRED_HARD_USERS = {1, 3, 5, 8, 9}


@dataclass(frozen=True)
class QuestionnaireAuditStats:
    hard_constraints_total: int
    users_with_hard_constraints: dict[int, int]
    soft_features_total: int
    unmapped_phrases_total: int
    events_total: int


def run_questionnaire_audit(
    source_users_path: Path | str,
    derived_dir: Path | str = "data/derived",
) -> QuestionnaireAuditStats:
    derived_path = Path(derived_dir)
    audit_dir = derived_path / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    users_payload = json.loads(Path(source_users_path).read_text(encoding="utf-8"))
    users = users_payload.get("users", [])

    constraints = _read_jsonl(derived_path / "user_constraints.jsonl")
    features = _read_jsonl(derived_path / "user_feature_values.jsonl")
    events = _read_jsonl(derived_path / "events.jsonl")
    event_items = _read_jsonl(derived_path / "event_items.jsonl")

    hard_constraints = [row for row in constraints if row.get("scope") == "hard"]
    soft_features = [row for row in features if row.get("profile_layer") == "explicit"]
    hard_by_user = _count_by_user(hard_constraints)
    soft_by_user = _group_features_by_user(soft_features)

    _write_csv(
        audit_dir / "questionnaire_constraints_by_user.csv",
        headers=["user_id", "constraint_key", "scope", "source", "reason_text", "confidence"],
        rows=[
            [
                row.get("user_id"),
                row.get("constraint_key"),
                row.get("scope"),
                row.get("source"),
                row.get("reason_text"),
                row.get("confidence"),
            ]
            for row in hard_constraints
        ],
    )

    _write_csv(
        audit_dir / "questionnaire_features_by_user.csv",
        headers=["user_id", "profile_layer", "axis", "feature_key", "weight", "source", "confidence"],
        rows=[
            [
                row.get("user_id"),
                row.get("profile_layer"),
                row.get("axis"),
                row.get("feature_key"),
                row.get("weight"),
                row.get("source"),
                row.get("confidence"),
            ]
            for row in soft_features
        ],
    )

    unmapped_rows = _collect_unmapped_phrases(users)
    _write_csv(
        audit_dir / "questionnaire_unmapped_phrases.csv",
        headers=["user_id", "phrase_type", "phrase_text", "normalized_phrase", "reason"],
        rows=unmapped_rows,
    )

    events_by_user = _count_by_user(events)
    items_by_user = _count_items_by_user(event_items=event_items, events=events)
    _write_csv(
        audit_dir / "seed_events_summary.csv",
        headers=["user_id", "event_count", "event_item_count"],
        rows=[
            [user["user_id"], events_by_user.get(user["user_id"], 0), items_by_user.get(user["user_id"], 0)]
            for user in users
        ],
    )

    _print_console_summary(hard_by_user=hard_by_user, soft_by_user=soft_by_user)
    _run_sanity_gate(hard_constraints=hard_constraints, hard_by_user=hard_by_user)

    return QuestionnaireAuditStats(
        hard_constraints_total=len(hard_constraints),
        users_with_hard_constraints=hard_by_user,
        soft_features_total=len(soft_features),
        unmapped_phrases_total=len(unmapped_rows),
        events_total=len(events),
    )


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as file_obj:
        for line in file_obj:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _write_csv(path: Path, headers: list[str], rows: list[list]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(headers)
        writer.writerows(rows)


def _count_by_user(rows: list[dict]) -> dict[int, int]:
    result: dict[int, int] = {}
    for row in rows:
        user_id = int(row["user_id"])
        result[user_id] = result.get(user_id, 0) + 1
    return result


def _group_features_by_user(rows: list[dict]) -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    for row in rows:
        user_id = int(row["user_id"])
        result.setdefault(user_id, []).append(f"{row['axis']}:{row['feature_key']}={row['weight']}")
    return result


def _count_items_by_user(event_items: list[dict], events: list[dict]) -> dict[int, int]:
    event_to_user: dict[tuple[str, str], int] = {}
    for event in events:
        event_to_user[(event["source_system"], event["event_uuid"])] = int(event["user_id"])

    result: dict[int, int] = {}
    for item in event_items:
        key = (item["source_system"], item["event_uuid"])
        user_id = event_to_user.get(key)
        if user_id is None:
            continue
        result[user_id] = result.get(user_id, 0) + 1
    return result


def _collect_unmapped_phrases(users: list[dict]) -> list[list]:
    tracked_markers = (
        "аллерг",
        "неперенос",
        "смертель",
        "арахис",
        "лактоз",
        "молочк",
        "глютен",
        "орех",
        "яйц",
        "соев",
        "рыб",
        "морепродукт",
        "свинин",
        "субпродукт",
        "халял",
        "веган",
        "вегетариан",
        "белк",
        "полезн",
        "ази",
        "итальян",
        "грузин",
        "кавказ",
        "выпечк",
        "легк",
        "сахар",
        "сладк",
        "фритюр",
        "лук",
        "гриб",
        "alpha-gal",
        "красное мясо",
    )
    rows: list[list] = []
    for user in users:
        user_id = int(user["user_id"])
        questionnaire = user.get("questionnaire", {})
        for phrase_type in ("likes", "dislikes"):
            for phrase in questionnaire.get(phrase_type, []):
                normalized = phrase.lower().replace("ё", "е").strip()
                if any(marker in normalized for marker in tracked_markers):
                    continue
                rows.append([user_id, phrase_type, phrase, normalized, "no deterministic rule matched"])
    return rows


def _print_console_summary(hard_by_user: dict[int, int], soft_by_user: dict[int, list[str]]) -> None:
    user_ids = sorted(set(hard_by_user.keys()) | set(soft_by_user.keys()))
    for user_id in user_ids:
        print(f"user {user_id} hard_constraints_count={hard_by_user.get(user_id, 0)}")
        print(f"user {user_id} soft_features={soft_by_user.get(user_id, [])}")


def _run_sanity_gate(hard_constraints: list[dict], hard_by_user: dict[int, int]) -> None:
    if len(hard_constraints) < len(REQUIRED_HARD_USERS):
        raise RuntimeError(
            f"Sanity gate failed: total hard constraints too low ({len(hard_constraints)})"
        )

    missing = sorted(user_id for user_id in REQUIRED_HARD_USERS if hard_by_user.get(user_id, 0) < 1)
    if missing:
        raise RuntimeError(
            "Sanity gate failed: required users missing hard constraints: "
            + ",".join(str(user_id) for user_id in missing)
        )
