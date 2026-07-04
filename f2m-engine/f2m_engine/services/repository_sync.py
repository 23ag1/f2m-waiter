from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from f2m_engine.repositories.postgres_repository import PostgresRepository


ENTITY_FILES = {
    "questionnaire_submissions": "questionnaire_submissions.jsonl",
    "user_constraints": "user_constraints.jsonl",
    "user_feature_values": "user_feature_values.jsonl",
    "events": "events.jsonl",
    "event_items": "event_items.jsonl",
    "dish_feature_values": "dish_feature_values.jsonl",
    "recommendation_requests": "recommendation_requests.jsonl",
    "recommendation_candidates": "recommendation_candidates.jsonl",
    "recommendation_outcomes": "recommendation_outcomes.jsonl",
    "ranking_dataset_rows": "ranking_dataset_rows.jsonl",
}


def apply_postgres_migrations(dsn: str, workspace_root: Path) -> None:
    repo = PostgresRepository(dsn=dsn)
    repo.execute_sql_file(str(workspace_root / "docs" / "food2mood_profile_schema_v2.sql"))
    migrations_dir = workspace_root / "db" / "migrations"
    for path in sorted(migrations_dir.glob("*.sql")):
        if path.name == "001_base_schema.sql":
            continue
        repo.execute_sql_file(str(path))


def import_derived_to_postgres(derived_dir: Path | str, dsn: str) -> dict[str, int]:
    derived = Path(derived_dir)
    repo = PostgresRepository(dsn=dsn)
    _ensure_seed_users(repo=repo, derived=derived)
    _ensure_seed_dishes(repo=repo, derived=derived)

    stats: dict[str, int] = {}
    for entity, filename in ENTITY_FILES.items():
        path = derived / filename
        rows = _read_jsonl(path)
        if entity == "questionnaire_submissions":
            for row in rows:
                repo.write_questionnaire_submission(row)
        elif entity == "user_constraints":
            for row in rows:
                repo.upsert_json_entity(
                    table="user_constraints",
                    key_columns=["user_id", "constraint_key"],
                    row={
                        "user_id": int(row["user_id"]),
                        "constraint_key": row["constraint_key"],
                        "constraint_kind": "other",
                        "scope": row.get("scope", "hard"),
                        "source": row.get("source", "seed_json"),
                        "reason_text": row.get("reason_text"),
                        "evidence_json": row,
                        "active": True,
                    },
                )
        elif entity == "user_feature_values":
            for row in rows:
                repo.upsert_json_entity(
                    table="user_feature_values",
                    key_columns=["user_id", "profile_layer", "axis", "feature_key"],
                    row={
                        "user_id": int(row["user_id"]),
                        "profile_layer": row["profile_layer"],
                        "axis": row["axis"],
                        "feature_key": row["feature_key"],
                        "weight": float(row["weight"]),
                        "source": row.get("source", "event"),
                        "confidence": row.get("confidence"),
                        "feature_version": "runtime_v1",
                    },
                )
        elif entity == "events":
            for row in rows:
                repo.upsert_json_entity(
                    table="events",
                    key_columns=["source_system", "event_uuid"],
                    row={
                        "source_system": row["source_system"],
                        "event_uuid": row["event_uuid"],
                        "user_id": int(row["user_id"]),
                        "event_type": row["event_type"],
                        "object_type": row.get("object_type", "dish"),
                        "object_id": row.get("object_id"),
                        "payload_json": row.get("payload_json", {}),
                        "occurred_at": row.get("occurred_at") or "2026-01-01T00:00:00+00:00",
                    },
                )
        elif entity == "event_items":
            for row in rows:
                repo.upsert_event_item(
                    row=type("EventItemProxy", (), {"model_dump": lambda self, mode="json", r=row: r})()
                )
        elif entity == "dish_feature_values":
            for row in rows:
                repo.upsert_json_entity(
                    table="dish_feature_values",
                    key_columns=["dish_id", "axis", "feature_key"],
                    row={
                        "dish_id": int(row["dish_id"]),
                        "axis": row["axis"],
                        "feature_key": row["feature_key"],
                        "value_num": row.get("value_num"),
                        "value_bool": row.get("value_bool"),
                        "source": row.get("source", "rule"),
                        "confidence": row.get("confidence"),
                        "feature_version": row.get("feature_version", "runtime_v1"),
                    },
                )
        elif entity == "recommendation_requests":
            for row in rows:
                repo.upsert_json_entity(
                    table="recommendation_requests",
                    key_columns=["recommendation_request_id"],
                    row=row,
                )
        elif entity == "recommendation_candidates":
            for row in rows:
                payload = {
                    **row,
                    "hard_filter_reasons": row.get("hard_filter_reasons", []),
                }
                repo.upsert_json_entity(
                    table="recommendation_candidates",
                    key_columns=["recommendation_request_id", "dish_id"],
                    row=payload,
                )
        elif entity == "recommendation_outcomes":
            for row in rows:
                repo.insert_json_entity(table="recommendation_outcomes", row=row)
        elif entity == "ranking_dataset_rows":
            for row in rows:
                repo.upsert_json_entity(
                    table="ranking_dataset_rows",
                    key_columns=["recommendation_request_id", "dish_id"],
                    row=row,
                )
        stats[entity] = len(rows)

    dish_cache = _read_json(derived / "dish_features_cache.json")
    for row in dish_cache:
        repo.upsert_json_entity(
            table="dish_features_cache",
            key_columns=["dish_id"],
            row={
                "dish_id": int(row["dish_id"]),
                "cache_json": row,
                "feature_version": row.get("meta", {}).get("feature_version", "runtime_v1"),
            },
        )
    user_profiles_cache = _read_json(derived / "user_profiles_cache.json")
    for row in user_profiles_cache:
        repo.upsert_json_entity(
            table="user_profiles_cache",
            key_columns=["user_id"],
            row={
                "user_id": int(row["user_id"]),
                "cache_json": row,
                "profile_version": row.get("meta", {}).get("feature_version", "runtime_v1"),
            },
        )
    stats["dish_features_cache"] = len(dish_cache)
    stats["user_profiles_cache"] = len(user_profiles_cache)
    return stats


