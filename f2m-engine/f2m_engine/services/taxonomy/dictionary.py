"""
Словари синонимов: "что может прийти с UI / из CSV-тегов меню" → feature_key.

Каждая запись — `feature_key: [возможные формы]`. Формы матчатся по нормализации
(_lower, _strip, replace ё→е). Добавление нового значения = одна строка сюда.
"""
from typing import Final

# ──────────────────────────────────────────────────────────────────────
# Аллергии / диетические ограничения / религиозные запреты (axis=restriction)
# ──────────────────────────────────────────────────────────────────────

RESTRICTION_SYNONYMS: Final[dict[str, tuple[str, ...]]] = {
    # Аллергии (phone TasteStep1 + tablet)
    "gluten": ("Глютен", "gluten"),
    "lactose": ("Лактоза", "lactose", "Молочное", "Молочные", "Молочка"),
    "peanut": ("Арахис", "peanut", "peanuts"),
    "nuts": ("Орехи", "nuts"),
    "fish_seafood": ("Рыба и морепродукты", "fish", "Рыба", "Морепродукты"),
    "egg": ("Яйца", "eggs", "egg", "Яйцо"),
    "soy": ("Соя", "soy"),
    # Долгосрочные пищевые запреты (phone TasteStep2)
    "vegetarian": ("Вегетарианство", "vegetarian"),
    "vegan": ("Веганство", "vegan"),
    "halal": ("Халяль", "halal"),
    "no_sugar": ("Без сахара", "no-sugar", "no_sugar"),
    # Исключения-продукты (phone TasteStep3) — строгие запреты, мапятся в restriction
    "pork": ("Свинина", "pork"),
    "offal": ("Мясные субпродукты (печень, язык)", "offal", "Субпродукты", "Печень"),
}

# Мягкие негативы в axis=ingredient (weight=-0.8, см. questionnaire_mapping.csv:16-17).
AVOID_SOFT_NEG_SYNONYMS: Final[dict[str, tuple[str, ...]]] = {
    "mushroom": ("Грибы", "mushroom", "mushrooms"),
    "onion": ("Лук", "onion", "onions"),
}

# Мягкие негативы в axis=taste (weight=-0.8, см. questionnaire_mapping.csv:18).
# «Острое» из TasteStep3 — не hard-ban, а soft penalty на taste.spicy.
AVOID_TASTE_NEG_SYNONYMS: Final[dict[str, tuple[str, ...]]] = {
    "spicy": ("Острые ингредиенты и специи", "spicy-avoid", "spicy_avoid"),
}

# ──────────────────────────────────────────────────────────────────────
# Питательные цели (axis=nutrition)
# ──────────────────────────────────────────────────────────────────────

NUTRITION_SYNONYMS: Final[dict[str, tuple[str, ...]]] = {
    "low_calorie": ("Мало калорий", "low-calorie", "low_calorie", "Низкокалорийная диета", "мало_калорий"),
    "high_protein": ("Много белка", "high-protein", "high_protein", "Высокобелковая диета", "много_белка"),
    "low_fat": ("Мало жиров", "low-fat", "low_fat", "мало_жиров"),
    "high_carb": ("Много углеводов", "high-carb", "high_carb", "много_углеводов"),
}

# ──────────────────────────────────────────────────────────────────────
# Кухни (axis=cuisine) — из menu_x5.tags_cuisine
# ──────────────────────────────────────────────────────────────────────

CUISINE_SYNONYMS: Final[dict[str, tuple[str, ...]]] = {
    "russian_home": ("Русская", "русская", "русское"),
    "asian": ("азиатская", "азиатское", "asian"),
    "japanese": ("японская", "японское", "japanese"),
    "korean": ("корейская", "корейское", "korean"),
    "thai": ("тайская", "тайское", "thai"),
    "italian": ("итальянская", "итальянское", "italian"),
    "georgian_caucasian": ("грузинская", "кавказская", "georgian"),
    "indian": ("индийская", "индийское", "indian"),
    "fast_food": ("фастфуд", "фаст-фуд", "fast food"),
    "healthy": ("здоровое", "healthy"),
    "comfort_food": ("домашняя", "домашнее", "home", "comfort_food"),
    "street_food": ("стритфуд", "street_food"),
    "author_style": ("авторское", "авторская", "author"),
    "home_style": ("домашний стиль", "home_style"),
}

# ──────────────────────────────────────────────────────────────────────
# Формат / текстура блюда (axis=format_texture) — из menu_x5.tags_satiety + названий категорий
# ──────────────────────────────────────────────────────────────────────

