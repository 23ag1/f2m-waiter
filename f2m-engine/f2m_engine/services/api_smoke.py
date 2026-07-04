from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from f2m_engine.api import create_app
from f2m_engine.repositories.postgres_repository import PostgresRepository
from f2m_engine.services.repository_sync import write_csv_report


def run_api_smoke(dsn: str, derived_dir: Path | str) -> list[dict[str, Any]]:
    app = create_app(dsn=dsn, derived_dir=str(derived_dir))
    client = TestClient(app)
    rows: list[dict[str, Any]] = []

    response = client.post(
        "/events/ingest",
        json={
            "source_system": "api_smoke",
            "event_uuid": "smoke-1",
            "user_id": 1,
            "event_type": "purchase_paid",
            "object_type": "order",
            "object_id": "smoke-1",
            "payload_json": {"dish": "Test dish", "context": "Обед"},
            "item": {"line_no": 1, "dish_name": "Test dish", "qty": 1},
        },
    )
    rows.append({"endpoint": "POST /events/ingest", "status_code": response.status_code, "ok": response.status_code == 200})

    response = client.post(
        "/questionnaire/submit",
        json={
            "user_id": 1,
            "questionnaire_type": "manual",
            "raw_answers_json": {"likes": ["asian"]},
            "hard_constraints": [{"constraint_key": "peanut", "scope": "hard"}],
            "explicit_features": [{"axis": "cuisine", "feature_key": "asian", "weight": 0.7}],
        },
    )
    rows.append({"endpoint": "POST /questionnaire/submit", "status_code": response.status_code, "ok": response.status_code == 200})

    response = client.post("/profiles/rebuild")
    rows.append({"endpoint": "POST /profiles/rebuild", "status_code": response.status_code, "ok": response.status_code == 200})

    response = client.get("/profiles/1")
    rows.append({"endpoint": "GET /profiles/{user_id}", "status_code": response.status_code, "ok": response.status_code == 200})

    response = client.post("/recommendations/score", json={"user_id": 1, "top_k": 5, "context": {"time_of_day": "lunch"}})
    rows.append({"endpoint": "POST /recommendations/score", "status_code": response.status_code, "ok": response.status_code == 200})
    request_id = response.json().get("request_id")
    first_dish = None
    results = response.json().get("results", [])
    if results:
        first_dish = str(results[0]["dish_id"])

    if request_id and first_dish:
        response = client.post(
            f"/recommendations/{request_id}/outcome",
            json={"dish_id": first_dish, "outcome": "viewed_details"},
        )
        rows.append({"endpoint": "POST /recommendations/{request_id}/outcome", "status_code": response.status_code, "ok": response.status_code == 200})
        response = client.get(f"/recommendations/{request_id}")
        rows.append({"endpoint": "GET /recommendations/{request_id}", "status_code": response.status_code, "ok": response.status_code == 200})

    response = client.post("/ranking/build-dataset")
    rows.append({"endpoint": "POST /ranking/build-dataset", "status_code": response.status_code, "ok": response.status_code == 200})
    return rows


def run_ingest_idempotency_check(dsn: str) -> list[dict[str, Any]]:
    repo = PostgresRepository(dsn=dsn)
    now = datetime.now(timezone.utc).isoformat()
    event_row = {
        "source_system": "idempotency_check",
        "event_uuid": "idem-1",
        "user_id": 1,
        "event_type": "purchase_paid",
        "object_type": "order",
        "object_id": "idem-1",
        "payload_json": {"dish": "Idempotent dish"},
        "occurred_at": now,
    }
    before = len(repo.fetch_all("events"))
    repo.upsert_json_entity(table="users", key_columns=["user_id"], row={"user_id": 1})
    repo.upsert_json_entity(table="events", key_columns=["source_system", "event_uuid"], row=event_row)
    middle = len(repo.fetch_all("events"))
    repo.upsert_json_entity(table="events", key_columns=["source_system", "event_uuid"], row=event_row)
    after = len(repo.fetch_all("events"))
    return [
        {
            "metric": "events_before",
            "value": before,
        },
        {
            "metric": "events_after_first_ingest",
            "value": middle,
        },
        {
            "metric": "events_after_second_ingest",
            "value": after,
        },
        {
            "metric": "idempotent",
            "value": (after == middle),
        },
    ]


def write_smoke_reports(derived_dir: Path | str, api_rows: list[dict[str, Any]], idem_rows: list[dict[str, Any]]) -> None:
    audit_dir = Path(derived_dir) / "audit"
    write_csv_report(audit_dir / "api_smoke_report.csv", api_rows)
    write_csv_report(audit_dir / "ingest_idempotency_report.csv", idem_rows)
