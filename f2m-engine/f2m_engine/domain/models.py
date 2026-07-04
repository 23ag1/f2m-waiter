from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class ProfileLayer(str, Enum):
    EXPLICIT = "explicit"
    LONG_TERM = "long_term"
    SHORT_TERM = "short_term"


class ConstraintScope(str, Enum):
    HARD = "hard"
    SOFT = "soft"
    UNKNOWN = "unknown"


class UserConstraint(BaseModel):
    user_id: int
    constraint_key: str
    scope: ConstraintScope
    source: str
    reason_text: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class UserFeatureValue(BaseModel):
    user_id: int
    profile_layer: ProfileLayer
    axis: str
    feature_key: str
    weight: float = Field(ge=-1.0, le=1.0)
    source: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("axis")
    @classmethod
    def validate_axis(cls, value: str) -> str:
        allowed = {
            "taste",
            "ingredient",
            "cuisine",
            "format_texture",
            "context",
            "restriction",
            "nutrition",
        }
        if value not in allowed:
            raise ValueError(f"Unsupported axis: {value}")
        return value


class Event(BaseModel):
    source_system: str
    event_uuid: str
    user_id: int
    event_type: str
    object_type: str = "dish"
    object_id: str | None = None
    occurred_at: str | None = None
    payload_json: dict | None = None


class EventItem(BaseModel):
    source_system: str
    event_uuid: str
    line_no: int = Field(ge=1)
    dish_name: str
    qty: int = Field(default=1, ge=1)
    modifiers_json: dict | None = None
