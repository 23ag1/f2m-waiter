from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from f2m_engine.domain.models import Event, EventItem, UserConstraint, UserFeatureValue
from f2m_engine.domain.policy import ensure_profile_layer_policy
from f2m_engine.repositories.base import Repository


class FileRepository(Repository):
    def __init__(self, base_dir: Path | str = "data/derived") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.questionnaire_submissions_path = self.base_dir / "questionnaire_submissions.jsonl"
        self.user_constraints_path = self.base_dir / "user_constraints.jsonl"
        self.user_features_path = self.base_dir / "user_feature_values.jsonl"
        self.events_path = self.base_dir / "events.jsonl"
        self.event_items_path = self.base_dir / "event_items.jsonl"

    def write_questionnaire_submission(self, row: dict[str, Any]) -> None:
        self._append_jsonl(self.questionnaire_submissions_path, row)

    def upsert_user_constraint(self, row: UserConstraint) -> None:
        records = self._read_jsonl(self.user_constraints_path)
        key = (row.user_id, row.constraint_key)
        payload = row.model_dump(mode="json")

        self._upsert_records(
            records=records,
            key_fn=lambda item: (item["user_id"], item["constraint_key"]),
            upsert_key=key,
            payload=payload,
            output_path=self.user_constraints_path,
        )

    def upsert_user_feature(self, row: UserFeatureValue, source_is_event: bool) -> None:
        ensure_profile_layer_policy(feature=row, source_is_event=source_is_event)

        records = self._read_jsonl(self.user_features_path)
        key = (row.user_id, row.profile_layer.value, row.axis, row.feature_key)
        payload = row.model_dump(mode="json")
        payload["profile_layer"] = row.profile_layer.value

        self._upsert_records(
            records=records,
            key_fn=lambda item: (
                item["user_id"],
                item["profile_layer"],
                item["axis"],
                item["feature_key"],
            ),
            upsert_key=key,
            payload=payload,
            output_path=self.user_features_path,
        )

    def upsert_event(self, row: Event) -> None:
        records = self._read_jsonl(self.events_path)
        payload = row.model_dump(mode="json")
        key = (row.source_system, row.event_uuid)
        self._upsert_records(
            records=records,
            key_fn=lambda item: (item["source_system"], item["event_uuid"]),
            upsert_key=key,
            payload=payload,
            output_path=self.events_path,
        )

    def upsert_event_item(self, row: EventItem) -> None:
        records = self._read_jsonl(self.event_items_path)
        payload = row.model_dump(mode="json")
        key = (row.source_system, row.event_uuid, row.line_no)
        self._upsert_records(
            records=records,
            key_fn=lambda item: (
                item["source_system"],
                item["event_uuid"],
                item["line_no"],
            ),
            upsert_key=key,
            payload=payload,
            output_path=self.event_items_path,
        )

    def _append_jsonl(self, path: Path, row: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as file_obj:
            file_obj.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []

        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as file_obj:
            for line in file_obj:
                stripped = line.strip()
                if not stripped:
                    continue
                rows.append(json.loads(stripped))
        return rows

    def _upsert_records(
        self,
        records: list[dict[str, Any]],
        key_fn: Callable[[dict[str, Any]], tuple[Any, ...]],
        upsert_key: Any,
        payload: dict[str, Any],
        output_path: Path,
    ) -> None:
        indexed: dict[Any, dict[str, Any]] = {key_fn(record): record for record in records}
        indexed[upsert_key] = payload
        ordered = [indexed[key] for key in sorted(indexed.keys())]

        with output_path.open("w", encoding="utf-8") as file_obj:
            for row in ordered:
                file_obj.write(json.dumps(row, ensure_ascii=False) + "\n")