def export_postgres_to_derived(derived_dir: Path | str, dsn: str) -> dict[str, int]:
    derived = Path(derived_dir)
    derived.mkdir(parents=True, exist_ok=True)
    repo = PostgresRepository(dsn=dsn)
    stats: dict[str, int] = {}
    order = {
        "questionnaire_submissions": "submission_id",
        "user_constraints": "user_id, constraint_key",
        "user_feature_values": "user_id, profile_layer, axis, feature_key",
        "events": "event_pk",
        "event_items": "event_pk, line_no",
        "dish_feature_values": "dish_id, axis, feature_key",
        "recommendation_requests": "recommendation_request_id",
        "recommendation_candidates": "recommendation_request_id, rank_position",
        "recommendation_outcomes": "outcome_id",
        "ranking_dataset_rows": "recommendation_request_id, rank_position, dish_id",
    }
    for entity, filename in ENTITY_FILES.items():
        rows = repo.fetch_all(entity, order_by=order.get(entity))
        _write_jsonl(derived / filename, _jsonify_rows(rows))
        stats[entity] = len(rows)

    dish_cache_rows = repo.fetch_all("dish_features_cache", order_by="dish_id")
    _write_json(derived / "dish_features_cache.json", [row["cache_json"] for row in dish_cache_rows])
    stats["dish_features_cache"] = len(dish_cache_rows)

    profile_cache_rows = repo.fetch_all("user_profiles_cache", order_by="user_id")
    _write_json(derived / "user_profiles_cache.json", [row["cache_json"] for row in profile_cache_rows])
    stats["user_profiles_cache"] = len(profile_cache_rows)
    return stats


def verify_repository_equivalence(derived_dir: Path | str, dsn: str) -> list[dict[str, Any]]:
    derived = Path(derived_dir)
    temp_export = derived / "_tmp_pg_export"
    export_postgres_to_derived(temp_export, dsn)
    rows: list[dict[str, Any]] = []

    all_files = sorted(
        set([*ENTITY_FILES.values(), "dish_features_cache.json", "user_profiles_cache.json"])
    )
    for filename in all_files:
        left = _canonical_content(derived / filename)
        right = _canonical_content(temp_export / filename)
        rows.append(
            {
                "entity_file": filename,
                "file_exists_in_source": (derived / filename).exists(),
                "file_exists_in_postgres_export": (temp_export / filename).exists(),
                "source_rows": _row_count(derived / filename),
                "postgres_rows": _row_count(temp_export / filename),
                "logical_equivalent": left == right,
            }
        )
    return rows


def postgres_row_counts(dsn: str) -> list[dict[str, Any]]:
    repo = PostgresRepository(dsn=dsn)
    tables = [
        "questionnaire_submissions",
        "user_constraints",
        "user_feature_values",
        "events",
        "event_items",
        "dish_feature_values",
        "dish_features_cache",
        "user_profiles_cache",
        "recommendation_requests",
        "recommendation_candidates",
        "recommendation_outcomes",
        "ranking_dataset_rows",
    ]
    rows: list[dict[str, Any]] = []
    for table in tables:
        count = len(repo.fetch_all(table))
        rows.append({"table_name": table, "row_count": count})
    return rows


def write_csv_report(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", encoding="utf-8", newline="") as file_obj:
            file_obj.write("")
        return
    headers = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _ensure_seed_users(repo: PostgresRepository, derived: Path) -> None:
    users: set[int] = set()
    for filename in ("questionnaire_submissions.jsonl", "events.jsonl", "user_constraints.jsonl", "user_feature_values.jsonl"):
        for row in _read_jsonl(derived / filename):
            if "user_id" in row:
                users.add(int(row["user_id"]))
    for user_id in sorted(users):
        repo.upsert_json_entity(
            table="users",
            key_columns=["user_id"],
            row={"user_id": user_id},
        )


def _ensure_seed_dishes(repo: PostgresRepository, derived: Path) -> None:
    dish_cache = _read_json(derived / "dish_features_cache.json")
    for row in dish_cache:
        dish_id = int(row["dish_id"])
        dish_name = row.get("meta", {}).get("name", f"dish_{dish_id}")
        repo.upsert_json_entity(
            table="dishes",
            key_columns=["dish_id"],
            row={"dish_id": dish_id, "dish_name": dish_name},
        )


def _canonical_content(path: Path) -> list[str]:
    if not path.exists():
        return []
    if path.suffix == ".jsonl":
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return sorted(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return sorted(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in payload)
        return [json.dumps(payload, ensure_ascii=False, sort_keys=True)]
    return [path.read_text(encoding="utf-8")]


def _row_count(path: Path) -> int:
    if not path.exists():
        return 0
    if path.suffix == ".jsonl":
        return len([line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return len(payload) if isinstance(payload, list) else 1
    return 1


def _jsonify_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        normalized: dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, (dict, list)):
                normalized[key] = value
            elif hasattr(value, "isoformat"):
                normalized[key] = value.isoformat()
            else:
                normalized[key] = value
        result.append(normalized)
    return result


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _read_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return [payload]


def _write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file_obj:
        for row in rows:
            file_obj.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
