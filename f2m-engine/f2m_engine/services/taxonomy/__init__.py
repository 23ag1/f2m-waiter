"""
Слой таксономии: перевод «что юзер написал в UI» и «что написано в тегах меню»
в канонические feature_keys ML-движка Food2Mood (runtime_taxonomy_resolved_v1).

Источник правды для осей/ключей — Rec/f2m 2/docs/runtime_taxonomy_resolved_v1.json.
"""
from app.services.taxonomy.mapper import (
    NormalizedFeature,
    normalize_avoid,
    normalize_food_desires,
    normalize_hate,
    normalize_hunger,
    normalize_novelty,
    normalize_preferences,
)

__all__ = [
    "NormalizedFeature",
    "normalize_avoid",
    "normalize_food_desires",
    "normalize_hate",
    "normalize_hunger",
    "normalize_novelty",
    "normalize_preferences",
]
