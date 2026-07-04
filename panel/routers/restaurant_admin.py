"""Restaurant admin panel API.

Tag overrides  → f2m_platform DB (display-layer tags for waiter/ai-menu)
Rec settings   → f2m-engine /config/settings  (engine reads this at scoring time)
Rules          → f2m_platform DB custom_rules  (read-only text display)
"""
import asyncio
import hmac
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from database import get_pool
from services.cvp_service import describe_profile_row, age_to_range

ADMIN_KEY = os.getenv("ADMIN_API_KEY", "")
ENGINE_URL = os.getenv("F2M_ENGINE_URL", "http://f2m-engine:1488").rstrip("/")
log = logging.getLogger(__name__)
router = APIRouter()

_settings_lock = asyncio.Lock()  # prevent lost-update race on concurrent settings PATCH

_TAXONOMY_FILE = Path("/app/taxonomy.json")
ENGINE_MANUAL_TAG_AXES = {"taste", "ingredient", "cuisine", "format_texture", "context", "nutrition"}

SYSTEM_RULES = [
    {"id": "sys_allergy", "text": "Учитывать аллергии и диеты — блюда с аллергенами из профиля гостя никогда не попадают в рекомендации"},
    {"id": "sys_stoplist", "text": "Проверять доступность блюд — блюда из стоп-листа POS не рекомендуются"},
    {"id": "sys_alcohol", "text": "Не предлагать алкоголь без запроса — только если гость сам выбрал его в сессии или попросил официанта"},
]


def _check_admin_key(key: str | None) -> None:
    if not ADMIN_KEY or not key or not hmac.compare_digest(key, ADMIN_KEY):
        raise HTTPException(401, "invalid admin key")


def _is_team_key(key: str | None) -> bool:
    """True if the request comes from our team (master ADMIN_API_KEY)."""
    return bool(ADMIN_KEY and key and hmac.compare_digest(key, ADMIN_KEY))


# ─── Engine helpers ───────────────────────────────────────────────────

async def _engine_get_settings() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(f"{ENGINE_URL}/config/settings")
        r.raise_for_status()
        return r.json()


