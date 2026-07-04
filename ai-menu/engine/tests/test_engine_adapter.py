"""
Тесты на чистые функции engine_adapter (без БД):
- _profile_to_raw_questionnaire: наш Postgres-профиль → raw для Rec2.
- _strip_reason_key: 'hard_lactose' → 'lactose'.

Регресс-кейсы (case_1/2/3) от коллеги — integration-тесты на полный flow
лежат в test_recommend_e2e.py (требуют запущенный pool/cache).
"""
import json
from pathlib import Path

from app.services.recommendation.engine_adapter import (
    _profile_to_raw_questionnaire,
    _strip_reason_key,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_profile_to_raw_case_1_safety():
    """case_1: glutens allergy + грибы запрещены + хочу суп + полноценный обед."""
    profile = {
        "user_id": 1,
        "hate": ["Глютен"],
        "preferences": [],
        "avoid": ["Грибы"],
        "novelty": "dislike",
        "prefer": ["soup"],
        "hungry": "full",
    }
    raw = _profile_to_raw_questionnaire(profile)
    expected = json.loads((FIXTURES / "case_1_raw.json").read_text(encoding="utf-8"))
    assert raw == expected


def test_profile_to_raw_case_2_kbzhu():
    """case_2: low_calorie + high_protein + рыба + полноценный."""
    profile = {
        "user_id": 2,
        "hate": [],
        "preferences": ["Низкокалорийная диета", "Высокобелковая диета"],
        "avoid": [],
        "novelty": "mixed",
        "prefer": ["fish"],
        "hungry": "full",
    }
    raw = _profile_to_raw_questionnaire(profile)
    # Сравниваем без soft_negative_ingredients (его в case_2_raw нет).
    expected = json.loads((FIXTURES / "case_2_raw.json").read_text(encoding="utf-8"))
    # У нас satiety = "Хочу полноценный прием пищи", у case_2 — то же.
    assert raw["allergies_or_intolerances"] == expected["allergies_or_intolerances"]
    assert raw["persistent_preferences"] == expected["persistent_preferences"]
    assert raw["want_now"] == expected["want_now"]
    assert raw["satiety"] == expected["satiety"]


def test_profile_to_raw_case_3_adventure():
    """case_3: novelty=like + хочу мясо + быстро утолить голод."""
    profile = {
        "user_id": 3,
        "hate": [],
        "preferences": [],
        "avoid": [],
        "novelty": "like",
        "prefer": ["meat"],
        "hungry": "quick",
    }
    raw = _profile_to_raw_questionnaire(profile)
    expected = json.loads((FIXTURES / "case_3_raw.json").read_text(encoding="utf-8"))
    assert raw["want_now"] == expected["want_now"]
    assert raw["satiety"] == expected["satiety"]
    assert raw["experiment_mode"] == expected["experiment_mode"]


def test_profile_to_raw_empty_profile():
    """Пустой профиль (анкета не пройдена) → пустые поля."""
    profile = {"user_id": 0}
    raw = _profile_to_raw_questionnaire(profile)
    assert raw["allergies_or_intolerances"] == []
    assert raw["persistent_preferences"] == []
    assert raw["ingredient_bans"] == []
    assert raw["want_now"] == []
    assert raw["satiety"] == ""
    assert raw["experiment_mode"] == ""


def test_profile_to_raw_tablet_codes_translate_to_russian():
    """Tablet шлёт английские коды (meat/fish/...), Rec2 нужны русские слова."""
    profile = {
        "user_id": 0, "hate": [], "preferences": [], "avoid": [],
        "novelty": None,
        "prefer": ["meat", "fish", "soup", "vegetables", "spicy", "sweet"],
        "hungry": "snack",
    }
    raw = _profile_to_raw_questionnaire(profile)
    # Проверяем что коды стали русскими словами
    assert "Мясо" in raw["want_now"]
    assert "Рыба и морепродукты" in raw["want_now"]
    assert "Суп" in raw["want_now"]
    assert "Овощи" in raw["want_now"]
    assert "Острое" in raw["want_now"]
    assert "Сладкое" in raw["want_now"]
    assert raw["satiety"] == "Хочу перекусить"


def test_profile_to_raw_handles_none_novelty():
    """novelty=None → experiment_mode=''."""
    profile = {"user_id": 0, "novelty": None}
    raw = _profile_to_raw_questionnaire(profile)
    assert raw["experiment_mode"] == ""


def test_strip_reason_key_basic():
    assert _strip_reason_key("hard_lactose") == "lactose"
    assert _strip_reason_key("hard_gluten_unknown") == "gluten"
    assert _strip_reason_key("hard_pork_review_required") == "pork"


def test_strip_reason_key_no_prefix():
    """Без префикса hard_ оставляет как есть."""
    assert _strip_reason_key("vegan_conflict") == "vegan_conflict"


def test_strip_reason_key_only_unknown_suffix():
    assert _strip_reason_key("lactose_unknown") == "lactose"
