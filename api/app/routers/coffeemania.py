"""
Coffeemania recommendation adapter.

Публичные эндпоинты (coffemania/SPEC_AB_recommendations.md):
  POST /api/coffeemania/v1/recommendations   - выдача рекомендаций
  POST /api/coffeemania/v1/cart              - live-корзина (ре-ранк исключением)
  POST /api/coffeemania/v1/purchases         - выгрузка покупок (аналитика + профиль)
  POST /api/coffeemania/v1/admin/reload-menu - служебный ингест меню

Зоны: здесь адаптер (БД + вызовы движка через API). Логика ЦВП/скоринга и фичи
меню - зона движка (Дима). Пока меню не заведено в движок, персонализация
best-effort, а базовая выдача идёт cold-start из каталога в БД.
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.integrations import coffeemania_engine as engine
from app.integrations.coffeemania_menu import ingest_menu

router = APIRouter()

_API_KEY = os.getenv("COFFEEMANIA_API_KEY", "").strip()
_DATA_DIR = os.getenv("COFFEEMANIA_DATA_DIR", "/data/coffeemania")
_CART_TTL = os.getenv("COFFEEMANIA_CART_TTL", "4 hours")  # окно живой корзины


# ── Схема БД ──────────────────────────────────────────────────────────
def init_coffeemania_tables(db_pool):
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS coffeemania_menu (
                    sku TEXT PRIMARY KEY,
                    name TEXT,
                    price NUMERIC DEFAULT 0,
                    categories JSONB DEFAULT '[]'::jsonb,
                    calories NUMERIC DEFAULT 0,
                    fats NUMERIC DEFAULT 0,
                    proteins NUMERIC DEFAULT 0,
                    carbohydrates NUMERIC DEFAULT 0,
                    composition TEXT DEFAULT '',
                    allergens JSONB DEFAULT '[]'::jsonb,
                    available_departments JSONB DEFAULT '[]'::jsonb,
                    is_recommendable BOOLEAN DEFAULT FALSE,
                    is_popular BOOLEAN DEFAULT FALSE,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS coffeemania_dish_restrictions (
                    sku TEXT PRIMARY KEY,
                    departments JSONB DEFAULT '[]'::jsonb
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS coffeemania_guest_map (
                    id BIGSERIAL PRIMARY KEY,
                    guest_id TEXT UNIQUE NOT NULL,
                    user_id BIGINT GENERATED ALWAYS AS (id + 900000000) STORED UNIQUE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS coffeemania_requests (
                    recommendation_id TEXT PRIMARY KEY,
                    client_request_id TEXT,
                    guest_id TEXT,
                    user_id BIGINT,
                    department_id INTEGER,
                    engine_request_id TEXT DEFAULT '',
                    status TEXT,
                    shown_skus JSONB DEFAULT '[]'::jsonb,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # Поток A: живая корзина (для ре-ранка исключением). Текущее состояние
            # корзины гостя, одна строка на guest+sku, с TTL.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS coffeemania_cart (
                    guest_id TEXT NOT NULL,
                    sku TEXT NOT NULL,
                    department_id INTEGER,
                    session_id TEXT,
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (guest_id, sku)
                )
            """)
            # Поток B: выгрузка покупок (push от Кофемании) - аналитика + профиль.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS coffeemania_purchases (
                    id BIGSERIAL PRIMARY KEY,
                    order_id TEXT DEFAULT '',
                    line_no INTEGER DEFAULT 0,
                    guest_id TEXT,
                    user_id BIGINT,
                    sku TEXT,
                    qty NUMERIC,
                    purchased_at TEXT,
                    received_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE (order_id, sku, line_no)
                )
            """)
            # старый единый outcome разнесён на cart + purchases
            cur.execute("DROP TABLE IF EXISTS coffeemania_outcomes")
        conn.commit()
    finally:
        db_pool.putconn(conn)


# ── Auth ──────────────────────────────────────────────────────────────
def _check_auth(authorization: Optional[str]) -> None:
    if not _API_KEY:
        return  # dev-режим: ключ не задан
    token = ""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if token != _API_KEY:
        raise HTTPException(status_code=401, detail={"error": "unauthorized"})


# ── Модели (контракт спеки) ───────────────────────────────────────────
class RecRequest(BaseModel):
    request_id: Optional[str] = None
    guest_id: str
    department_id: int
    context: dict[str, Any] = Field(default_factory=dict)
    basket: list[str] = Field(default_factory=list)
    candidate_skus: Optional[list[str]] = None
    top_k: int = 10


class RecItem(BaseModel):
    sku: str
    name: str
    rank: int
    score: float
    reason: str = ""


class RecResponse(BaseModel):
    request_id: str
    guest_id: str
    status: str
    recommendations: list[RecItem]


class CartItem(BaseModel):
    sku: str
    action: str = "add"  # add | remove


class CartRequest(BaseModel):
    guest_id: str
    department_id: Optional[int] = None
    session_id: Optional[str] = None
    items: list[CartItem]


class PurchaseItem(BaseModel):
    sku: str
    qty: Optional[float] = None


class PurchaseOrder(BaseModel):
    guest_id: str
    order_id: Optional[str] = None
    occurred_at: Optional[str] = None
    items: list[PurchaseItem]


class PurchasesRequest(BaseModel):
    orders: list[PurchaseOrder]


# ── Хелперы ───────────────────────────────────────────────────────────
def _flatten_context(ctx: dict[str, Any] | None) -> dict[str, str]:
    return {
        str(k): str(v)
        for k, v in (ctx or {}).items()
        if v is not None and not isinstance(v, (dict, list))
    }


def _get_or_create_user(cur, guest_id: str) -> int:
    cur.execute("SELECT user_id FROM coffeemania_guest_map WHERE guest_id=%s", (guest_id,))
    row = cur.fetchone()
    if row:
        return int(row[0])
    cur.execute(
        "INSERT INTO coffeemania_guest_map (guest_id) VALUES (%s) "
        "ON CONFLICT (guest_id) DO NOTHING RETURNING user_id",
        (guest_id,),
    )
    row = cur.fetchone()
    if row:
        return int(row[0])
    cur.execute("SELECT user_id FROM coffeemania_guest_map WHERE guest_id=%s", (guest_id,))
    return int(cur.fetchone()[0])


def _candidate_pool(cur, department_id: int, candidate_skus, basket) -> list[dict]:
    """Рекомендуемые блюда, доступные в ресторане, вне корзины."""
    sql = """
        SELECT m.sku, m.name, m.price, m.categories, m.is_popular
        FROM coffeemania_menu m
        LEFT JOIN coffeemania_dish_restrictions r ON r.sku = m.sku
        WHERE m.is_recommendable = TRUE
          AND (r.departments IS NULL OR NOT (r.departments @> %s::jsonb))
          AND (m.available_departments = '[]'::jsonb OR m.available_departments @> %s::jsonb)
    """
    params: list[Any] = [json.dumps([department_id]), json.dumps([department_id])]
    if candidate_skus:
        sql += " AND m.sku = ANY(%s)"
        params.append([str(s) for s in candidate_skus])
    sql += " ORDER BY m.is_popular DESC, m.name ASC LIMIT 400"
    cur.execute(sql, params)

    basket_set = {str(b) for b in (basket or [])}
    pool: list[dict] = []
    for sku, name, price, categories, is_popular in cur.fetchall():
        if str(sku) in basket_set:
            continue
        cats = categories if isinstance(categories, list) else (json.loads(categories) if categories else [])
        pool.append({
            "sku": str(sku), "name": name, "price": float(price or 0),
            "categories": cats, "is_popular": bool(is_popular),
        })
    return pool


def _engine_order(user_id: int, top_k: int, context: dict[str, Any]) -> tuple[str, list[str]]:
    """Best-effort персонализация: возвращает (engine_request_id, [sku...])."""
    try:
        res = engine.score(user_id, top_k, _flatten_context(context))
    except Exception:
        return "", []
    engine_request_id = str(res.get("request_id") or "")
    order: list[str] = []
    for row in (res.get("results") or res.get("food_recommendations") or []):
        if not isinstance(row, dict):
            continue
        sku = str(row.get("dish_id") or row.get("sku") or row.get("object_id") or "")
        if sku:
            order.append(sku)
    return engine_request_id, order


# ── Эндпоинты ─────────────────────────────────────────────────────────
@router.post("/v1/recommendations", response_model=RecResponse)
def recommendations(
    payload: RecRequest,
    request: Request,
    authorization: Optional[str] = Header(None),
):
    _check_auth(authorization)
    db_pool = request.app.state.db_pool

    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            user_id = _get_or_create_user(cur, payload.guest_id)
            # живая корзина гостя (в пределах TTL) - исключаем её из выдачи (ре-ранк)
            cur.execute(
                "SELECT sku FROM coffeemania_cart "
                "WHERE guest_id=%s AND updated_at > NOW() - (%s)::interval",
                (payload.guest_id, _CART_TTL),
            )
            cart_skus = [r[0] for r in cur.fetchall()]
            basket = list(payload.basket or []) + cart_skus
            pool = _candidate_pool(cur, payload.department_id, payload.candidate_skus, basket)
        conn.commit()
    finally:
        db_pool.putconn(conn)

    engine_request_id, engine_skus = _engine_order(user_id, payload.top_k, payload.context)

    pool_by_sku = {d["sku"]: d for d in pool}
    ordered: list[dict] = []
    seen: set[str] = set()

    # 1. персонализация от движка (только те sku, что реально есть в каталоге)
    for sku in engine_skus:
        if sku in pool_by_sku and sku not in seen:
            ordered.append(pool_by_sku[sku])
            seen.add(sku)
    status = "ok" if ordered else "cold_start"

    # 2. добор из cold-start пула с разнообразием категорий
    seen_cats: set[str] = set()
    for d in pool:
        if len(ordered) >= payload.top_k:
            break
        if d["sku"] in seen:
            continue
        cat = d["categories"][0] if d["categories"] else ""
        if cat and cat in seen_cats:
            continue
        seen_cats.add(cat)
        ordered.append(d)
        seen.add(d["sku"])

    ordered = ordered[: payload.top_k]
    if not ordered:
        status = "cold_start"

    recs = [
        RecItem(
            sku=d["sku"], name=d["name"], rank=i,
            score=round(max(0.0, 1.0 - (i - 1) * 0.03), 3),
            reason="Популярное блюдо" if d.get("is_popular") else (d["categories"][0] if d["categories"] else ""),
        )
        for i, d in enumerate(ordered, 1)
    ]

    recommendation_id = payload.request_id or f"cmrec_{uuid.uuid4().hex[:12]}"

    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO coffeemania_requests
                    (recommendation_id, client_request_id, guest_id, user_id, department_id,
                     engine_request_id, status, shown_skus)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                ON CONFLICT (recommendation_id) DO UPDATE SET
                    status=EXCLUDED.status, engine_request_id=EXCLUDED.engine_request_id,
                    shown_skus=EXCLUDED.shown_skus
            """, (
                recommendation_id, payload.request_id, payload.guest_id, user_id,
                payload.department_id, engine_request_id, status,
                json.dumps([r.sku for r in recs]),
            ))
        conn.commit()
    finally:
        db_pool.putconn(conn)

    return RecResponse(
        request_id=recommendation_id,
        guest_id=payload.guest_id,
        status=status,
        recommendations=recs,
    )