async def _engine_patch_settings(patch: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.patch(f"{ENGINE_URL}/config/settings", json=patch)
        r.raise_for_status()
        return r.json()


# ─── Pydantic models ──────────────────────────────────────────────────

class TagBody(BaseModel):
    tag: str

class PriorityDishBody(BaseModel):
    dish_id: int

class PriorityIngredientBody(BaseModel):
    ingredient: str

class RecommendationSetBody(BaseModel):
    name: str
    categories: list[str]

class BusinessGoalBody(BaseModel):
    key: str
    value: str


# ─── Display-layer tag helpers ────────────────────────────────────────

def _parse_base_tags(dish: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    raw_json = dish.get("dish_tags_json") or ""
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, list):
                tags.extend(str(t).strip() for t in parsed if t)
        except Exception:
            pass
    if not tags:
        val = dish.get("dish_tags") or ""
        tags.extend(t.strip() for t in val.split(",") if t.strip())
    return list(dict.fromkeys(tags))


def _apply_overrides(base: list[str], overrides: list[dict]) -> list[str]:
    removed = {o["tag"] for o in overrides if o["action"] == "remove"}
    added = [o["tag"] for o in overrides if o["action"] == "add"]
    result = [t for t in base if t not in removed]
    for t in added:
        if t not in result:
            result.append(t)
    return result


_tag_axis_map_cache: dict[str, str] | None = None


def _taxonomy_tag_axis_map() -> dict[str, str]:
    global _tag_axis_map_cache
    if _tag_axis_map_cache is not None:
        return _tag_axis_map_cache
    taxonomy = json.loads(_TAXONOMY_FILE.read_text(encoding="utf-8"))
    axes = taxonomy.get("storage_axes", {})
    result: dict[str, str] = {}
    for axis, values in axes.items():
        if axis not in ENGINE_MANUAL_TAG_AXES:
            continue
        if isinstance(values, list):
            for value in values:
                result[str(value)] = axis
        elif axis == "nutrition" and isinstance(values, dict):
            for value in values.get("boolean_tags", []):
                result[str(value)] = axis
            for value in values.get("satiety_class_values", []):
                result[str(value)] = axis
    aliases = taxonomy.get("aliases", {})
    if isinstance(aliases, dict):
        for alias, canonical in aliases.items():
            canonical_axis = result.get(str(canonical))
            if canonical_axis:
                result[str(alias)] = canonical_axis
    _tag_axis_map_cache = result
    return result


async def _sync_engine_manual_tag_override(*, dish_id: int, tag: str, action: str) -> bool:
    axis = _taxonomy_tag_axis_map().get(tag)
    if not axis:
        return False
    async with _settings_lock:
        settings = await _engine_get_settings()
        rows = list(settings.get("manual_tag_overrides") or [])
        rows = [
            row
            for row in rows
            if not (
                str(row.get("dish_id")) == str(dish_id)
                and str(row.get("axis")) == axis
                and str(row.get("key")) == tag
            )
        ]
        rows.append(
            {
                "dish_id": str(dish_id),
                "axis": axis,
                "key": tag,
                "action": action,
                "source": "admin_panel",
            }
        )
        await _engine_patch_settings({"manual_tag_overrides": rows})
    return True


# ─── Теги меню (DB) ───────────────────────────────────────────────────

@router.get("/admin/menu-tags")
async def get_menu_tags(x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    pool = await get_pool()
    dishes = await pool.fetch(
        "SELECT dish_id, category, name, dish_tags, dish_tags_json FROM menu ORDER BY category, dish_id"
    )
    overrides = await pool.fetch(
        "SELECT dish_id, tag, action FROM menu_tag_overrides ORDER BY created_at"
    )
    ov_by_dish: dict[int, list] = {}
    for o in overrides:
        ov_by_dish.setdefault(o["dish_id"], []).append(dict(o))
    result = []
    for d in dishes:
        dd = dict(d)
        base = _parse_base_tags(dd)
        tags = _apply_overrides(base, ov_by_dish.get(dd["dish_id"], []))
        result.append({"dish_id": dd["dish_id"], "category": dd["category"], "name": dd["name"], "tags": tags})
    return {"dishes": result}


@router.get("/admin/tag-registry")
async def get_tag_registry(x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    taxonomy = json.loads(_TAXONOMY_FILE.read_text(encoding="utf-8"))
    axes = taxonomy.get("storage_axes", {})
    tags = []
    for axis, values in axes.items():
        if isinstance(values, list):
            tags.extend({"axis": axis, "tag": v} for v in values)
        elif isinstance(values, dict):
            for value_list in values.values():
                if isinstance(value_list, list):
                    tags.extend({"axis": axis, "tag": v} for v in value_list)
    return {"tags": tags}


@router.post("/admin/menu-tags/{dish_id}/add-tag")
async def add_tag(dish_id: int, body: TagBody, x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    if not body.tag.strip():
        raise HTTPException(400, "empty tag")
    pool = await get_pool()
    await pool.execute(
        """INSERT INTO menu_tag_overrides (dish_id, tag, action)
           VALUES ($1, $2, 'add')
           ON CONFLICT (dish_id, tag)
           DO UPDATE SET action = 'add', created_at = now()""",
        dish_id, body.tag.strip(),
    )
    engine_synced = await _sync_engine_manual_tag_override(dish_id=dish_id, tag=body.tag.strip(), action="add")
    return {"ok": True, "engine_synced": engine_synced}


@router.delete("/admin/menu-tags/{dish_id}/remove-tag")
async def remove_tag(dish_id: int, tag: str = Query(...), x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    if not tag.strip():
        raise HTTPException(400, "empty tag")
    pool = await get_pool()
    await pool.execute(
        """INSERT INTO menu_tag_overrides (dish_id, tag, action)
           VALUES ($1, $2, 'remove')
           ON CONFLICT (dish_id, tag)
           DO UPDATE SET action = 'remove', created_at = now()""",
        dish_id, tag.strip(),
    )
    engine_synced = await _sync_engine_manual_tag_override(dish_id=dish_id, tag=tag.strip(), action="remove")
    return {"ok": True, "engine_synced": engine_synced}


# ─── ЦВП профили (DB) ────────────────────────────────────────────────

@router.get("/admin/cvp-profiles")
async def get_cvp_profiles(x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT user_id, fio, age, sex, prefer, hate, style, mood FROM profile ORDER BY user_id DESC LIMIT 500"
    )
    return {"profiles": [
        {
            "user_id": str(r["user_id"]),
            "fio": r.get("fio") or "",
            "age": age_to_range(r.get("age")),
            "sex": r.get("sex") or "",
            "taste_profile": describe_profile_row(dict(r)),
        }
        for r in rows
    ]}


# ─── Приоритетные блюда (engine) ─────────────────────────────────────

@router.get("/admin/priority-dishes")
async def get_priority_dishes(x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    settings = await _engine_get_settings()
    ids = settings.get("priority_dish_ids", [])
    ingredient_keys = settings.get("priority_ingredients", [])
    if not ids:
        return {"dishes": [], "priority_ingredients": ingredient_keys}
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT dish_id, name, category FROM menu WHERE dish_id = ANY($1::int[])",
        [int(i) for i in ids if str(i).isdigit()],
    )
    name_map = {str(r["dish_id"]): r for r in rows}
    dishes = [
        {
            "dish_id": i,
            "name": name_map.get(str(i), {}).get("name", f"ID {i}"),
            "category": name_map.get(str(i), {}).get("category", ""),
        }
        for i in ids
    ]
    return {"dishes": dishes, "priority_ingredients": ingredient_keys}


@router.post("/admin/priority-dishes")
async def add_priority_dish(body: PriorityDishBody, x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    async with _settings_lock:
        settings = await _engine_get_settings()
        ids = list(set(settings.get("priority_dish_ids", [])) | {str(body.dish_id)})
        await _engine_patch_settings({"priority_dish_ids": ids})
    return {"ok": True}


@router.post("/admin/priority-dishes/by-ingredient")
async def add_priority_by_ingredient(body: PriorityIngredientBody, x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    ingredient = body.ingredient.strip().lower()
    if not ingredient:
        raise HTTPException(400, "empty ingredient")
    pool = await get_pool()
    dishes = await pool.fetch(
        "SELECT dish_id, name, category FROM menu WHERE LOWER(ingredients) LIKE $1",
        f"%{ingredient}%",
    )
    async with _settings_lock:
        settings = await _engine_get_settings()
        current_ings = set(settings.get("priority_ingredients", []))
        new_ings = current_ings | {ingredient}
        await _engine_patch_settings({"priority_ingredients": list(new_ings)})
    return {"added": [dict(d) for d in dishes], "count": len(dishes)}


@router.delete("/admin/priority-ingredients/{ingredient}")
async def remove_priority_ingredient(ingredient: str, x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    async with _settings_lock:
        settings = await _engine_get_settings()
        ingredients = [
            item
            for item in settings.get("priority_ingredients", [])
            if str(item).strip().lower() != ingredient.strip().lower()
        ]
        await _engine_patch_settings({"priority_ingredients": ingredients})
    return {"ok": True}


@router.delete("/admin/priority-dishes/{dish_id}")
async def remove_priority_dish(dish_id: int, x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    async with _settings_lock:
        settings = await _engine_get_settings()
        ids = [i for i in settings.get("priority_dish_ids", []) if str(i) != str(dish_id)]
        await _engine_patch_settings({"priority_dish_ids": ids})
    return {"ok": True}


# ─── Стоп-лист (engine, read-only) ───────────────────────────────────

@router.get("/admin/stop-list")
async def get_stop_list(x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    settings = await _engine_get_settings()
    ids = settings.get("stop_list_dish_ids", [])
    if not ids:
        return {"dishes": [], "source": "POS (iiko)", "note": "Стоп-лист пуст или синхронизация с POS не настроена"}
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT dish_id, name, category FROM menu WHERE dish_id = ANY($1::int[])",
        [int(i) for i in ids if str(i).isdigit()],
    )
    name_map = {str(r["dish_id"]): r for r in rows}
    dishes = [
        {"dish_id": i, "name": name_map.get(str(i), {}).get("name", f"ID {i}"), "category": name_map.get(str(i), {}).get("category", "")}
        for i in ids
    ]
    return {"dishes": dishes, "source": "POS (iiko)"}


# ─── Бизнес-цели (engine) ────────────────────────────────────────────

@router.get("/admin/business-goals")
async def get_business_goals(x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    settings = await _engine_get_settings()
    bg = settings.get("business_goals") or {}
    return {
        "margin_mode": bool((bg.get("margin") or {}).get("enabled", False)),
        "upsell_mode": bool((bg.get("upsell") or {}).get("enabled", False)),
    }


@router.post("/admin/business-goals/toggle")
async def toggle_business_goal(body: BusinessGoalBody, x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    if body.key not in ("margin_mode", "upsell_mode"):
        raise HTTPException(400, "unknown key")
    enabled = body.value.lower() in ("true", "1", "yes")
    async with _settings_lock:
        settings = await _engine_get_settings()
        bg = dict(settings.get("business_goals") or {})
        engine_key = "margin" if body.key == "margin_mode" else "upsell"
        bg[engine_key] = {"enabled": enabled}
        await _engine_patch_settings({"business_goals": bg})
    return {"ok": True}


# ─── Сеты (engine) ───────────────────────────────────────────────────

@router.get("/admin/recommendation-sets")
async def get_recommendation_sets(x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    async with _settings_lock:
        settings = await _engine_get_settings()
        bg = dict(settings.get("business_goals") or {})
        sets = list(bg.get("sets") or [])
        if not isinstance(sets, list):
            sets = []
        if any(not s.get("id") for s in sets):
            for s in sets:
                if not s.get("id"):
                    s["id"] = str(uuid.uuid4())
            bg["sets"] = sets
            await _engine_patch_settings({"business_goals": bg})
        result = [{"id": s["id"], "name": s.get("name", ""), "categories": s.get("categories", []), "active": s.get("active", True)} for s in sets]
    return {"sets": result}


@router.post("/admin/recommendation-sets")
async def create_recommendation_set(body: RecommendationSetBody, x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    if not body.name.strip():
        raise HTTPException(400, "empty name")
    if not body.categories:
        raise HTTPException(400, "empty categories")
    new_id = str(uuid.uuid4())
    async with _settings_lock:
        settings = await _engine_get_settings()
        bg = dict(settings.get("business_goals") or {})
        sets = list(bg.get("sets") or [])
        sets.append({"id": new_id, "name": body.name.strip(), "categories": body.categories, "active": True})
        bg["sets"] = sets
        await _engine_patch_settings({"business_goals": bg})
    return {"id": new_id, "ok": True}


@router.patch("/admin/recommendation-sets/{set_id}/toggle")
async def toggle_recommendation_set(set_id: str, x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    async with _settings_lock:
        settings = await _engine_get_settings()
        bg = dict(settings.get("business_goals") or {})
        sets = list(bg.get("sets") or [])
        idx = next((i for i, s in enumerate(sets) if s.get("id") == set_id), None)
        if idx is None:
            raise HTTPException(404, "set not found")
        sets[idx] = dict(sets[idx])
        sets[idx]["active"] = not sets[idx].get("active", True)
        bg["sets"] = sets
        await _engine_patch_settings({"business_goals": bg})
        new_active = sets[idx]["active"]
    return {"active": new_active}


@router.delete("/admin/recommendation-sets/{set_id}")
async def delete_recommendation_set(set_id: str, x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    async with _settings_lock:
        settings = await _engine_get_settings()
        bg = dict(settings.get("business_goals") or {})
        sets = list(bg.get("sets") or [])
        idx = next((i for i, s in enumerate(sets) if s.get("id") == set_id), None)
        if idx is None:
            raise HTTPException(404, "set not found")
        sets.pop(idx)
        bg["sets"] = sets
        await _engine_patch_settings({"business_goals": bg})
    return {"ok": True}


# ─── Правила (DB, read-only) ──────────────────────────────────────────

@router.get("/admin/rules")
async def get_rules(x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, rule_type, rule_text, active FROM custom_rules WHERE active = true ORDER BY id"
    )
    return {
        "system_rules": SYSTEM_RULES,
        "custom_rules": [{"id": r["id"], "rule_type": r["rule_type"], "text": r["rule_text"]} for r in rows],
    }


# ─── Вспомогательные (меню для попапов) ──────────────────────────────

@router.get("/admin/menu-categories")
async def get_menu_categories(x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT DISTINCT category FROM menu WHERE category IS NOT NULL ORDER BY category"
    )
    return {"categories": [r["category"] for r in rows]}


@router.get("/admin/menu-list")
async def get_menu_list(x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    pool = await get_pool()
    rows = await pool.fetch("SELECT dish_id, name, category FROM menu ORDER BY category, name")
    return {"dishes": [dict(r) for r in rows]}


# ─── iiko ключи (DB) ─────────────────────────────────────────────────

class IikoKeyBody(BaseModel):
    restaurant_name: str
    api_key: str
    organization_id: str | None = None
    terminal_group_id: str | None = None
    client_secret: str | None = None
    app_id: str | None = None
    owner: str | None = None  # 'team' | 'client' — только team-ключ может задать


@router.get("/admin/iiko-keys")
async def get_iiko_keys(x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    pool = await get_pool()
    is_team = _is_team_key(x_admin_key)
    rows = await pool.fetch(
        "SELECT id, restaurant_name, api_key, organization_id, terminal_group_id, client_secret, app_id, owner, created_at FROM iiko_keys ORDER BY created_at DESC"
    )

    def _mask(val: str | None) -> str | None:
        return val if (not val or is_team) else val[:4] + "****"

    keys = []
    for r in rows:
        d = dict(r)
        d["api_key"] = _mask(d["api_key"])
        d["client_secret"] = _mask(d["client_secret"])
        keys.append(d)
    return {"keys": keys, "is_team": is_team}


@router.post("/admin/iiko-keys")
async def upsert_iiko_key(body: IikoKeyBody, x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    if not body.restaurant_name.strip():
        raise HTTPException(400, "empty restaurant_name")
    if not body.api_key.strip():
        raise HTTPException(400, "empty api_key")

    # owner: team может указать любой, остальные всегда client
    if _is_team_key(x_admin_key) and body.owner in ("team", "client"):
        owner = body.owner
    else:
        owner = "client"

    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO iiko_keys (restaurant_name, api_key, organization_id, terminal_group_id, client_secret, app_id, owner)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (restaurant_name) DO UPDATE SET
            api_key = EXCLUDED.api_key,
            organization_id = EXCLUDED.organization_id,
            terminal_group_id = EXCLUDED.terminal_group_id,
            client_secret = EXCLUDED.client_secret,
            app_id = EXCLUDED.app_id,
            owner = EXCLUDED.owner
        """,
        body.restaurant_name.strip(),
        body.api_key.strip(),
        body.organization_id,
        body.terminal_group_id,
        body.client_secret,
        body.app_id,
        owner,
    )
    return {"ok": True, "owner": owner}


@router.delete("/admin/iiko-keys/{restaurant_name}")
async def delete_iiko_key(restaurant_name: str, x_admin_key: str | None = Header(default=None)):
    _check_admin_key(x_admin_key)
    pool = await get_pool()
    if not _is_team_key(x_admin_key):
        row = await pool.fetchrow("SELECT owner FROM iiko_keys WHERE restaurant_name = $1", restaurant_name)
        if row and row["owner"] == "team":
            raise HTTPException(403, "only team can delete team-owned keys")
    result = await pool.execute("DELETE FROM iiko_keys WHERE restaurant_name = $1", restaurant_name)
    if result == "DELETE 0":
        raise HTTPException(404, "not found")
    return {"ok": True}
