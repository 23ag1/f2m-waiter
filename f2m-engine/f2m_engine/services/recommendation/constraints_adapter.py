"""
Адаптер между Postgres-слоем (`menu_x5.features` JSONB) и
вендорным движком Rec2 (`f2m_engine.pipelines.dish_constraints`).

Rec2 ожидает на входе файловую структуру:
  derived_dir/
    dish_features_cache.json   ← список dish-словарей (Stage A output)

build_dish_constraints читает этот JSON и пишет:
  derived_dir/
    dish_constraints.csv             ← готовые hard-flags на каждое блюдо
    dish_constraints_extraction_audit.csv  ← audit trail

Мы храним dish_features_cache в Postgres (`menu_x5.features` JSONB), поэтому
этот адаптер один раз при старте API экспортирует все блюда в JSON-файл,
после чего вызывает build_dish_constraints.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import asyncpg

from f2m_engine.pipelines.dish_constraints import build_dish_constraints

log = logging.getLogger(__name__)


async def export_features_cache(
    pool: asyncpg.Pool,
    derived_dir: Path,
) -> int:
    """
    Экспортирует все блюда из menu_x5 в формат `dish_features_cache.json`,
    который читает движок (Stage A → Stage B bridge).

    Возвращает количество экспортированных блюд.
    """
    derived_dir.mkdir(parents=True, exist_ok=True)
    rows = await pool.fetch(
        "SELECT dish_id, features FROM menu_x5 WHERE features IS NOT NULL"
    )
    dishes: list[dict[str, Any]] = []
    for row in rows:
        features = row["features"]
        if not isinstance(features, dict):
            continue
        # dish_id должен быть на верхнем уровне (string) — этого ждёт Rec2.
        dishes.append({"dish_id": str(row["dish_id"]), **features})

    cache_path = derived_dir / "dish_features_cache.json"
    cache_path.write_text(
        json.dumps(dishes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info("export_features_cache: wrote %d dishes to %s", len(dishes), cache_path)
    return len(dishes)


async def rebuild_dish_constraints(
    pool: asyncpg.Pool,
    derived_dir: Path,
) -> dict[str, int]:
    """
    Полная offline-разметка для движка Rec2:
    1. Экспорт menu_x5.features → dish_features_cache.json
    2. Запуск build_dish_constraints (Rec2) → dish_constraints.csv

    Должна вызываться один раз после rebuild_dish_features (или при
    обновлении меню). Идемпотентно — переписывает файлы целиком.
    """
    exported = await export_features_cache(pool, derived_dir)
    constraints = build_dish_constraints(derived_dir)
    log.info(
        "rebuild_dish_constraints: exported=%d, constraints=%d", exported, len(constraints)
    )
    return {"exported": exported, "constraints": len(constraints)}
