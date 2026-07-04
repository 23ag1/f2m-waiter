from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from f2m_engine.domain.models import Event, EventItem, UserConstraint, UserFeatureValue


class Repository(ABC):
    @abstractmethod
    def write_questionnaire_submission(self, row: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def upsert_user_constraint(self, row: UserConstraint) -> None:
        pass

    @abstractmethod
    def upsert_user_feature(self, row: UserFeatureValue, source_is_event: bool) -> None:
        pass

    @abstractmethod
    def upsert_event(self, row: Event) -> None:
        pass

    @abstractmethod
    def upsert_event_item(self, row: EventItem) -> None:
        pass
