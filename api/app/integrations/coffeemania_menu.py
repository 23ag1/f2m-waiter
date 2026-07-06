"""
Загрузка меню Кофемании в Postgres для адаптера рекомендаций.

Читает выгрузки Info API (dishes/restrictions), фильтрует до реальных продаваемых
блюд и складывает каталог + доступность по ресторанам. Фичи блюд для скоринга -
зона движка (Дима); здесь только каталог, доступность и флаги для cold-start.

Источник меню в пилоте - live-pull Info API (Фаза 1). Пока ингестим локальные
JSON-выгрузки из папки COFFEEMANIA_DATA_DIR.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from psycopg2.extras import execute_batch

# Подстроки категорий, которые не рекомендуем: алкоголь, компоненты, кейтеринг.
_EXCLUDE_CATEGORY_SUBSTR = (
    "вино", "игрист", "коктейл", "дижестив", "шампан", "виск", "ликёр", "ликер",
    "аперитив", "пиво", "пивн", "сидр", "вермут", "коньяк", "бренди", "граппа",
    "текил", "самбук", "абсент", "модификатор", "начинки и соус", "гарнир",
    "кейтеринг", "на заказ",
)
_POPULAR_SUBSTR = ("популярн",)


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _dish_category_titles(dish: dict) -> list[str]:
    titles = list(dish.get("categories") or [])
    for ext in (dish.get("extendedCategories") or []):
        title = ext.get("title")
        if title:
            titles.append(title)
    return [str(t) for t in titles if t]


def classify_dish(dish: dict) -> dict[str, Any]:
    """Нормализованная строка меню + флаги is_recommendable / is_popular."""
    titles = _dish_category_titles(dish)
    titles_l = [_norm(t) for t in titles]
    price_raw = dish.get("price") or 0
    has_price = bool(price_raw and float(price_raw) > 0)
    # Блюдо рекомендуемо, если есть хотя бы одна "нормальная" категория.
    # (одна доп-категория вроде "Кулинария на заказ" не должна убивать флагман)
    good_titles = [t for t in titles_l if not any(sub in t for sub in _EXCLUDE_CATEGORY_SUBSTR)]
    # onSale в выгрузке всегда false (не заполнен). Реальный сигнал снятия с продажи -
    # isOutdated (у таких outOfSaleDate в прошлом). Неактивные не храним/не рекомендуем.
    is_active = dish.get("isOutdated") is not True
    return {
        "sku": str(dish.get("sku") or ""),
        "name": str(dish.get("name") or dish.get("internalName") or ""),
        "price": float(price_raw) if has_price else 0.0,
        "categories": titles,
        "calories": dish.get("calories") or 0,
        "fats": dish.get("fats") or 0,
        "proteins": dish.get("proteins") or 0,
        "carbohydrates": dish.get("carbohydrates") or 0,
        "composition": str(dish.get("siteComposition") or dish.get("composition") or ""),
        "allergens": list(dish.get("allergens") or []),
        "available_departments": list(dish.get("availableInDepartments") or []),
        "is_active": is_active,
        "is_recommendable": is_active and has_price and len(good_titles) > 0,
        "is_popular": any(sub in title for title in titles_l for sub in _POPULAR_SUBSTR),
    }


def load_exports(data_dir: str | Path) -> dict[str, list]:
    base = Path(data_dir)
    dishes = json.loads((base / "dishes.json").read_text(encoding="utf-8")).get("result", [])
    restrictions = json.loads((base / "restrictions.json").read_text(encoding="utf-8")).get("result", [])
    return {"dishes": dishes, "restrictions": restrictions}


def ingest_menu(db_pool, data_dir: str | Path) -> dict[str, int]:
    """Загружает меню и стоп-листы в БД. Возвращает статистику."""
    data = load_exports(data_dir)
    all_rows = [classify_dish(d) for d in data["dishes"] if d.get("sku")]
    rows = [r for r in all_rows if r["is_active"]]  # снятые с продажи не грузим в базу

    menu_params = [
        (
            r["sku"], r["name"], r["price"], json.dumps(r["categories"], ensure_ascii=False),
            r["calories"], r["fats"], r["proteins"], r["carbohydrates"], r["composition"],
            json.dumps(r["allergens"]), json.dumps(r["available_departments"]),
            r["is_recommendable"], r["is_popular"],
        )
        for r in rows
    ]
    restr_params = [
        (str(res["sku"]), json.dumps(list(res.get("departments") or [])))
        for res in data["restrictions"] if res.get("sku")
    ]

    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            execute_batch(cur, """
                INSERT INTO coffeemania_menu
                    (sku, name, price, categories, calories, fats, proteins, carbohydrates,
                     composition, allergens, available_departments, is_recommendable, is_popular, updated_at)
                VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,NOW())
                ON CONFLICT (sku) DO UPDATE SET
                    name=EXCLUDED.name, price=EXCLUDED.price, categories=EXCLUDED.categories,
                    calories=EXCLUDED.calories, fats=EXCLUDED.fats, proteins=EXCLUDED.proteins,
                    carbohydrates=EXCLUDED.carbohydrates, composition=EXCLUDED.composition,
                    allergens=EXCLUDED.allergens, available_departments=EXCLUDED.available_departments,
                    is_recommendable=EXCLUDED.is_recommendable, is_popular=EXCLUDED.is_popular, updated_at=NOW()
            """, menu_params, page_size=500)
            execute_batch(cur, """
                INSERT INTO coffeemania_dish_restrictions (sku, departments)
                VALUES (%s, %s::jsonb)
                ON CONFLICT (sku) DO UPDATE SET departments=EXCLUDED.departments
            """, restr_params, page_size=500)
        conn.commit()
    finally:
        db_pool.putconn(conn)

    return {
        "dishes_total": len(all_rows),
        "dishes_active": len(rows),
        "recommendable": sum(1 for r in rows if r["is_recommendable"]),
        "restrictions": len(restr_params),
    }