@router.post("/v1/cart")
def cart(
    payload: CartRequest,
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """Поток A - живая корзина: только записываем состояние, реки не возвращаем.
    Ре-ранк исключением сработает на следующем /recommendations."""
    _check_auth(authorization)
    db_pool = request.app.state.db_pool
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            for item in payload.items:
                if item.action == "remove":
                    cur.execute(
                        "DELETE FROM coffeemania_cart WHERE guest_id=%s AND sku=%s",
                        (payload.guest_id, item.sku),
                    )
                else:
                    cur.execute("""
                        INSERT INTO coffeemania_cart (guest_id, sku, department_id, session_id, updated_at)
                        VALUES (%s,%s,%s,%s,NOW())
                        ON CONFLICT (guest_id, sku) DO UPDATE SET
                            department_id=EXCLUDED.department_id,
                            session_id=EXCLUDED.session_id, updated_at=NOW()
                    """, (payload.guest_id, item.sku, payload.department_id, payload.session_id))
            # чистим протухшие позиции этого гостя
            cur.execute(
                "DELETE FROM coffeemania_cart WHERE guest_id=%s AND updated_at < NOW() - (%s)::interval",
                (payload.guest_id, _CART_TTL),
            )
        conn.commit()
    finally:
        db_pool.putconn(conn)
    return {"status": "ok", "guest_id": payload.guest_id, "items": len(payload.items)}


@router.post("/v1/purchases")
def purchases(
    payload: PurchasesRequest,
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """Поток B - выгрузка покупок (push от Кофемании): пишем + кормим движок."""
    _check_auth(authorization)
    db_pool = request.app.state.db_pool

    to_engine: list[tuple[int, str, Optional[str]]] = []  # (user_id, sku, event_uuid)
    ingested = 0

    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            for order in payload.orders:
                user_id = _get_or_create_user(cur, order.guest_id)
                order_id = order.order_id or ""
                for line_no, item in enumerate(order.items, 1):
                    cur.execute("""
                        INSERT INTO coffeemania_purchases
                            (order_id, line_no, guest_id, user_id, sku, qty, purchased_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (order_id, sku, line_no) DO UPDATE SET qty=EXCLUDED.qty
                    """, (order_id, line_no, order.guest_id, user_id, item.sku, item.qty, order.occurred_at))
                    ingested += 1
                    event_uuid = f"{order_id}.{item.sku}.{line_no}" if order_id else None
                    to_engine.append((int(user_id), item.sku, event_uuid))
        conn.commit()
    finally:
        db_pool.putconn(conn)

    # best-effort: кормим профиль движка событиями покупок
    for user_id, sku, event_uuid in to_engine:
        try:
            engine.ingest_purchase(user_id, sku, event_uuid=event_uuid)
        except Exception:
            pass

    return {"status": "ok", "orders": len(payload.orders), "items": ingested}


@router.post("/v1/admin/reload-menu")
def reload_menu(request: Request, authorization: Optional[str] = Header(None)):
    _check_auth(authorization)
    try:
        stats = ingest_menu(request.app.state.db_pool, _DATA_DIR)
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail={"error": "menu_files_not_found", "path": _DATA_DIR})
    return {"status": "ok", **stats}
