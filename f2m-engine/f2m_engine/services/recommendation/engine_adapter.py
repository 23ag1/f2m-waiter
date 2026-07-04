"""
Адаптер вызова Rec2-движка questionnaire-only с soft-blocking логикой.

Концепция:
1. Передаём ВСЕ блюда в scorer (а не только safe), получаем рейтинг по 8
   компонентам.
2. Параллельно прогоняем apply_questionnaire_hard_filter — получаем blocked
   reasons для меток на UI.
3. Помечаем blocked + добавляем penalty -1000 → они автоматически уходят
   в самый низ списка, но НЕ исчезают из выдачи (продуктовое требование:
   юзер видит всё меню, бэйдж warning подсказывает почему блюдо ниже).
4. unresolved (parse_confidence < 0.75 / нет ингредиентов) — отдельный флаг
   БЕЗ score-penalty: на UI мягкая пометка «Состав уточняется».

Profile в Postgres → raw_questionnaire dict вид как в case_*.json.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from f2m_engine.domain.recommendation_settings import load_recommendation_settings
from f2m_engine.pipelines.dish_constraints import (
    apply_questionnaire_hard_filter,
    build_dish_constraints,
)
from f2m_engine.pipelines.questionnaire_logging import (
    next_questionnaire_request_id,
)
from f2m_engine.pipelines.questionnaire_normalizer import (
    normalize_questionnaire,
)
from f2m_engine.pipelines.questionnaire_scoring import (
    score_questionnaire_candidates,
)

log = logging.getLogger(__name__)

BLOCKED_PENALTY = -1000.0


# ──────────────────────────────────────────────────────────────────────
# profile (БД) → raw_questionnaire (формат Rec2 case_*.json)
# ──────────────────────────────────────────────────────────────────────

# Tablet шлёт коды (meat/fish/...), Rec2 normalizer ищет русские слова.
_FOOD_DESIRE_TO_RU: dict[str, str] = {
    "vegetables": "Овощи",
    "meat": "Мясо",
    "fish": "Рыба и морепродукты",
    "soup": "Суп",
    "spicy": "Острое",
    "sweet": "Сладкое",
    "light": "Лёгкое",
    "hot": "Горячее",
}

_HUNGRY_TO_RU: dict[str, str] = {
    "snack": "Хочу перекусить",
    "quick": "Хочу быстро утолить голод",
    "full": "Хочу полноценный прием пищи",
}

_NOVELTY_TO_RU: dict[str, str] = {
    "like": "Да, нравятся необычные сочетания",
    "dislike": "Нет, люблю знакомые вкусы",
    "mixed": "Иногда люблю экспериментировать",
}


def _profile_to_raw_questionnaire(profile: dict[str, Any]) -> dict[str, Any]:
    """
    Наш Postgres-профиль → raw_questionnaire в формате который ожидает
    f2m_engine.pipelines.questionnaire_normalizer.

    Имена полей подобраны так, чтобы normalizer корректно классифицировал
    значения по hard_constraints / soft_preferences / request_context:
    - 'allerg'-подстрока в имени → попадает в hard_constraints.allergens
    - 'ban'/'exclude'-подстрока → hard_constraints.ingredient_excludes
    - 'experiment'/'novelty' → soft_preferences.familiarity_novelty
    - 'want_now' → request_context.want_now
    - 'satiety' → request_context.satiety
    """
    hate = profile.get("hate") or []
    preferences = profile.get("preferences") or []
    avoid = profile.get("avoid") or []
    prefer = profile.get("prefer") or []
    novelty = profile.get("novelty")
    hungry = profile.get("hungry")

    return {
        "allergies_or_intolerances": list(hate),
        "persistent_preferences": list(preferences),
        "ingredient_bans": list(avoid),
        "experiment_mode": _NOVELTY_TO_RU.get(novelty or "", ""),
        "want_now": [_FOOD_DESIRE_TO_RU.get(v, v) for v in prefer if v],
        "satiety": _HUNGRY_TO_RU.get(hungry or "", ""),
    }


# ──────────────────────────────────────────────────────────────────────
# Главная функция: profile → top-N с soft-blocking
# ──────────────────────────────────────────────────────────────────────

def recommend_via_engine(
    *,
    profile: dict[str, Any],
    derived_dir: Path,
    top_k: int = 50,
    request_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Возвращает dict:
      - scored: list[dict]  — все блюда отсортированы по final_score DESC,
                              каждое содержит blocked/blocked_reasons/unresolved
      - normalized_profile: dict
      - filter_summary: dict (counts для логирования)
    """
    request_context = dict(request_context or {})
    recommendation_settings = load_recommendation_settings(derived_dir)
    raw = _profile_to_raw_questionnaire(profile)

    normalized = normalize_questionnaire(
        raw_questionnaire=raw,
        request_context=request_context,
    )

    # Hard filter — для меток, не для отсева.
    constraints = build_dish_constraints(derived_dir)
    venue = str(request_context.get("venue", "") or "")
    request_id, _ = next_questionnaire_request_id(derived_dir)
    filter_result = apply_questionnaire_hard_filter(
        request_id=request_id,
        venue=venue,
        normalized_profile=normalized,
        dish_constraints=constraints,
    )

    # Маппинг dish_id → причина блокировки + тип (explicit/unresolved/review_required).
    blocked_map: dict[str, dict[str, str]] = {
        row["dish_id"]: {
            "key": row["blocked_reason_key"],
            "type": row["blocked_reason_type"],
        }
        for row in filter_result.blocked_rows
    }

    # Скорим ВСЕ блюда (включая blocked, напитки, соусы, кофе) без prefilter-фильтрации.
    all_prefilter = constraints
    scored, trace = score_questionnaire_candidates(
        request_id=request_id,
        user_id=int(profile.get("user_id", 0) or 0),
        normalized_profile=normalized,
        safe_candidates=all_prefilter,
        request_context=request_context,
        top_k=top_k,
        recommendation_settings=recommendation_settings,
    )

    # Soft-blocking: помечаем + сильный penalty.
    for row in scored:
        dish_id = str(row.get("dish_id", ""))
        blocked = blocked_map.get(dish_id)
        if blocked is None:
            row["blocked"] = False
            row["blocked_reasons"] = []
            row["unresolved"] = False
        else:
            reason_key = blocked["key"]
            reason_type = blocked["type"]
            # explicit_conflict → реальный аллерген; unresolved → состав неполный
            row["blocked"] = reason_type in {"explicit_conflict", "system_hard_rule"}
            row["unresolved"] = reason_type in {
                "unresolved",
                "review_required",
            }
            # Чистим reason_key от префиксов "hard_" / "_unknown" / "_review_required".
            row["blocked_reasons"] = [_strip_reason_key(reason_key)]
            if row["blocked"]:
                row["final_score"] = float(row["final_score"]) + BLOCKED_PENALTY
                row["score"] = row["final_score"]
            # unresolved БЕЗ penalty — продуктовое решение

    scored.sort(key=_ranked_output_sort_key)
    for idx, row in enumerate(scored, start=1):
        row["rank"] = idx

    return {
        "scored": scored,
        "normalized_profile": normalized,
        "filter_summary": {
            "candidate_count_before": filter_result.candidate_count_before,
            "candidate_count_after": filter_result.candidate_count_after,
            "blocked_count": filter_result.blocked_count,
            "blocked_reasons_summary": filter_result.blocked_reasons_summary,
        },
        "request_id": request_id,
        "trace": trace,
    }


def _strip_reason_key(key: str) -> str:
    """'hard_lactose' → 'lactose'; 'hard_gluten_unknown' → 'gluten'."""
    s = key
    if s.startswith("hard_"):
        s = s[len("hard_"):]
    for suf in ("_unknown", "_review_required"):
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s


def _ranked_output_sort_key(row: dict[str, Any]) -> tuple[int, float, str]:
    if bool(row.get("blocked", False)):
        rank_group = 2
    else:
        rank_group = int(row.get("soft_negative_rank_group", 0))
    return (
        rank_group,
        -float(row.get("final_score", 0.0)),
        str(row.get("dish_name", "")),
    )
