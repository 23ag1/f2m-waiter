"""
Mock-движок для демо без реальных вызовов в LLM.

Включается переменной окружения MOCK_LLM=true. Гибридный режим:
  - Запрос про "Том Ям" → детальный сценарий с осмысленными фильтрами
    и персонализированными сообщениями.
  - Любой другой запрос → универсальный fallback по ключевым словам
    (без хождения в DeepSeek).
"""

from __future__ import annotations

import os
import random
import re
import time
from typing import Dict, List, Optional


def is_enabled() -> bool:
    return os.getenv("MOCK_LLM", "false").strip().lower() in ("1", "true", "yes", "on")


# ─────────────────────────────────────────────────────────────────────────────
# Детектор сценариев
# ─────────────────────────────────────────────────────────────────────────────

_TOM_YAM_PATTERNS = (
    r"том[ -]*ям",
    r"тайск\w+ суп",
)


def is_tom_yam(admin_request: str) -> bool:
    s = (admin_request or "").lower()
    return any(re.search(p, s) for p in _TOM_YAM_PATTERNS)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Mock извлечения фильтров
# ─────────────────────────────────────────────────────────────────────────────

_BASE_FILTERS = {
    "sex": None,
    "age_min": None,
    "age_max": None,
    "style": None,
    "blacklist_ingredients": [],
    "temp_state": None,
    "temp_category": None,
    "last_visit": None,
}


_KEYWORD_TO_CATEGORY = {
    "паст": "Паста",
    "пицц": "Пицца",
    "суп": "Супы",
    "стейк": "Мясо и птица",
    "бургер": "Горячие блюда",
    "рамен": "Японская кухня",
    "суши": "Японская кухня",
    "поке": "Поке",
    "салат": "Салаты",
    "десерт": "Десерты",
    "вок": "Вок",
    "хинкал": "Хинкали",
    "чебурек": "Чебуреки",
}


def mock_extract_filters(admin_request: str) -> dict:
    """Возвращает заранее заготовленный фильтр под распознанный сценарий."""
    out = dict(_BASE_FILTERS)
    text = (admin_request or "").lower()

    if is_tom_yam(admin_request):
        # Том Ям — острый тайский суп с креветками, кокосовым молоком, лемонграссом, чили
        out["temp_category"] = "Супы"
        out["blacklist_ingredients"] = [
            "креветки", "морепродукты", "перец чили",
            "кокосовое молоко", "лемонграсс",
        ]
        return out

    # Универсальный fallback: ищем категорию по ключевому слову
    for kw, cat in _KEYWORD_TO_CATEGORY.items():
        if kw in text:
            out["temp_category"] = cat
            break

    # Простая эвристика: если в запросе слово "острое/острый" — пометим "острое" как ингредиент
    if re.search(r"остр[ыоуа]", text):
        out["blacklist_ingredients"] = ["острое", "перец чили"]

    # "диета" → стиль
    if re.search(r"диет\w*", text):
        out["style"] = "диетическое"
    elif re.search(r"веган\w*", text):
        out["style"] = "веганство"
    elif re.search(r"вегетариан\w*", text):
        out["style"] = "вегетарианство"

    return out


# ─────────────────────────────────────────────────────────────────────────────
# 2. Mock генерации сообщений
# ─────────────────────────────────────────────────────────────────────────────

# Микрозадержка на сообщение — чтобы стрим в UI выглядел красиво
_MOCK_DELAY_MIN_MS = int(os.getenv("MOCK_LLM_DELAY_MIN_MS", "70"))
_MOCK_DELAY_MAX_MS = int(os.getenv("MOCK_LLM_DELAY_MAX_MS", "140"))


def _delay():
    if _MOCK_DELAY_MAX_MS <= 0:
        return
    ms = random.randint(_MOCK_DELAY_MIN_MS, _MOCK_DELAY_MAX_MS)
    time.sleep(ms / 1000.0)


def _first_name(fio: Optional[str]) -> str:
    if not fio:
        return "Друг"
    return fio.split()[0].strip() or "Друг"


def _has_kw(text: Optional[str], *kws: str) -> bool:
    s = (text or "").lower()
    return any(k in s for k in kws)


# Шаблоны под сегменты профиля для Том Яма
def _tom_yam_message(profile: dict) -> str:
    name = _first_name(profile.get("fio"))
    style = (profile.get("style") or "").lower()
    prefer = (profile.get("prefer") or "").lower()
    experiments = (profile.get("experiments") or "").lower()

    # 1. Любители тайской/острой кухни — энергично
    if _has_kw(prefer, "острое", "тайск", "том ям", "рамен", "азиатск"):
        return (
            f"{name}, для любителей острого — встречайте! 🌶️ "
            "Тот самый Том Ям — ароматный тайский суп с тонким балансом кислинки и пряностей. "
            "Уже в меню, ждём вас!"
        )

    # 2. Диета — упор на лёгкость
    if "диет" in style:
        return (
            f"{name}, новинка как раз для вашего стиля питания: Том Ям — "
            "лёгкий, ароматный суп с морепродуктами и тайскими специями. "
            "Низкокалорийный, согревающий, без лишнего масла."
        )

    # 3. Веган/вегетарианец — мягкое предложение овощной версии
    if "веган" in style or "вегетариан" in style:
        return (
            f"{name}, мы добавили в меню Том Ям — а ещё можем приготовить его в овощной версии без морепродуктов. "
            "Ароматный тайский суп с тофу и грибами — заходите попробовать."
        )

    # 4. Любители рыбы / морепродуктов
    if _has_kw(prefer, "рыб", "морепродукт", "суши", "сашими"):
        return (
            f"{name}, новинка для вас: Том Ям — знаменитый тайский суп с креветками и морепродуктами. "
            "Тот случай, когда тарелка супа становится событием."
        )

    # 5. Любители супов
    if _has_kw(prefer, "суп"):
        return (
            f"{name}, в меню новый суп — Том Ям. Ароматный, согревающий, "
            "с лёгкой остринкой и тонким балансом вкусов. Ждём вас!"
        )

    # 6. Готов к экспериментам
    if "эксперимент" in experiments:
        return (
            f"{name}, новинка для тех, кто любит пробовать что-то необычное: Том Ям — "
            "знаменитый тайский суп. Ароматы, которые запоминаются."
        )

    # 7. Дефолт — спокойное приглашение
    return (
        f"{name}, у нас в меню новинка — Том Ям. "
        "Тайский суп с морепродуктами, лёгкой остринкой и тонким ароматом специй. Заходите попробовать!"
    )


