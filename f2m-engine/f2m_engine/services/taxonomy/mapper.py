"""
Маппер: преобразует ответы анкет (русские UI-лейблы / англ. коды tablet)
в канонические NormalizedFeature для ML-движка.

Контракт:
- На вход — только то, что реально приходит с phone/tablet (см. dictionary.py).
- На выход — list[NormalizedFeature] с axis из feature_keys.AXIS_*.
- Unmapped значения НЕ падают, а возвращают None из match и логируются WARN.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Optional

from app.services.taxonomy import feature_keys as fk
from app.services.taxonomy.dictionary import (
    AVOID_SOFT_NEG_INDEX,
    AVOID_TASTE_NEG_INDEX,
    HUNGER_INDEX,
    INSTORE_GOAL_INDEX,
    NUTRITION_INDEX,
    RESTRICTION_INDEX,
    normalize_form,
)

log = logging.getLogger(__name__)

Polarity = Literal["pos", "neg"]


@dataclass(frozen=True, slots=True)
class NormalizedFeature:
    axis: str           # AXIS_RESTRICTION / AXIS_NUTRITION / AXIS_INGREDIENT / ...
    feature_key: str    # каноничный ключ из feature_keys.*
    weight: float       # знак учитывает polarity; модуль — сила
    polarity: Polarity  # "pos" = юзер любит, "neg" = избегает

    def __post_init__(self) -> None:
        # Strict guard: разваливание таксономии → видимый error-лог.
        if not fk.is_valid(self.axis, self.feature_key):
            log.error(
                "taxonomy: invalid (axis=%s, feature_key=%s) — not in runtime_taxonomy",
                self.axis, self.feature_key,
            )


def _match(value: str, index: dict[str, str]) -> Optional[str]:
    """Lookup по индексу с нормализацией. None если не найдено."""
    return index.get(normalize_form(value))


# ──────────────────────────────────────────────────────────────────────
# Phone TasteStep1 — аллергии
# ──────────────────────────────────────────────────────────────────────

def normalize_hate(values: list[str]) -> list[NormalizedFeature]:
    """
    Аллергии → restriction (hard constraint, weight=1.0, polarity=neg).
    «Нет, всё хорошо» и подобные никогда не приходят (фронт их фильтрует).
    """
    out: list[NormalizedFeature] = []
    for v in values:
        key = _match(v, RESTRICTION_INDEX)
        if key is None:
            log.warning("taxonomy: unmapped hate value %r", v)
            continue
        out.append(NormalizedFeature(
            axis=fk.AXIS_RESTRICTION, feature_key=key, weight=1.0, polarity="neg",
        ))
    return out


# ──────────────────────────────────────────────────────────────────────
# Phone TasteStep2 — долгосрочные пищевые предпочтения
# ──────────────────────────────────────────────────────────────────────

def normalize_preferences(values: list[str]) -> list[NormalizedFeature]:
    """
    Pазделяет между двумя осями:
    - Вегетарианство / Без сахара → restriction (weight=1.0, polarity=neg — «без этого»)
    - Мало калорий / Много белка → nutrition (weight=0.9, polarity=pos — цель)
    """
    out: list[NormalizedFeature] = []
    for v in values:
        if key := _match(v, RESTRICTION_INDEX):
            out.append(NormalizedFeature(
                axis=fk.AXIS_RESTRICTION, feature_key=key, weight=1.0, polarity="neg",
            ))
            continue
        if key := _match(v, NUTRITION_INDEX):
            out.append(NormalizedFeature(
                axis=fk.AXIS_NUTRITION, feature_key=key, weight=0.9, polarity="pos",
            ))
            continue
        log.warning("taxonomy: unmapped preference value %r", v)
    return out


# ──────────────────────────────────────────────────────────────────────
# Phone TasteStep3 — продукты к избеганию
# ──────────────────────────────────────────────────────────────────────

def normalize_avoid(values: list[str]) -> list[NormalizedFeature]:
    """
    Разделяет между тремя осями (см. questionnaire_mapping.csv:13-18):
    - Свинина / Рыба / Субпродукты → restriction (weight=1.0, polarity=neg)
    - Грибы / Лук → ingredient (weight=0.8, polarity=neg)
    - Острое → taste.spicy (weight=0.8, polarity=neg) — soft penalty, не hard-ban
    """
    out: list[NormalizedFeature] = []
    for v in values:
        if key := _match(v, RESTRICTION_INDEX):
            out.append(NormalizedFeature(
                axis=fk.AXIS_RESTRICTION, feature_key=key, weight=1.0, polarity="neg",
            ))
            continue
        if key := _match(v, AVOID_SOFT_NEG_INDEX):
            out.append(NormalizedFeature(
                axis=fk.AXIS_INGREDIENT, feature_key=key, weight=0.8, polarity="neg",
            ))
            continue
        if key := _match(v, AVOID_TASTE_NEG_INDEX):
            out.append(NormalizedFeature(
                axis=fk.AXIS_TASTE, feature_key=key, weight=0.8, polarity="neg",
            ))
            continue
        log.warning("taxonomy: unmapped avoid value %r", v)
    return out


# ──────────────────────────────────────────────────────────────────────
# Phone TasteStep4 — novelty
# ──────────────────────────────────────────────────────────────────────

_NOVELTY_WEIGHTS: dict[str, float] = {
    "like": 0.7,
    "dislike": -0.7,
    "mixed": 0.0,
}


def normalize_novelty(value: str | None) -> Optional[NormalizedFeature]:
    """
    "like" / "dislike" / "mixed" → meta.novelty с весом +0.7 / -0.7 / 0.0.
    None или unmapped → None.
    """
    if value is None:
        return None
    norm = normalize_form(value)
    if norm not in _NOVELTY_WEIGHTS:
        log.warning("taxonomy: unmapped novelty value %r", value)
        return None
    return NormalizedFeature(
        axis=fk.AXIS_META,
        feature_key="novelty",
        weight=_NOVELTY_WEIGHTS[norm],
        polarity="pos" if _NOVELTY_WEIGHTS[norm] >= 0 else "neg",
    )


# ──────────────────────────────────────────────────────────────────────
# Tablet — food_desires (что хочется сейчас)
# ──────────────────────────────────────────────────────────────────────

# instore_goal ключ → на какую ось движка это ложится.
_INSTORE_GOAL_AXIS_MAP: dict[str, str] = {
    "healthy_choice": fk.AXIS_CONTEXT,
    "meat": fk.AXIS_INGREDIENT,
    "fish_seafood": fk.AXIS_INGREDIENT,
    "soup": fk.AXIS_FORMAT_TEXTURE,
    "spicy": fk.AXIS_TASTE,
    "sweet": fk.AXIS_TASTE,
    "low_calorie": fk.AXIS_NUTRITION,
}


def normalize_food_desires(values: list[str]) -> list[NormalizedFeature]:
    """
    tablet food_options → short-term контекст. weight=0.7 (соответствует
    questionnaire_mapping.csv instore_goal), polarity=pos.

    "light" мапим как low_calorie (в features.format_texture ключа light нет).
    "hot" пока не маппим — нет таргета в текущей таксономии features.
    """
    out: list[NormalizedFeature] = []
    for v in values:
        key = _match(v, INSTORE_GOAL_INDEX)
        if key is None:
            log.warning("taxonomy: unmapped food_desire value %r", v)
            continue
        axis = _INSTORE_GOAL_AXIS_MAP.get(key, fk.AXIS_CONTEXT)
        out.append(NormalizedFeature(
            axis=axis, feature_key=key, weight=0.7, polarity="pos",
        ))
    return out


# ──────────────────────────────────────────────────────────────────────
# Tablet — hunger_level
# ──────────────────────────────────────────────────────────────────────

def normalize_hunger(value: str | None) -> Optional[NormalizedFeature]:
    """
    snack / quick / full → nutrition.satiety_class с весом 0.8.
    """
    if value is None:
        return None
    key = _match(value, HUNGER_INDEX)
    if key is None:
        log.warning("taxonomy: unmapped hunger value %r", value)
        return None
    return NormalizedFeature(
        axis=fk.AXIS_NUTRITION, feature_key=key, weight=0.8, polarity="pos",
    )
