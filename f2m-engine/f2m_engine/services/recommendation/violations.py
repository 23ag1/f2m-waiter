"""
Подсчёт нарушений ограничений юзера в конкретном блюде:
- hate ("Яйца") + hard_flags.egg=True → "Содержит яйца"
- avoid ("Грибы") + ingredient.mushroom=1.0 → "Содержит грибы"
- preferences ("Вегетарианство") + ingredient.chicken/beef/... → "Не вегетарианское"

Используется в двух местах:
1. scorer.score_dish — каждое нарушение добавляет −1.0 к скору (опускает вниз)
2. rec_x5._format_dish_x5 — попадает в dish_tags первым, красным цветом

Спец. правило для vegetarian: dish.features.restriction обычно НЕ содержит
ключ "vegetarian" (стейдж dish_features его не выставляет). Поэтому проверяем
по ingredient + hard_flags явно.
"""
from __future__ import annotations

from typing import Any

from app.services.recommendation.profile_features import UserFeatureBag

# Человекочитаемые надписи на красном теге.
WARNING_LABELS: dict[str, str] = {
    "egg": "Содержит яйца",
    "lactose": "Содержит лактозу",
    "gluten": "Содержит глютен",
    "nuts": "Содержит орехи",
    "peanut": "Содержит арахис",
    "soy": "Содержит сою",
    "fish_seafood": "Содержит рыбу",
    "mushroom": "Содержит грибы",
    "vegetarian": "Не вегетарианское",
    "vegan": "Не веганское",
    "halal": "Не халяль",
    "no_sugar": "Содержит сахар",
}

# Ингредиенты-индикаторы мясного блюда (для vegetarian violation).
_MEAT_INGREDIENTS = frozenset(
    {"chicken", "beef", "pork", "turkey", "lamb", "ham", "bacon", "duck"}
)


def compute_violations(
    user: UserFeatureBag,
    dish_features: dict[str, Any] | None,
) -> list[str]:
    """
    Возвращает список человекочитаемых нарушений для конкретного блюда
    под конкретного юзера. Пустой список = блюдо не противоречит профилю.

    Сохраняем порядок: restriction-нарушения раньше ingredient — критичные
    выше, чтобы фронт показывал их в первую очередь.
    """
    if not dish_features:
        return []

    out: list[str] = []
    seen: set[str] = set()

    dish_restrictions = dish_features.get("restriction") or {}
    dish_hard_flags = dish_features.get("hard_flags") or {}
    dish_ingredients = dish_features.get("ingredient") or {}

    # 1) Restriction-ось: vegetarian / halal / no_sugar / hate-аллергены (egg, lactose, gluten...)
    user_restrictions = user.by_axis.get("restriction", {})
    for slug, weight in user_restrictions.items():
        if weight >= 0 or slug in seen:
            continue

        violated = False
        if slug == "vegetarian":
            # spec: features.restriction обычно не содержит vegetarian, проверяем ingredients
            if any(m in dish_ingredients for m in _MEAT_INGREDIENTS):
                violated = True
            elif _truthy(dish_hard_flags.get("fish_seafood")):
                violated = True
            elif _truthy(dish_restrictions.get("fish_seafood")):
                violated = True
        elif slug == "vegan":
            if any(m in dish_ingredients for m in _MEAT_INGREDIENTS):
                violated = True
            elif _truthy(dish_hard_flags.get("fish_seafood")):
                violated = True
            elif _truthy(dish_hard_flags.get("egg")) or _truthy(dish_hard_flags.get("lactose")):
                violated = True
        else:
            # обычный аллерген: проверяем restriction + hard_flags
            if _truthy(dish_restrictions.get(slug)) or _truthy(dish_hard_flags.get(slug)):
                violated = True

        if violated:
            label = WARNING_LABELS.get(slug, f"Не подходит ({slug})")
            out.append(label)
            seen.add(slug)

    # 2) Ingredient-ось: avoid (грибы, лук и т.д.)
    user_ingredients = user.by_axis.get("ingredient", {})
    for slug, weight in user_ingredients.items():
        if weight >= 0 or slug in seen:
            continue
        if _truthy(dish_ingredients.get(slug)):
            label = WARNING_LABELS.get(slug, f"Содержит {slug}")
            out.append(label)
            seen.add(slug)

    return out


def _truthy(v: Any) -> bool:
    """True/1.0/нечто положительное считаем нарушением."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v > 0
    return False
