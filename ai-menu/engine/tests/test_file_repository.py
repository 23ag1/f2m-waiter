from pathlib import Path

import pytest

from app.domain.models import (
    ConstraintScope,
    Event,
    EventItem,
    ProfileLayer,
    UserConstraint,
    UserFeatureValue,
)
from app.repositories.file_repository import FileRepository


def test_upsert_user_constraint_rewrites_same_key(tmp_path: Path) -> None:
    repo = FileRepository(base_dir=tmp_path)
    row = UserConstraint(
        user_id=1,
        constraint_key="peanut",
        scope=ConstraintScope.HARD,
        source="questionnaire",
    )
    repo.upsert_user_constraint(row)

    updated = row.model_copy(update={"reason_text": "allergy"})
    repo.upsert_user_constraint(updated)

    lines = repo.user_constraints_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert "allergy" in lines[0]


def test_upsert_user_feature_enforces_layer_policy(tmp_path: Path) -> None:
    repo = FileRepository(base_dir=tmp_path)
    row = UserFeatureValue(
        user_id=1,
        profile_layer=ProfileLayer.EXPLICIT,
        axis="taste",
        feature_key="spicy",
        weight=0.4,
        source="event",
    )

    with pytest.raises(ValueError):
        repo.upsert_user_feature(row=row, source_is_event=True)


def test_write_questionnaire_submission_appends_jsonl(tmp_path: Path) -> None:
    repo = FileRepository(base_dir=tmp_path)
    repo.write_questionnaire_submission({"user_id": 1, "questionnaire_type": "seed_json"})
    repo.write_questionnaire_submission({"user_id": 2, "questionnaire_type": "seed_json"})

    lines = repo.questionnaire_submissions_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_event_idempotency_key_is_source_plus_uuid(tmp_path: Path) -> None:
    repo = FileRepository(base_dir=tmp_path)
    row = Event(
        source_system="cust_json",
        event_uuid="1.1",
        user_id=1,
        event_type="purchase_paid",
        object_type="order",
        object_id="1.1",
    )
    repo.upsert_event(row)
    repo.upsert_event(row.model_copy(update={"payload_json": {"retry": True}}))

    lines = repo.events_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert "retry" in lines[0]


def test_event_items_upsert_by_event_and_line(tmp_path: Path) -> None:
    repo = FileRepository(base_dir=tmp_path)
    row = EventItem(
        source_system="cust_json",
        event_uuid="1.1",
        line_no=1,
        dish_name="Dish",
        qty=1,
    )
    repo.upsert_event_item(row)
    repo.upsert_event_item(row.model_copy(update={"qty": 2}))

    lines = repo.event_items_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert '"qty": 2' in lines[0]
