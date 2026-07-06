"""
Coffeemania Info API puller.

Тянет вживую из их Info API (relay2.coffeemania.ru:5015) и обновляет таблицы,
которые читает api-адаптер:
  - меню (Dishes)            -> coffeemania_menu               (реже, раз в час)
  - стоп-листы (DishRestrictions) -> coffeemania_dish_restrictions (чаще, раз в 15 мин)

Частоты по рекомендации Кофемании: меню раз в час, стоп-листы раз в 15 минут.
Фичи блюд для скоринга - зона движка (Дима); здесь только каталог и доступность.

Ingest разнесён: pull_menu() и pull_stoplists() независимы, чтобы стоп-листы
можно было обновлять чаще меню. Обновление таблицы - полная замена в транзакции
(атомарный свап для читателей), с защитой от пустого ответа (не затираем данные).
"""
from __future__ import annotations

import json
import logging
import os

import httpx
import psycopg2
from psycopg2.extras import execute_batch

log = logging.getLogger("coffeemania_puller")

INFO_URL = os.getenv("COFFEEMANIA_INFO_URL", "https://relay2.coffeemania.ru:5015").rstrip("/")
VERIFY_SSL = os.getenv("COFFEEMANIA_INFO_VERIFY_SSL", "true").lower() not in ("0", "false", "no")
HTTP_TIMEOUT = float(os.getenv("COFFEEMANIA_INFO_TIMEOUT", "90"))

_EXCLUDE_CATEGORY_SUBSTR = (
    "вино", "игрист", "коктейл", "дижестив", "шампан", "виск", "ликёр", "ликер",
    "аперитив", "пиво", "пивн", "сидр", "вермут", "коньяк", "бренди", "граппа",
    "текил", "самбук", "абсент", "модификатор", "начинки и соус", "гарнир",
    "кейтеринг", "на заказ",
)
_POPULAR_SUBSTR = ("популярн",)


def _norm(value) -> str:
    return str(value or "").strip().lower()


def _titles(dish: dict) -> list[str]:
    titles = list(dish.get("categories") or [])
    for ext in (dish.get("extendedCategories") or []):
        if ext.get("title"):
            titles.append(ext["title"])
    return [str(t) for t in titles if t]


def classify_dish(dish: dict) -> dict:
    """Нормализованная строка меню + is_recommendable / is_popular (как в api-адаптере)."""
    titles = _titles(dish)
    titles_l = [_norm(t) for t in titles]
    price = dish.get("price") or 0
    has_price = bool(price and float(price) > 0)
    good = [t for t in titles_l if not any(s in t for s in _EXCLUDE_CATEGORY_SUBSTR)]
    # onSale в выгрузке всегда false (не заполнен) - непригоден. Реальный сигнал
    # снятия с продажи - isOutdated (у таких outOfSaleDate в прошлом). Такие блюда
    # не храним и не рекомендуем.
    is_active = dish.get("isOutdated") is not True
    return {
        "sku": str(dish.get("sku") or ""),
        "name": str(dish.get("name") or dish.get("internalName") or ""),
        "price": float(price) if has_price else 0.0,
        "categories": titles,
        "calories": dish.get("calories") or 0,
        "fats": dish.get("fats") or 0,
        "proteins": dish.get("proteins") or 0,
        "carbohydrates": dish.get("carbohydrates") or 0,
        "composition": str(dish.get("siteComposition") or dish.get("composition") or ""),
        "allergens": list(dish.get("allergens") or []),
        "available_departments": list(dish.get("availableInDepartments") or []),
        "is_active": is_active,
        "is_recommendable": is_active and has_price and len(good) > 0,
        "is_popular": any(s in t for t in titles_l for s in _POPULAR_SUBSTR),
    }


def _connect():
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ.get("POSTGRES_PORT", 5432)),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    )


def _fetch(endpoint: str) -> list:
    url = f"{INFO_URL}/api/Info/{endpoint}"
    with httpx.Client(timeout=HTTP_TIMEOUT, verify=VERIFY_SSL) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json().get("result", []) or []


def _ensure_tables(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS coffeemania_menu (
                sku TEXT PRIMARY KEY, name TEXT, price NUMERIC DEFAULT 0,
                categories JSONB DEFAULT '[]'::jsonb,
                calories NUMERIC DEFAULT 0, fats NUMERIC DEFAULT 0,
                proteins NUMERIC DEFAULT 0, carbohydrates NUMERIC DEFAULT 0,
                composition TEXT DEFAULT '', allergens JSONB DEFAULT '[]'::jsonb,
                available_departments JSONB DEFAULT '[]'::jsonb,
                is_recommendable BOOLEAN DEFAULT FALSE, is_popular BOOLEAN DEFAULT FALSE,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS coffeemania_dish_restrictions (
                sku TEXT PRIMARY KEY, departments JSONB DEFAULT '[]'::jsonb,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("ALTER TABLE coffeemania_dish_restrictions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()")
    conn.commit()


def pull_menu() -> tuple[int, int]:
    dishes = _fetch("Dishes")
    if not dishes:
        log.warning("menu: пустой ответ Info API - обновление пропущено (данные сохранены)")
        return 0, 0
    all_rows = [classify_dish(d) for d in dishes if d.get("sku")]
    rows = [r for r in all_rows if r["is_active"]]  # снятые с продажи не грузим в базу
    params = [
        (r["sku"], r["name"], r["price"], json.dumps(r["categories"], ensure_ascii=False),
         r["calories"], r["fats"], r["proteins"], r["carbohydrates"], r["composition"],
         json.dumps(r["allergens"]), json.dumps(r["available_departments"]),
         r["is_recommendable"], r["is_popular"])
        for r in rows
    ]
    conn = _connect()
    try:
        _ensure_tables(conn)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM coffeemania_menu")
            execute_batch(cur, """
                INSERT INTO coffeemania_menu
                    (sku, name, price, categories, calories, fats, proteins, carbohydrates,
                     composition, allergens, available_departments, is_recommendable, is_popular, updated_at)
                VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,NOW())
            """, params, page_size=500)
        conn.commit()
    finally:
        conn.close()
    reco = sum(1 for r in rows if r["is_recommendable"])
    log.info("menu pulled: %d active dishes, %d recommendable (of %d total)", len(rows), reco, len(all_rows))
    return len(rows), reco


def pull_stoplists() -> int:
    restrictions = _fetch("DishRestrictions")
    if not restrictions:
        log.warning("stoplists: пустой ответ Info API - обновление пропущено (данные сохранены)")
        return 0
    params = [
        (str(x["sku"]), json.dumps(list(x.get("departments") or [])))
        for x in restrictions if x.get("sku")
    ]
    conn = _connect()
    try:
        _ensure_tables(conn)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM coffeemania_dish_restrictions")
            execute_batch(cur, """
                INSERT INTO coffeemania_dish_restrictions (sku, departments, updated_at)
                VALUES (%s, %s::jsonb, NOW())
            """, params, page_size=500)
        conn.commit()
    finally:
        conn.close()
    log.info("stoplists pulled: %d skus", len(params))
    return len(params)
