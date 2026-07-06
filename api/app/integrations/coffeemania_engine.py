"""
Тонкий синхронный клиент f2m-engine (зона Димы, мы только зовём его HTTP API).

Движок в docker-сети доступен как http://f2m-engine:1488. Все вызовы с коротким
таймаутом; персонализация - best-effort, при недоступности движка адаптер
откатывается на cold-start.
"""
from __future__ import annotations

import os
import uuid

import httpx

ENGINE_URL = os.getenv("F2M_ENGINE_URL", "http://f2m-engine:1488").rstrip("/")
_TIMEOUT = float(os.getenv("F2M_ENGINE_TIMEOUT", "4.0"))


def score(user_id: int, top_k: int, context: dict | None = None) -> dict:
    """POST /recommendations/score. Бросает исключение при ошибке (ловит вызывающий)."""
    payload = {"user_id": int(user_id), "top_k": int(top_k), "context": context or {}}
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(f"{ENGINE_URL}/recommendations/score", json=payload)
        resp.raise_for_status()
        return resp.json()


def ingest_purchase(user_id: int, sku: str, event_uuid: str | None = None) -> None:
    """POST /events/ingest - кормит профиль событием покупки. Best-effort."""
    payload = {
        "source_system": "coffeemania",
        "event_uuid": event_uuid or str(uuid.uuid4()),
        "user_id": int(user_id),
        "event_type": "purchase_paid",
        "object_type": "dish",
        "object_id": str(sku),
        "payload_json": {},
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        client.post(f"{ENGINE_URL}/events/ingest", json=payload)


def send_outcome(engine_request_id: str, sku: str, outcome_type: str) -> None:
    """POST /recommendations/{id}/outcome - проброс исхода. Best-effort."""
    payload = {"dish_id": str(sku), "outcome": outcome_type}
    with httpx.Client(timeout=_TIMEOUT) as client:
        client.post(f"{ENGINE_URL}/recommendations/{engine_request_id}/outcome", json=payload)
