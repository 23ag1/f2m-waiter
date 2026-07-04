from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from f2m_engine.domain.models import Event, EventItem
from f2m_engine.repositories.base import Repository


@dataclass(frozen=True)
class EventIngestionStats:
    users_processed: int
    events_written: int
    items_written: int


def ingest_seed_purchase_events(
    users_path: Path | str,
    repository: Repository,
) -> EventIngestionStats:
    with Path(users_path).open("r", encoding="utf-8") as file_obj:
        payload = json.load(file_obj)

    users = payload.get("users", [])
    events_written = 0
    items_written = 0

    for user in users:
        user_id = int(user["user_id"])
        orders = user.get("orders", [])
        for order in orders:
            event_uuid = str(order["transaction_id"])
            event = Event(
                source_system="cust_json",
                event_uuid=event_uuid,
                user_id=user_id,
                event_type="purchase_paid",
                object_type="order",
                object_id=event_uuid,
                payload_json={
                    "dish": order.get("dish"),
                    "context": order.get("context"),
                    "ingredients": order.get("ingredients"),
                    "flavor_profile": order.get("flavor_profile"),
                },
            )
            repository.upsert_event(event)
            events_written += 1

            item = EventItem(
                source_system="cust_json",
                event_uuid=event_uuid,
                line_no=1,
                dish_name=str(order.get("dish", "")),
                qty=1,
                modifiers_json={"seed_context": order.get("context")},
            )
            repository.upsert_event_item(item)
            items_written += 1

    return EventIngestionStats(
        users_processed=len(users),
        events_written=events_written,
        items_written=items_written,
    )
