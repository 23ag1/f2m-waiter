"""Описание ЦВП профиля для ресторанной панели."""
from __future__ import annotations
from typing import Any


def age_to_range(age: Any) -> str:
    try:
        a = int(age)
    except (TypeError, ValueError):
        return str(age) if age else "—"
    if a < 18:
        return "до 18"
    if a <= 25:
        return "18–25"
    if a <= 35:
        return "26–35"
    if a <= 45:
        return "36–45"
    if a <= 55:
        return "46–55"
    return "56+"


def describe_profile_row(profile_row: dict[str, Any]) -> str:
    parts = []
    if profile_row.get("prefer"):
        parts.append(f"Любит: {profile_row['prefer']}")
    if profile_row.get("hate"):
        parts.append(f"Не любит: {profile_row['hate']}")
    if profile_row.get("style"):
        parts.append(f"Стиль: {profile_row['style']}")
    if profile_row.get("mood"):
        parts.append(f"Настроение: {profile_row['mood']}")
    return " · ".join(parts) if parts else "ЦВП пока не сформирован."
