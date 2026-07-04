"""
Построение dish_features_cache.jsonb на одно блюдо.

Формат совместим с dish_features_cache движка (Rec/f2m 2/data/derived/dish_features_cache.json):
{
    "cuisine": {"asian": 1.0, ...},
    "format_texture": {"soup": 1.0, ...},
    "nutrition": {"satiety_class": "hearty", "low_calorie": true, ...},
    "taste": {...},
    "ingredient": {...},
    "hard_flags": {"gluten": false, ...},
    "meta": {"name": ..., "category": ..., "price": ..., "weight": ..., "kbzhu": ...},
}

На входе — row из menu_x5 (словарь). На выходе — dict, готовый к записи в JSONB.
"""
from __future__ import annotations

import logging
from typing import Any

from app.services.taxonomy.dictionary import (
    CUISINE_INDEX,
    FORMAT_TEXTURE_INDEX,
    NUTRITION_INDEX,
    SATIETY_INDEX,
    normalize_form,
)
from app.services.taxonomy.feature_keys import NUTRITION_BOOLEAN_KEYS

log = logging.getLogger(__name__)


def _split_csv(value: str | None) -> list[str]:
    """CSV-теги → list чистых значений. Пустые и whitespace отбрасываем."""
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _map_via_index(values: list[str], index: dict[str, str]) -> dict[str, float]:
    """CSV-значения → {canonical_key: 1.0}. Unmapped логируются WARN."""
    out: dict[str, float] = {}
    for v in values:
        key = index.get(normalize_form(v))
        if key is None:
            log.warning("dish_features: unmapped tag %r", v)
            continue
        out[key] = 1.0
    return out


def build_dish_features(dish: dict[str, Any]) -> dict[str, Any]:
    """
    Преобразует строку menu_x5 в JSONB dish_features через вендорный движок
    (см. engine_adapter.build_dish_features_rich) — там богатая экстракция
    ингредиентов/кухни/формата/вкуса/hard_flags через словари коллеги.

    Тонкий fallback на CSV-теги оставлен внутри adapter (satiety_class из
    tags_satiety если kbzhu не распарсился).
    """
    from app.services.taxonomy.engine_adapter import build_dish_features_rich
    return build_dish_features_rich(dish)


def _build_dish_features_legacy(dish: dict[str, Any]) -> dict[str, Any]:
    """Прежняя тонкая версия, оставлена для сравнения и отката при нужде."""
    cuisines = _split_csv(dish.get("tags_cuisine"))
    satieties = _split_csv(dish.get("tags_satiety"))
    kbzhu = _split_csv(dish.get("tags_kbzhu"))
    dish_tags = _split_csv(dish.get("dish_tags"))

    cuisine_map = _map_via_index(cuisines, CUISINE_INDEX)
    # format_texture извлекаем из dish_tags (пусто сейчас) и satiety-ключей,
    # которые попадают в format (light/hearty/snack — но это nutrition satiety).
    format_texture_map = _map_via_index(dish_tags, FORMAT_TEXTURE_INDEX)

    # nutrition.boolean_tags из tags_kbzhu
    nutrition: dict[str, Any] = {}
    for v in kbzhu:
        key = NUTRITION_INDEX.get(normalize_form(v))
        if key and key in NUTRITION_BOOLEAN_KEYS:
            nutrition[key] = True
        elif key is None:
            log.warning("dish_features: unmapped kbzhu tag %r", v)

    # nutrition.satiety_class — единственное значение (snack/light/hearty) из tags_satiety
    satiety_class: str | None = None
    for v in satieties:
        if key := SATIETY_INDEX.get(normalize_form(v)):
            satiety_class = key
            break  # берём первое валидное
    if satiety_class:
        nutrition["satiety_class"] = satiety_class

    meta = {
        "name": dish.get("name"),
        "category": dish.get("category"),
        "category_id": dish.get("category_id"),
        "weight": dish.get("weight"),
        "kbzhu": dish.get("kbzhu"),
        "ingredients_raw": dish.get("ingredients"),
    }

    return {
        "cuisine": cuisine_map,
        "format_texture": format_texture_map,
        "taste": {},           # отсутствует в меню X5, заполнится движком по ингредиентам
        "ingredient": {},      # требует словарь ингредиентов — задача для следующей фазы
        "context": {},         # заполнится из временных тегов или вручную
        "nutrition": nutrition,
        "hard_flags": {},      # аналогично ingredient — требует ingredient_dictionary
        "meta": meta,
    }


async def rebuild_all(pool) -> dict[str, int]:
    """
    Перестраивает features для всех блюд в menu_x5.
    Возвращает статистику: processed, updated, failed.
    """
    rows = await pool.fetch(
        """SELECT dish_id, category, category_id, name, ingredients,
                  kbzhu, weight, tags_kbzhu, tags_satiety,
                  tags_cuisine, dish_tags
           FROM menu_x5 ORDER BY dish_id"""
    )
    processed = len(rows)
    # dict передаём напрямую — pool-level JSONB codec (database.py::_init_connection)
    # сериализует его через json.dumps сам. json.dumps здесь привёл бы к double-encode.
    payload: list[tuple[dict, int]] = []
    failed_ids: list[int] = []
    for row in rows:
        try:
            features = build_dish_features(dict(row))
            payload.append((features, row["dish_id"]))
        except Exception:
            log.exception("dish_features: failed for dish_id=%s", row["dish_id"])
            failed_ids.append(row["dish_id"])

    updated = 0
    if payload:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(
                    "UPDATE menu_x5 SET features = $1 WHERE dish_id = $2",
                    payload,
                )
                updated = len(payload)

    return {"processed": processed, "updated": updated, "failed": len(failed_ids)}
