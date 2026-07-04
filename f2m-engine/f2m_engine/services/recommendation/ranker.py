"""
Ranker для /api/v1/rec_x5/get_rec.

Оборачивает движок Rec2 (recommend_via_engine) в нашу UX-структуру:
    {
      "recommended": [...лидер каждой категории...],
      "categories": [{category_id, category, dishes: [...]} ...]
    }

Лидер категории = первое блюдо после сортировки внутри категории по
final_score DESC. Если все блюда категории blocked (penalty -1000) —
лидер тоже blocked, но категория всё равно представлена в recommended
с warning-бэйджем.

Категории между собой отсортированы по скору лидера.

Контракт каждого блюда дополняется новыми полями (для UI):
    - ranking_score: float
    - blocked: bool
    - blocked_reasons: list[str]   # ["lactose", "gluten", ...]
    - unresolved: bool             # состав уточняется
    - score_components: dict       # 8 компонент scoring для дебага
    - explanation: str             # человеческое пояснение от движка
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from app.services.recommendation.engine_adapter import recommend_via_engine
from app.services.recommendation.profile_features import UserFeatureBag, profile_to_features

log = logging.getLogger(__name__)

# Сколько блюд в категории получают AI-комментарий
_AI_COMMENT_TOP_PER_CAT = 3
# Макс. блюд на один запрос в DeepSeek (600 max_tokens ~ 12 блюд по 50 символов)
_AI_COMMENT_MAX_TOTAL = 12

# Какие поля от engine-output пробрасываем в каждое блюдо.
_AUGMENT_FIELDS = (
    "ranking_score", "blocked", "blocked_reasons", "unresolved",
    "rank", "explanation", "warning_tags", "display_tags",
    "soft_negative_hit_key", "soft_negative_hit_keys", "soft_negative_rank_group",
)


async def rank_dishes(
    *,
    dishes: list[dict[str, Any]],
    profile: dict[str, Any] | None,
    formatter: Callable[[dict[str, Any]], dict[str, Any]],
    derived_dir: Path,
    request_context: dict[str, Any] | None = None,
    deepseek_api_key: str = "",
) -> dict[str, Any]:
    """
    Главный entry point.

    dishes — список row из menu_x5 (с поле features).
    profile — row из profile-таблицы (или None для анонима).
    formatter — _format_dish_x5: row из БД → наружный формат для UI.
    derived_dir — папка с dish_features_cache.json + dish_constraints.csv
                  (предварительно построена через rebuild_dish_constraints).
    deepseek_api_key — ключ для генерации AI-комментариев (опционально).

    Если профиля нет / пустой — fallback на default-структуру (порядок от
    БД, без ranking_score).
    """
    if not profile or _is_profile_empty(profile):
        log.info("rank_dishes: empty profile → fallback structure")
        return _default_structure(dishes, formatter)

    engine_out = recommend_via_engine(
        profile=profile,
        derived_dir=derived_dir,
        top_k=len(dishes),
        request_context=request_context or {},
    )
    scored: list[dict[str, Any]] = engine_out["scored"]

    # Маппим scoring-rows на наши БД-блюда по dish_id.
    dishes_by_id: dict[str, dict[str, Any]] = {
        str(d["dish_id"]): d for d in dishes
    }

    # Группируем по category_id, сохраняя порядок из scored (он уже DESC).
    cat_buckets: dict[int, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for scoring_row in scored:
        dish_id = str(scoring_row.get("dish_id", ""))
        dish = dishes_by_id.get(dish_id)
        if dish is None:
            continue
        cat_id = dish.get("category_id")
        if cat_id is None:
            continue
        cat_buckets.setdefault(int(cat_id), []).append((dish, scoring_row))

    # Лидер = первый pair в bucket (внутри уже DESC по скору).
    # Категории между собой сортируем по final_score лидера.
    cat_ids_sorted = sorted(
        cat_buckets.keys(),
        key=lambda cid: int(cat_buckets[cid][0][1].get("rank", 999999)),
    )

    recommended: list[dict[str, Any]] = []
    categories_out: list[dict[str, Any]] = []
    for cat_id in cat_ids_sorted:
        pairs = cat_buckets[cat_id]
        leader_dish, leader_score = pairs[0]
        recommended.append(_augment(formatter(leader_dish), leader_score))

        rest = pairs[1:]
        if not rest:
            continue
        categories_out.append({
            "category_id": cat_id,
            "category": str(leader_dish.get("category", "")),
            "dishes": [
                _augment(formatter(d), s) for d, s in rest
            ],
        })

    # AI-комментарии генерируются отдельным эндпоинтом после отрисовки меню.
    # Убрано из основного запроса чтобы меню грузилось быстро (~2 сек).

    return {"recommended": recommended, "categories": categories_out}


# ──────────────────────────────────────────────────────────────────────


_CAUTION_TAG = {
    "title": "Состав уточняется",
    "color": "#B45309",
    "bg": "#FEF3C7",
}


def _augment(
    dish_formatted: dict[str, Any],
    scoring_row: dict[str, Any],
) -> dict[str, Any]:
    """Добавляет в dish-объект поля от engine (final_score, blocked, etc)."""
    dish_formatted["ranking_score"] = round(
        float(scoring_row.get("final_score", 0.0)), 4
    )
    dish_formatted["blocked"] = bool(scoring_row.get("blocked", False))
    dish_formatted["blocked_reasons"] = list(scoring_row.get("blocked_reasons", []))
    dish_formatted["rank"] = int(scoring_row.get("rank", 0) or 0)
    dish_formatted["warning_tags"] = list(scoring_row.get("warning_tags", []))
    dish_formatted["display_tags"] = list(scoring_row.get("display_tags", []))
    dish_formatted["soft_negative_hit_key"] = str(scoring_row.get("soft_negative_hit_key", ""))
    dish_formatted["soft_negative_hit_keys"] = list(scoring_row.get("soft_negative_hit_keys", []))
    dish_formatted["soft_negative_rank_group"] = int(scoring_row.get("soft_negative_rank_group", 0) or 0)
    is_unresolved = bool(scoring_row.get("unresolved", False))
    dish_formatted["unresolved"] = is_unresolved
    # Янтарный тег первым в списке если unresolved (без блокировки).
    if is_unresolved and not dish_formatted.get("blocked", False):
        existing_tags = dish_formatted.get("dish_tags") or []
        dish_formatted["dish_tags"] = [_CAUTION_TAG, *existing_tags]
    dish_formatted["score_components"] = {
        k: scoring_row.get(k)
        for k in (
            "desired_content_match",
            "satiety_match",
            "nutrition_match",
            "cuisine_match",
            "familiarity_novelty_match",
            "temperature_match",
            "soft_negative_penalty",
            "soft_negative_rank_group",
            "diversity_bonus",
            "intent_coverage_bonus",
            "venue_boost",
        )
    }
    explanation = scoring_row.get("explanation")
    if explanation:
        # Не перетираем существующий ai_comment если он уже был
        if not dish_formatted.get("ai_comment"):
            dish_formatted["ai_comment"] = explanation
    return dish_formatted


async def _apply_ai_comments(
    recommended: list[dict[str, Any]],
    categories: list[dict[str, Any]],
    profile: dict[str, Any],
    api_key: str,
) -> None:
    """
    Генерирует AI-комментарии для первых _AI_COMMENT_TOP_PER_CAT блюд
    каждой категории (лидер из recommended + первые N-1 из categories.dishes).
    Результаты записываются напрямую в ai_comment каждого блюда.
    """
    from app.services.ai_comment import generate_dish_comments

    bag = profile_to_features(profile)

    # Собираем кандидатов: лидер + первые N-1 из rest каждой категории.
    # recommended[i] — лидер категории categories[i].
    candidates: list[dict[str, Any]] = []

    for i, dish in enumerate(recommended):
        candidates.append(dish)
        if i < len(categories):
            rest_dishes = categories[i].get("dishes") or []
            for d in rest_dishes[: _AI_COMMENT_TOP_PER_CAT - 1]:
                candidates.append(d)

    if not candidates:
        return

    candidates = candidates[:_AI_COMMENT_MAX_TOTAL]
    comments = await generate_dish_comments(bag, candidates, api_key)
    for dish in candidates:
        did = str(dish.get("internal_id", ""))
        comment = comments.get(did, "")
        if comment:
            dish["ai_comment"] = comment


def _is_profile_empty(profile: dict[str, Any]) -> bool:
    """Анкета считается пустой если ни одно из 6 полей не заполнено."""
    keys = ("hate", "preferences", "avoid", "novelty", "prefer", "hungry")
    for k in keys:
        v = profile.get(k)
        if v:
            return False
    return True


def _default_structure(
    dishes: list[dict[str, Any]],
    formatter: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Fallback: первое блюдо каждой категории в recommended, остальные в categories."""
    categories_map: dict[int, dict[str, Any]] = {}
    for dish in dishes:
        cat_id = dish.get("category_id")
        if cat_id is None:
            continue
        cat_id = int(cat_id)
        if cat_id not in categories_map:
            categories_map[cat_id] = {
                "category_id": cat_id,
                "category": dish.get("category", ""),
                "dishes": [],
            }
        categories_map[cat_id]["dishes"].append(formatter(dish))

    categories = list(categories_map.values())
    recommended = [cat["dishes"][0] for cat in categories if cat["dishes"]]
    rest_categories = []
    for cat in categories:
        if len(cat["dishes"]) > 1:
            rest_categories.append({
                "category_id": cat["category_id"],
                "category": cat["category"],
                "dishes": cat["dishes"][1:],
            })
    return {"recommended": recommended, "categories": rest_categories}