def _generic_message(admin_request: str, profile: dict) -> str:
    """Универсальный fallback — собирается из admin_request + имени."""
    name = _first_name(profile.get("fio"))
    # Срезаем admin_request до читаемой длины и убираем лишние пробелы
    pitch = re.sub(r"\s+", " ", (admin_request or "").strip())
    if len(pitch) > 140:
        pitch = pitch[:137].rstrip(",.;:- ") + "…"
    return f"{name}, у нас новости: {pitch} Будем рады видеть вас в нашем ресторане!"


def _llm_reasons_for_profile(profile: dict, scenario: str) -> List[str]:
    """
    LLM-style reasons (1-3 шт.) — добавляются к детерминированным.
    Цель: каждый профиль получает максимально содержательный персональный тег.
    """
    reasons: List[str] = []
    prefer = (profile.get("prefer") or "").lower()
    style = (profile.get("style") or "").lower()
    experiments = (profile.get("experiments") or "").lower()
    age = (profile.get("age") or "").lower()

    # ── Сценарий "Том Ям" — тэги под тайскую/острую/азиатскую тему ──
    if scenario == "tom_yam":
        # Самые целевые сегменты — приоритет
        if _has_kw(prefer, "том ям", "тайск"):
            reasons.append("фанат тайской кухни")
        elif _has_kw(prefer, "острое", "острая"):
            reasons.append("любит острое")
        elif _has_kw(prefer, "рамен", "азиатск", "японск"):
            reasons.append("любит азиатскую кухню")
        elif _has_kw(prefer, "морепродукт", "креветк", "сашими", "суши"):
            reasons.append("любит морепродукты")
        elif _has_kw(prefer, "рыб"):
            reasons.append("любит рыбу")
        elif _has_kw(prefer, "суп"):
            reasons.append("любит супы")

        # Дополнительные стили
        if "диет" in style:
            reasons.append("следит за рационом")
        elif "веган" in style:
            reasons.append("веган — нужна овощная версия")
        elif "вегетариан" in style:
            reasons.append("вегетарианский стиль")

        # Готовность к новинкам
        if "эксперимент" in experiments and not reasons:
            reasons.append("любит пробовать новое")

        if not reasons:
            reasons.append("подойдёт под новинку")
        return reasons[:2]

    # ── Универсальный fallback под любые другие запросы ──
    # Приоритет — самый специфичный признак prefer
    if _has_kw(prefer, "том ям", "тайск"):
        reasons.append("любит тайскую кухню")
    elif _has_kw(prefer, "острое", "острая"):
        reasons.append("любит острое")
    elif _has_kw(prefer, "паст"):
        reasons.append("любит пасту")
    elif _has_kw(prefer, "пицц"):
        reasons.append("любит пиццу")
    elif _has_kw(prefer, "бургер"):
        reasons.append("любит бургеры")
    elif _has_kw(prefer, "стейк", "мясо"):
        reasons.append("любит мясо")
    elif _has_kw(prefer, "суши", "рамен", "японск"):
        reasons.append("любит японскую кухню")
    elif _has_kw(prefer, "морепродукт", "креветк", "сашими"):
        reasons.append("любит морепродукты")
    elif _has_kw(prefer, "рыб"):
        reasons.append("любит рыбу")
    elif _has_kw(prefer, "тофу", "хумус"):
        reasons.append("любит растительную кухню")
    elif _has_kw(prefer, "суп"):
        reasons.append("любит супы")
    elif _has_kw(prefer, "салат"):
        reasons.append("любит салаты")
    elif _has_kw(prefer, "десерт", "сыр"):
        reasons.append("любит десерты")

    # Стили
    if "диет" in style:
        reasons.append("на диете")
    elif "веган" in style:
        reasons.append("веган")
    elif "вегетариан" in style:
        reasons.append("вегетарианец")

    # Готовность к новинкам
    if "эксперимент" in experiments and not reasons:
        reasons.append("любит пробовать новое")

    if not reasons:
        reasons.append("подойдёт под новинку")
    return reasons[:2]


def mock_generate_message(admin_request: str, profile: dict) -> dict:
    """Возвращает payload в формате, ожидаемом broadcast_service."""
    _delay()

    if is_tom_yam(admin_request):
        text = _tom_yam_message(profile)
        scenario = "tom_yam"
    else:
        text = _generic_message(admin_request, profile)
        scenario = "generic"

    return {
        "text": text,
        "reasons": _llm_reasons_for_profile(profile, scenario),
    }
