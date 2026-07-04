"""
Преобразование БД-профиля пользователя в UserFeatureBag — контейнер
NormalizedFeature, сгруппированных по осям, готовых к скорингу.

Идёт через уже существующий mapper (фаза R1), ничего не изобретая.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.taxonomy import (
    NormalizedFeature,
    normalize_avoid,
    normalize_food_desires,
    normalize_hate,
    normalize_hunger,
    normalize_novelty,
    normalize_preferences,
)


@dataclass(frozen=True, slots=True)
class UserFeatureBag:
    """
    Контейнер замапленных предпочтений юзера. Ключ — axis, значение —
    {feature_key: signed_weight} (+ для pos, - для neg).

    Пустой bag = "юзер не ответил" → ranker вернёт дефолтный порядок.
    """
    by_axis: dict[str, dict[str, float]] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not any(self.by_axis.values())

    def get_weight(self, axis: str, feature_key: str) -> float:
        """Подписанный вес (0.0 если ключа нет)."""
        return self.by_axis.get(axis, {}).get(feature_key, 0.0)


def _apply(bag_dict: dict[str, dict[str, float]], features: list[NormalizedFeature]) -> None:
    """Добавляет features в bag_dict, накапливая веса при дубликатах."""
    for f in features:
        axis_map = bag_dict.setdefault(f.axis, {})
        signed = f.weight if f.polarity == "pos" else -f.weight
        # При повторах выбираем максимум по модулю — аллергия не должна
        # случайно ослабнуть от второго упоминания.
        prev = axis_map.get(f.feature_key, 0.0)
        if abs(signed) > abs(prev):
            axis_map[f.feature_key] = signed


def profile_to_features(profile: dict[str, Any] | None) -> UserFeatureBag:
    """
    Читает поля профиля из БД и прогоняет через маппер:
    - hate (JSONB list[str]) → restriction (neg)
    - preferences (JSONB)    → restriction + nutrition
    - avoid (JSONB)          → restriction + ingredient + taste
    - novelty (str)          → meta.novelty
    - prefer (JSONB)         → short-term goal на ingredient/taste/context/format
    - hungry (str)           → nutrition.satiety_class

    None или пустой профиль → пустой bag.
    """
    bag: dict[str, dict[str, float]] = {}
    if not profile:
        return UserFeatureBag(by_axis=bag)

    hate = profile.get("hate") or []
    preferences = profile.get("preferences") or []
    avoid = profile.get("avoid") or []
    prefer = profile.get("prefer") or []
    novelty = profile.get("novelty")
    hungry = profile.get("hungry")

    _apply(bag, normalize_hate(hate))
    _apply(bag, normalize_preferences(preferences))
    _apply(bag, normalize_avoid(avoid))
    _apply(bag, normalize_food_desires(prefer))

    if novelty_feat := normalize_novelty(novelty):
        _apply(bag, [novelty_feat])
    if hunger_feat := normalize_hunger(hungry):
        _apply(bag, [hunger_feat])

    return UserFeatureBag(by_axis=bag)
