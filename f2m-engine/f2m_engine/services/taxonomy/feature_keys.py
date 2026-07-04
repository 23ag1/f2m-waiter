"""
Канонические feature_keys по 6 осям из runtime_taxonomy_resolved_v1.json.
Эти константы — единственный источник правды для движка и валидации.

При расширении таксономии ML-специалистом: правим здесь + в dictionary.py.
"""
from typing import Final

AXIS_TASTE: Final = "taste"
AXIS_INGREDIENT: Final = "ingredient"
AXIS_CUISINE: Final = "cuisine"
AXIS_FORMAT_TEXTURE: Final = "format_texture"
AXIS_CONTEXT: Final = "context"
AXIS_RESTRICTION: Final = "restriction"
AXIS_NUTRITION: Final = "nutrition"
AXIS_META: Final = "meta"

TASTE_KEYS: Final = frozenset({"sweet", "salty", "sour", "spicy", "bitter", "umami"})

CUISINE_KEYS: Final = frozenset({
    "russian_home", "asian", "japanese", "korean", "thai", "italian",
    "georgian_caucasian", "indian", "fast_food", "healthy", "comfort_food",
    "street_food", "home_style", "author_style",
})

FORMAT_TEXTURE_KEYS: Final = frozenset({
    "soup", "salad", "bowl", "roll", "pizza", "pasta", "burger", "shawarma",
    "dessert", "breakfast", "bakery", "grilled", "fried", "baked", "steamed",
    "crispy", "creamy",
})

CONTEXT_KEYS: Final = frozenset({
    "morning", "lunch", "evening", "night", "quick", "romantic", "work_lunch",
    "delivery_home", "delivery_office", "dine_in", "company", "healthy_choice",
    "recovery", "indulgence",
})

RESTRICTION_KEYS: Final = frozenset({
    "gluten", "lactose", "nuts", "peanut", "fish_seafood", "egg", "soy",
    "pork", "offal", "mushroom", "onion", "spicy_avoid",
    "vegetarian", "vegan", "halal", "no_sugar",
})

NUTRITION_BOOLEAN_KEYS: Final = frozenset({
    "low_calorie", "high_protein", "low_fat", "high_carb",
})
SATIETY_CLASS_KEYS: Final = frozenset({"snack", "light", "hearty"})

META_KEYS: Final = frozenset({"novelty"})

# Оси с закрытым набором feature_keys — валидатор сверяет с этим мапом.
# ingredient — открытая ось (canonical ingredient_ids), валидация пропускается.
# nutrition — смешанная (boolean_tags ∪ satiety_class values).
_CLOSED_AXIS_KEYS: Final[dict[str, frozenset[str]]] = {
    AXIS_TASTE: TASTE_KEYS,
    AXIS_CUISINE: CUISINE_KEYS,
    AXIS_FORMAT_TEXTURE: FORMAT_TEXTURE_KEYS,
    AXIS_CONTEXT: CONTEXT_KEYS,
    AXIS_RESTRICTION: RESTRICTION_KEYS,
    AXIS_NUTRITION: NUTRITION_BOOLEAN_KEYS | SATIETY_CLASS_KEYS,
    AXIS_META: META_KEYS,
}


def is_valid(axis: str, feature_key: str) -> bool:
    """
    Проверяет пару (axis, feature_key) на соответствие runtime_taxonomy.
    Для AXIS_INGREDIENT всегда True (открытый набор).
    """
    if axis == AXIS_INGREDIENT:
        return True
    keys = _CLOSED_AXIS_KEYS.get(axis)
    return keys is not None and feature_key in keys

# Aliases из runtime_taxonomy_resolved_v1.json — приведение к каноничной форме.
AXIS_ALIASES: Final[dict[str, str]] = {
    "georgian": "georgian_caucasian",
    "caucasian": "georgian_caucasian",
    "asian_style": "asian",
    "italian_style": "italian",
    "author": "author_style",
    "home": "home_style",
    "breakfast_context": "morning",
    "dinner": "evening",
    "healthy_context": "healthy_choice",
    "full_meal": "hearty",
}


def resolve_alias(key: str) -> str:
    """Приводит key к каноничной форме через AXIS_ALIASES."""
    return AXIS_ALIASES.get(key, key)