FORMAT_TEXTURE_SYNONYMS: Final[dict[str, tuple[str, ...]]] = {
    "soup": ("суп", "soup", "супы"),
    "salad": ("салат", "salad", "салаты"),
    "bowl": ("боул", "bowl"),
    "roll": ("ролл", "roll", "роллы"),
    "pizza": ("пицца", "pizza"),
    "pasta": ("паста", "pasta"),
    "burger": ("бургер", "burger"),
    "shawarma": ("шаурма", "shawarma"),
    "dessert": ("десерт", "dessert", "сладкое", "sweet"),
    "breakfast": ("завтрак", "breakfast"),
    "bakery": ("выпечка", "bakery", "хлеб"),
    "grilled": ("гриль", "grilled", "на гриле"),
    "fried": ("жареное", "fried"),
    "baked": ("запечённое", "baked", "запеченное"),
    "steamed": ("на пару", "steamed"),
    "crispy": ("хрустящее", "crispy"),
    "creamy": ("кремовое", "creamy", "сливочное"),
}

# Satiety class (axis=nutrition.satiety) — легкое/сытное/перекус из tags_satiety
SATIETY_SYNONYMS: Final[dict[str, tuple[str, ...]]] = {
    "snack": ("перекус", "snack"),
    "light": ("легкое", "лёгкое", "light"),
    "hearty": ("сытное", "hearty", "full", "full_meal"),
}

# ──────────────────────────────────────────────────────────────────────
# Контекст (axis=context) — что хочется поесть прямо сейчас (tablet food_options)
# ──────────────────────────────────────────────────────────────────────

INSTORE_GOAL_SYNONYMS: Final[dict[str, tuple[str, ...]]] = {
    # Реальные опции tablet из _FOOD_OPTIONS в rec_x5.py.
    # light/hot маппинг: light → nutrition.low_calorie (в features.format_texture
    # ключей light/hot НЕТ, поэтому матчим в реальную ось — low_calorie уже
    # размечен на 50%+ блюд по правилам движка). hot пока не маппим — нет
    # подходящего таргета без расширения таксономии format_texture.
    "healthy_choice": ("vegetables", "Больше овощей", "овощи"),
    "meat": ("meat", "Мясо"),
    "fish_seafood": ("fish", "Рыба и морепродукты"),
    "soup": ("soup", "Суп"),
    "spicy": ("spicy", "Острое блюдо", "Острое"),
    "sweet": ("sweet", "Сладкое"),
    "low_calorie": ("light", "Лёгкое", "лёгкое"),
}

# Уровень голода (tablet hunger_level → format_texture satiety)
HUNGER_SYNONYMS: Final[dict[str, tuple[str, ...]]] = {
    "snack": ("snack", "Хочу перекусить", "Перекус"),
    "quick": ("quick", "Хочу быстро утолить голод", "Быстро"),
    "hearty": ("full", "hearty", "Хочу полноценный прием пищи", "Полноценный"),
}

# ──────────────────────────────────────────────────────────────────────
# Вкусы (axis=taste) — пока нет в анкете, мапим только из тегов блюд/ингредиентов
# ──────────────────────────────────────────────────────────────────────

TASTE_SYNONYMS: Final[dict[str, tuple[str, ...]]] = {
    "sweet": ("сладкое", "sweet"),
    "salty": ("солёное", "соленое", "salty"),
    "sour": ("кислое", "sour"),
    "spicy": ("острое", "spicy"),
    "bitter": ("горькое", "bitter"),
    "umami": ("умами", "umami"),
}


def _build_reverse_index(
    synonyms: dict[str, tuple[str, ...]],
) -> dict[str, str]:
    """Разворачивает {key: [synonyms]} в {normalized_synonym: key} для O(1) lookup."""
    index: dict[str, str] = {}
    for canonical_key, forms in synonyms.items():
        index[_normalize_form(canonical_key)] = canonical_key
        for form in forms:
            index[_normalize_form(form)] = canonical_key
    return index


def _normalize_form(value: str) -> str:
    """Приводит к lowercase + trim + замена ё→е для поиска в индексе."""
    return value.strip().lower().replace("ё", "е")


# Pre-built reverse indexes — строятся один раз при импорте модуля.
RESTRICTION_INDEX: Final = _build_reverse_index(RESTRICTION_SYNONYMS)
AVOID_SOFT_NEG_INDEX: Final = _build_reverse_index(AVOID_SOFT_NEG_SYNONYMS)
AVOID_TASTE_NEG_INDEX: Final = _build_reverse_index(AVOID_TASTE_NEG_SYNONYMS)
NUTRITION_INDEX: Final = _build_reverse_index(NUTRITION_SYNONYMS)
CUISINE_INDEX: Final = _build_reverse_index(CUISINE_SYNONYMS)
FORMAT_TEXTURE_INDEX: Final = _build_reverse_index(FORMAT_TEXTURE_SYNONYMS)
SATIETY_INDEX: Final = _build_reverse_index(SATIETY_SYNONYMS)
INSTORE_GOAL_INDEX: Final = _build_reverse_index(INSTORE_GOAL_SYNONYMS)
HUNGER_INDEX: Final = _build_reverse_index(HUNGER_SYNONYMS)
TASTE_INDEX: Final = _build_reverse_index(TASTE_SYNONYMS)  # noqa: F401 — reserved for R2


def normalize_form(value: str) -> str:
    """Public alias для использования в mapper.py."""
    return _normalize_form(value)
