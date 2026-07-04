"""
Детерминистический скорер: user_bag × dish.features → score + top contributors.

Формула — упрощённая версия Rec/f2m 2/app/pipelines/scoring_deterministic.py:
взвешенное скалярное произведение user-вектора на dish-вектор по 6 осям.

Упрощения на текущей фазе:
- Нет hard filters: dish.features.hard_flags пустые, пока нет ingredient
  dictionary. Аллергии дают сильный negative вклад через _layer_match.
- Нет long_term/short_term слоёв: у нас explicit только (нет истории заказов).
- Нет novelty/repeat penalty: нет трекинга «уже видел».
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.recommendation.profile_features import UserFeatureBag
from app.services.recommendation.violations import compute_violations
from app.services.taxonomy import feature_keys as fk

# Penalty за каждое нарушение профиля (vegetarian + meat, allergy + dish и т.д.).
# Soft-фильтр: блюдо не выкидывается, но опускается вниз сортировки.
_VIOLATION_PENALTY = 1.0

# context_match: множитель как в scoring_deterministic.py:284-289 движка.
# Если клиент на /get_rec передаст request_context = ["lunch","quick"],
# блюда с этими же context-ключами получат +0.28 × avg_weight в скоре.
_CONTEXT_MATCH_WEIGHT = 0.28

# Веса осей из scoring_deterministic.py:14-20. Сумма ≈ 1.0.
AXIS_WEIGHTS: dict[str, float] = {
    fk.AXIS_TASTE: 0.22,
    fk.AXIS_INGREDIENT: 0.26,
    fk.AXIS_CUISINE: 0.20,
    fk.AXIS_FORMAT_TEXTURE: 0.17,
    fk.AXIS_CONTEXT: 0.15,
    fk.AXIS_NUTRITION: 0.10,  # наш add: satiety_class + boolean_tags
    # restriction большой — это soft-аналог hard-фильтра движка.
    # Когда dish_features.restriction появится (после ingredient-dictionary),
    # аллергия даст -0.5 penalty, фактически отодвигая блюдо в конец.
    fk.AXIS_RESTRICTION: 0.5,
}

# Сколько top-вкладчиков возвращать для объяснений.
_TOP_K_CONTRIBUTORS = 5


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    total: float
    # [(axis, feature_key, contribution), ...] отсортированы по |contribution| desc
    top_positive: list[tuple[str, str, float]]
    top_negative: list[tuple[str, str, float]]


def _extract_dish_axis(dish_features: dict[str, Any], axis: str) -> dict[str, float]:
    """
    Извлекает {feature_key: weight} по оси из JSONB блюда.

    Для nutrition особая логика: boolean_tags (low_calorie=true) трактуем
    как weight=1.0; satiety_class="hearty" — {hearty: 1.0}.
    """
    raw = dish_features.get(axis)
    if axis != fk.AXIS_NUTRITION:
        return raw if isinstance(raw, dict) else {}

    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for key, value in raw.items():
        if key == "satiety_class" and isinstance(value, str):
            out[value] = 1.0
        elif isinstance(value, bool) and value:
            out[key] = 1.0
        elif isinstance(value, (int, float)):
            out[key] = float(value)
    return out


def score_dish(
    user: UserFeatureBag,
    dish_features: dict[str, Any] | None,
    request_context: list[str] | None = None,
) -> ScoreBreakdown:
    """
    Возвращает суммарный score (может быть отрицательным) и top-contributors.
    Если dish_features=None (меню ещё не перестроено), score=0, списки пустые.

    request_context — список context-ключей из запроса (time_of_day, hunger
    level и т.п.). Если передан и у блюда есть совпадения по context-оси —
    добавится context_match bonus (+0.28 × avg_weight).
    """
    if not dish_features:
        return ScoreBreakdown(total=0.0, top_positive=[], top_negative=[])

    contributions: list[tuple[str, str, float]] = []

    for axis, axis_weight in AXIS_WEIGHTS.items():
        user_axis = user.by_axis.get(axis, {})
        dish_axis = _extract_dish_axis(dish_features, axis)
        if not user_axis or not dish_axis:
            continue
        for feature_key, user_signed in user_axis.items():
            dish_value = dish_axis.get(feature_key, 0.0)
            if dish_value == 0.0:
                continue
            contribution = user_signed * dish_value * axis_weight
            contributions.append((axis, feature_key, contribution))

    # Context-bonus от текущего запроса (независим от profile).
    if request_context:
        dish_context = _extract_dish_axis(dish_features, fk.AXIS_CONTEXT)
        matched = [dish_context[k] for k in request_context if k in dish_context]
        if matched:
            ctx_bonus = _CONTEXT_MATCH_WEIGHT * sum(matched) / len(request_context)
            contributions.append((fk.AXIS_CONTEXT, "request_match", ctx_bonus))

    # Soft-penalty за нарушения (vegetarian, hate-аллергены, avoid-ингредиенты).
    # Каждое нарушение опускает блюдо в выдаче, но не выкидывает.
    # try/except — defensive: даже если violations упадёт на странном dish,
    # основной скоринг не должен ломаться.
    try:
        violations = compute_violations(user, dish_features)
    except Exception:
        violations = []
    for v in violations:
        contributions.append((fk.AXIS_RESTRICTION, f"violation:{v}", -_VIOLATION_PENALTY))

    total = sum(c[2] for c in contributions)
    contributions.sort(key=lambda x: abs(x[2]), reverse=True)

    positives = [c for c in contributions if c[2] > 0][:_TOP_K_CONTRIBUTORS]
    negatives = [c for c in contributions if c[2] < 0][:_TOP_K_CONTRIBUTORS]

    return ScoreBreakdown(total=total, top_positive=positives, top_negative=negatives)
