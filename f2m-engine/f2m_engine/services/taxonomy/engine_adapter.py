"""
Адаптер к вендорному движку (backend/vendor/f2m_engine/).

Не меняем код движка — только обёртываем его приватные функции-extractors
под нашу модель строки menu_x5 (Postgres row: name / category / ingredients /
kbzhu / weight).

Возвращаем dict, совместимый по структуре с нашим текущим build_dish_features,
чтобы rebuild_all / API мог переключиться точка-в-точку.
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from f2m_engine.config.taxonomy import RuntimeTaxonomy, load_runtime_taxonomy
from f2m_engine.pipelines.dish_features_stage_a import (
    _compute_hard_flags,
    _compute_nutrition,
    _extract_context_from_text,
    _extract_cuisine,
    _extract_format_texture,
    _extract_ingredients,
    _extract_taste_from_ingredients,
    _normalize,
)

log = logging.getLogger(__name__)

_TAXONOMY_PATH = Path(__file__).resolve().parents[3] / "vendor" / "f2m_engine" / "data" / "taxonomy.json"


@lru_cache(maxsize=1)
def _taxonomy() -> RuntimeTaxonomy:
    return load_runtime_taxonomy(_TAXONOMY_PATH)


# ──────────────────────────────────────────────────────────────────────
# Парсинг X5-формата «Б7 Ж3.8 У36.4 Кк207.8» → kcal/protein/fat/carb
# (формат движка «К:…;Б:…;Ж:…;Э:…ккал» у нас не используется)
# ──────────────────────────────────────────────────────────────────────

_KBZHU_PATTERN = re.compile(
    r"Б\s*([\d.,]+).*?Ж\s*([\d.,]+).*?У\s*([\d.,]+).*?Кк\s*([\d.,]+)",
    re.IGNORECASE,
)


def _parse_kbzhu(raw: Any) -> dict[str, float | None]:
    """
    Примеры входа: "Б7 Ж3.8 У36.4 Кк207.8", "Б29 Ж19 У40 Кк450".
    Возвращает per-100g значения по всем макро.
    kcal — тоже per-100g; вызывающий code умножит на weight/100 для per-portion.
    """
    empty = {"protein_per_100g": None, "fat_per_100g": None, "carb_per_100g": None, "kcal_per_100g": None}
    if not raw:
        return empty
    m = _KBZHU_PATTERN.search(str(raw))
    if not m:
        return empty
    try:
        protein, fat, carb, kcal = (float(v.replace(",", ".")) for v in m.groups())
    except ValueError:
        return empty
    return {
        "protein_per_100g": protein,
        "fat_per_100g": fat,
        "carb_per_100g": carb,
        "kcal_per_100g": kcal,
    }


def _parse_weight(raw: Any) -> float | None:
    """«110г» → 110.0, «315г» → 315.0, None → None."""
    if not raw:
        return None
    m = re.search(r"([\d.,]+)", str(raw))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


# ──────────────────────────────────────────────────────────────────────
# Главная функция: строка menu_x5 → полный dish_features dict
# ──────────────────────────────────────────────────────────────────────

def build_dish_features_rich(dish: dict[str, Any]) -> dict[str, Any]:
    """
    Обогащённая версия build_dish_features через вендорный движок.

    Вход — row из menu_x5 (name, category, ingredients, kbzhu, weight, tags_*).
    Выход — dict совместимый с предыдущим build_dish_features
    (cuisine/format_texture/taste/ingredient/context/nutrition/hard_flags/meta).
    """
    taxonomy = _taxonomy()

    name = _normalize(dish.get("name"))
    category = _normalize(dish.get("category"))
    ingredients_text = _normalize(dish.get("ingredients"))
    concat = f"{name} {category} {ingredients_text}"

    # 1. Ingredients через ALIASES движка.
    ingredient_weights, aliases_used = _extract_ingredients(concat)

    # 1a. Дополняем словарь движка тем, чего там нет (исторически узкий ALIASES):
    # арахис/орехи/острые маркеры в сыром тексте состава или в названии.
    # Без этого hard_flags.peanut/nuts всегда false, а taste.spicy ставится
    # только при явных chili/curry — и warning-теги аллергикам не работают.
    _augment_ingredients_from_text(ingredient_weights, aliases_used, concat)

    # 2. Nutrition: парсим X5-формат kbzhu + weight, затем отдаём в движок.
    kbzhu = _parse_kbzhu(dish.get("kbzhu"))
    weight_g = _parse_weight(dish.get("weight"))
    # X5 даёт kbzhu per-100g. Движок принимает kcal_per_portion — умножаем
    # на weight_g/100. Если weight неизвестен — per-portion посчитать нельзя,
    # оставим None (тогда low_calorie=False через builtin-логику движка).
    kcal_per_100 = kbzhu.pop("kcal_per_100g", None)
    kcal_per_portion = (
        kcal_per_100 * weight_g / 100.0
        if kcal_per_100 is not None and weight_g
        else None
    )
    nutrition_input = {
        **kbzhu,
        "weight_g": weight_g,
        "weight_needs_review": False,
        "weight_raw": dish.get("weight"),
        "kcal_per_portion": kcal_per_portion,
    }
    nutrition = _compute_nutrition(nutrition_input)
    # Если движок не смог — используем satiety_class из tags_satiety (как было).
    if not nutrition.get("satiety_class"):
        fallback_class = _satiety_from_tags(dish.get("tags_satiety"))
        if fallback_class:
            nutrition["satiety_class"] = fallback_class

    # 3. Hard flags: вяжем к ингредиентам + алкоголю.
    hard_flags = _compute_hard_flags(ingredient_weights, concat, taxonomy)

    # Зеркалим true-hard_flags в ось restriction — scorer.py ожидает
    # именно там negative-контрибьютор для аллергий (см. AXIS_WEIGHTS[restriction]).
    restriction = {key: 1.0 for key, is_set in hard_flags.items() if is_set}

    # 4. Cuisine (из name/description/category/ingredients + nutrition-health).
    #    Используем приватный extractor с dummy-evidence (нам оно не нужно).
    evidence_stub: list[list[Any]] = []
    cuisine = _extract_cuisine(
        name=name,
        description="",
        category=category,
        ingredients=ingredients_text,
        nutrition=nutrition,
        taxonomy=taxonomy,
        dish_id=str(dish.get("dish_id", "")),
        dish_name=str(dish.get("name", "")),
        evidence_rows=evidence_stub,
    )

    # 5. Format texture.
    format_texture = _extract_format_texture(
        name=name,
        category=category,
        ingredients=ingredients_text,
        taxonomy=taxonomy,
        dish_id=str(dish.get("dish_id", "")),
        dish_name=str(dish.get("name", "")),
        evidence_rows=evidence_stub,
    )

    # 6. Taste из ингредиентов (sugar→sweet, soy_sauce→umami и т.п.).
    taste = _extract_taste_from_ingredients(ingredient_weights)

    # 7. Context (morning/lunch/quick/healthy_choice из текста).
    context = _extract_context_from_text(concat)

    return {
        "cuisine": cuisine,
        "format_texture": format_texture,
        "taste": taste,
        "ingredient": ingredient_weights,
        "context": context,
        "nutrition": nutrition,
        "hard_flags": hard_flags,
        "restriction": restriction,
        "meta": {
            "name": dish.get("name"),
            "category": dish.get("category"),
            "category_id": dish.get("category_id"),
            "price": dish.get("price"),
            "weight": dish.get("weight"),
            "kbzhu": dish.get("kbzhu"),
            "ingredients_raw": dish.get("ingredients"),
            "aliases_used": aliases_used,
        },
    }


_EXTRA_INGREDIENT_PATTERNS: dict[str, tuple[str, ...]] = {
    "peanut": ("арахис", "арахисов", "peanut"),
    "nuts": (
        "миндал", "кешью", "фисташ", "фундук", "грецк", "кедров",
        "пекан", "макадам",
        "almond", "cashew", "pistach", "walnut", "hazelnut", "pecan",
    ),
    "chili": (
        "перец чили", "перец красный острый", "халапень", "халапеньо",
        "шрирач", "табаско", "tabasco", "wasab", "васаби",
        "карри", "том ям", "том-ям", "кимчи", "арабьят", "аррабьят",
        "по-корейски", "корейск", "harissa", "сальса остр",
        "паст а карри", "tikka", "tom yum",
        # Сырьё в составе:
        "перец острый",
    ),
    "mushroom": (
        "гриб", "шампин", "вешенк", "опят", "лисич", "трюфел",
        "белый гриб", "mushroom", "porcin",
    ),
}


def _augment_ingredients_from_text(
    ingredient_weights: dict[str, float],
    aliases_used: list[str],
    concat_text: str,
) -> None:
    """
    Дополняет ingredient_weights, найденные вендорным extractor-ом, паттернами,
    которых нет в стоковом ALIASES движка. Mutates in place.

    Намеренно осторожно:
    - "орех" один НЕ матчим (мускатный орех — специя, не аллерген уровня орехов)
    - "перец чёрный" не матчим как chili
    - матч любой подстрокой, но из узкого списка
    """
    haystack = concat_text.lower()
    for canonical, patterns in _EXTRA_INGREDIENT_PATTERNS.items():
        if canonical in ingredient_weights and ingredient_weights[canonical] >= 1.0:
            continue
        for pat in patterns:
            if pat in haystack:
                ingredient_weights[canonical] = max(
                    ingredient_weights.get(canonical, 0.0), 1.0
                )
                aliases_used.append(pat)
                break


def _satiety_from_tags(raw: Any) -> str | None:
    """Для блюд без распознанного kbzhu оставляем сатиети по тегам меню."""
    if not raw:
        return None
    value = str(raw).lower().strip()
    if "сытн" in value:
        return "hearty"
    if "легк" in value or "лёгк" in value:
        return "light"
    if "перекус" in value:
        return "snack"
    return None
