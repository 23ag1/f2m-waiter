from __future__ import annotations

import json
from typing import Any

import psycopg

from f2m_engine.domain.models import Event, EventItem, UserConstraint, UserFeatureValue
from f2m_engine.domain.policy import ensure_profile_layer_policy
from f2m_engine.repositories.base import Repository


class PostgresRepository(Repository):
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def write_questionnaire_submission(self, row: dict[str, Any]) -> None:
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into questionnaire_submissions
                    (user_id, questionnaire_type, source_system, raw_answers_json, extracted_json, extractor_version)
                    values (%s, %s, %s, %s::jsonb, %s::jsonb, %s)
                    """,
                    (
                        int(row["user_id"]),
                        row.get("questionnaire_type", "seed_json"),
                        row.get("source_system", "local"),
                        json.dumps(row.get("raw_answers_json", {}), ensure_ascii=False),
                        json.dumps(row.get("extracted_json", {}), ensure_ascii=False),
                        row.get("extractor_version", "runtime_v1"),
                    ),
                )

    def upsert_user_constraint(self, row: UserConstraint) -> None:
        payload = row.model_dump(mode="json")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into user_constraints
                    (user_id, constraint_key, constraint_kind, scope, source, reason_text, evidence_json, active)
                    values (%s, %s, %s, %s, %s, %s, %s::jsonb, true)
                    on conflict (user_id, constraint_key)
                    do update set
                      scope = excluded.scope,
                      source = excluded.source,
                      reason_text = excluded.reason_text,
                      evidence_json = excluded.evidence_json,
                      updated_at = now()
                    """,
                    (
                        int(payload["user_id"]),
                        payload["constraint_key"],
                        "other",
                        payload["scope"],
                        payload["source"],
                        payload.get("reason_text"),
                        json.dumps({"confidence": payload.get("confidence")}, ensure_ascii=False),
                    ),
                )

    def upsert_user_feature(self, row: UserFeatureValue, source_is_event: bool) -> None:
        ensure_profile_layer_policy(feature=row, source_is_event=source_is_event)
        payload = row.model_dump(mode="json")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into user_feature_values
                    (user_id, profile_layer, axis, feature_key, weight, source, confidence, feature_version)
                    values (%s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (user_id, profile_layer, axis, feature_key)
                    do update set
                      weight = excluded.weight,
                      source = excluded.source,
                      confidence = excluded.confidence,
                      feature_version = excluded.feature_version,
                      updated_at = now()
                    """,
                    (
                        int(payload["user_id"]),
                        payload["profile_layer"],
                        payload["axis"],
                        payload["feature_key"],
                        float(payload["weight"]),
                        payload["source"],
                        payload.get("confidence"),
                        "runtime_v1",
                    ),
                )

    def upsert_event(self, row: Event) -> None:
        payload = row.model_dump(mode="json")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into events
                    (source_system, event_uuid, user_id, event_type, object_type, object_id, payload_json, occurred_at)
                    values (%s, %s, %s, %s, %s, %s, %s::jsonb, coalesce(%s::timestamptz, now()))
                    on conflict (source_system, event_uuid)
                    do update set
                      event_type = excluded.event_type,
                      object_type = excluded.object_type,
                      object_id = excluded.object_id,
                      payload_json = excluded.payload_json,
                      occurred_at = excluded.occurred_at
                    """,
                    (
                        payload["source_system"],
                        payload["event_uuid"],
                        int(payload["user_id"]),
                        payload["event_type"],
                        payload.get("object_type", "dish"),
                        payload.get("object_id"),
                        json.dumps(payload.get("payload_json", {}), ensure_ascii=False),
                        payload.get("occurred_at"),
                    ),
                )

    def upsert_event_item(self, row: EventItem) -> None:
        payload = row.model_dump(mode="json")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select event_pk from events where source_system = %s and event_uuid = %s",
                    (payload["source_system"], payload["event_uuid"]),
                )
                event_pk_row = cur.fetchone()
                if not event_pk_row:
                    return
                event_pk = event_pk_row[0]
                cur.execute(
                    """
                    insert into event_items
                    (event_pk, line_no, dish_name, qty, modifiers_json)
                    values (%s, %s, %s, %s, %s::jsonb)
                    on conflict (event_pk, line_no)
                    do update set
                      dish_name = excluded.dish_name,
                      qty = excluded.qty,
                      modifiers_json = excluded.modifiers_json
                    """,
                    (
                        event_pk,
                        int(payload["line_no"]),
                        payload["dish_name"],
                        int(payload.get("qty", 1)),
                        json.dumps(payload.get("modifiers_json", {}), ensure_ascii=False),
                    ),
                )

    def upsert_json_entity(self, table: str, key_columns: list[str], row: dict[str, Any]) -> None:
        columns = list(row.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        set_clause = ", ".join(
            f"{column}=excluded.{column}"
            for column in columns
            if column not in key_columns
        )
        if set_clause:
            sql = (
                f"insert into {table} ({', '.join(columns)}) values ({placeholders}) "
                f"on conflict ({', '.join(key_columns)}) do update set {set_clause}"
            )
        else:
            sql = (
                f"insert into {table} ({', '.join(columns)}) values ({placeholders}) "
                f"on conflict ({', '.join(key_columns)}) do nothing"
            )
        values = [json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for v in row.values()]
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, values)

    def insert_json_entity(self, table: str, row: dict[str, Any]) -> None:
        columns = list(row.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        sql = f"insert into {table} ({', '.join(columns)}) values ({placeholders})"
        values = [json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for v in row.values()]
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, values)

    def fetch_all(self, table: str, order_by: str | None = None) -> list[dict[str, Any]]:
        sql = f"select * from {table}"
        if order_by:
            sql += f" order by {order_by}"
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute(sql)
                rows = cur.fetchall()
                return [dict(row) for row in rows]

    def execute_sql_file(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as file_obj:
            sql = file_obj.read()
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
