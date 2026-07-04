from __future__ import annotations

import json
from pathlib import Path
from typing import Any


RU_TAG_LABELS: dict[tuple[str, str], str] = {
    ("taste", "sweet"): "Сладкое",
    ("taste", "salty"): "Соленое",
    ("taste", "sour"): "Кислое",
    ("taste", "spicy"): "Острое",
    ("taste", "bitter"): "Горькое",
    ("taste", "umami"): "Умами",
    ("cuisine", "russian_home"): "Русская кухня",
    ("cuisine", "asian"): "Азиатское",
    ("cuisine", "japanese"): "Японское",
    ("cuisine", "korean"): "Корейское",
    ("cuisine", "thai"): "Тайское",
    ("cuisine", "italian"): "Итальянское",
    ("cuisine", "georgian_caucasian"): "Кавказское",
    ("cuisine", "indian"): "Индийское",
    ("cuisine", "fast_food"): "Фастфуд",
    ("cuisine", "healthy"): "ЗОЖ",
    ("cuisine", "comfort_food"): "Комфортная еда",
    ("cuisine", "street_food"): "Стритфуд",
    ("cuisine", "home_style"): "Домашнее",
    ("cuisine", "author_style"): "Авторское",
    ("format_texture", "soup"): "Суп",
    ("format_texture", "salad"): "Салат",
    ("format_texture", "bowl"): "Боул",
    ("format_texture", "roll"): "Ролл",
    ("format_texture", "pizza"): "Пицца",
    ("format_texture", "pasta"): "Паста",
    ("format_texture", "burger"): "Бургер",
    ("format_texture", "shawarma"): "Шаурма",
    ("format_texture", "dessert"): "Десерт",
    ("format_texture", "breakfast"): "Завтрак",
    ("format_texture", "bakery"): "Выпечка",
    ("format_texture", "grilled"): "Гриль",
    ("format_texture", "fried"): "Жареное",
    ("format_texture", "baked"): "Запеченное",
    ("format_texture", "steamed"): "На пару",
    ("format_texture", "crispy"): "Хрустящее",
    ("format_texture", "creamy"): "Сливочное",
    ("context", "morning"): "Утро",
    ("context", "lunch"): "Обед",
    ("context", "evening"): "Вечер",
    ("context", "night"): "Ночь",
    ("context", "quick"): "Быстро",
    ("context", "romantic"): "Романтический повод",
    ("context", "work_lunch"): "Рабочий обед",
    ("context", "delivery_home"): "Доставка домой",
    ("context", "delivery_office"): "Доставка в офис",
    ("context", "dine_in"): "В зале",
    ("context", "company"): "Для компании",
    ("context", "healthy_choice"): "Здоровый выбор",
    ("context", "recovery"): "Восстановление",
    ("context", "indulgence"): "Побаловать себя",
    ("restriction", "gluten"): "Глютен",
    ("restriction", "lactose"): "Лактоза",
    ("restriction", "nuts"): "Орехи",
    ("restriction", "peanut"): "Арахис",
    ("restriction", "fish_seafood"): "Рыба и морепродукты",
    ("restriction", "egg"): "Яйцо",
    ("restriction", "soy"): "Соя",
    ("restriction", "pork"): "Свинина",
    ("restriction", "offal"): "Субпродукты",
    ("restriction", "mushroom"): "Грибы",
    ("restriction", "onion"): "Лук",
    ("restriction", "spicy_avoid"): "Избегать острого",
    ("restriction", "vegetarian"): "Вегетарианство",
    ("restriction", "vegan"): "Веганство",
    ("restriction", "halal"): "Халяль",
    ("restriction", "no_sugar"): "Без сахара",
    ("nutrition", "low_calorie"): "Низкокалорийное",
    ("nutrition", "high_protein"): "Много белка",
    ("nutrition", "low_fat"): "Меньше жира",
    ("nutrition", "high_carb"): "Углеводное",
    ("nutrition", "snack"): "Перекус",
    ("nutrition", "light"): "Легкое",
    ("nutrition", "hearty"): "Сытное",
}


def localize_tag(axis: str, key: str, locale: str = "ru") -> str:
    if locale != "ru":
        return str(key)
    return RU_TAG_LABELS.get((str(axis), str(key)), str(key))


def display_tag(axis: str, key: str, kind: str, priority: int, locale: str = "ru") -> dict[str, Any]:
    return {
        "axis": str(axis),
        "key": str(key),
        "label": localize_tag(axis=axis, key=key, locale=locale),
        "kind": str(kind),
        "priority": int(priority),
    }


def missing_taxonomy_labels(taxonomy_path: Path | str) -> list[dict[str, str]]:
    taxonomy = json.loads(Path(taxonomy_path).read_text(encoding="utf-8"))
    axes = taxonomy.get("storage_axes", {})
    rows: list[dict[str, str]] = []
    for axis, keys in sorted(axes.items()):
        if axis == "ingredient":
            continue
        if isinstance(keys, list):
            axis_keys = keys
        elif axis == "nutrition" and isinstance(keys, dict):
            axis_keys = [
                *keys.get("boolean_tags", []),
                *keys.get("satiety_class_values", []),
            ]
        else:
            continue
        for key in sorted(str(item) for item in axis_keys):
            if (str(axis), key) not in RU_TAG_LABELS:
                rows.append({"axis": str(axis), "key": key, "issue": "missing_ru_label"})
    return rows
