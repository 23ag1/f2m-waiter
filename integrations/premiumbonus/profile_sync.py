"""
Двусторонняя синхронизация вкусового профиля Food2Mood ↔ PremiumBonus.

Что синхронизируется:
  F2M → PB  : демография (phone, fio, sex→gender, age→birth_date)
              + диетический сегмент (preferences → group_id, если маппинг настроен)
  PB → F2M  : баланс бонусов, статус лояльности, история покупок

Что НЕ хранится в PB (нет нативных полей):
  hate/avoid/novelty — остаются только в F2M БД.

Env vars (дополнительно к PremiumBonusClient):
  PB_GROUP_VEGETARIAN   — UUID группы для вегетарианцев
  PB_GROUP_LOW_CAL      — UUID группы «мало калорий»
  PB_GROUP_NO_PORK      — UUID группы «без свинины»
  PB_GROUP_DEFAULT      — UUID группы по умолчанию
"""

from __future__ import annotations
import os
import re
from datetime import datetime
from typing import Any, List, Dict, Optional, Tuple

from client import PremiumBonusClient

# ─────────────────────────────────────────────
# Маппинг: dietary preference → PB group_id
# Заполни через env или подставь UUID из личного кабинета PB
# ─────────────────────────────────────────────
_DIET_GROUP_MAP: dict[str, str] = {
    "vegetarian": os.getenv("PB_GROUP_VEGETARIAN", ""),
    "vegan": os.getenv("PB_GROUP_VEGETARIAN", ""),
    "low-calorie": os.getenv("PB_GROUP_LOW_CAL", ""),
    "мало калорий": os.getenv("PB_GROUP_LOW_CAL", ""),
    "no-pork": os.getenv("PB_GROUP_NO_PORK", ""),
    "без свинины": os.getenv("PB_GROUP_NO_PORK", ""),
    "без глютена": os.getenv("PB_GROUP_DEFAULT", ""),
}


def _parse_fio(fio: str | None) -> tuple[str, str, str]:
    """Разбивает ФИО на составляющие."""
    if not fio:
        return "", "", ""
    parts = fio.strip().split()
    surname = parts[0] if len(parts) > 0 else ""
    name = parts[1] if len(parts) > 1 else ""
    middle_name = parts[2] if len(parts) > 2 else ""
    return surname, name, middle_name


def _f2m_sex_to_pb_gender(sex: str | None) -> str:
    if sex == "male":
        return "male"
    if sex == "female":
        return "female"
    return ""


def _f2m_age_to_birth_date(age: str | None) -> str:
    """
    F2M хранит birthdate в DD.MM.YYYY (из QuestionnaireRequest).
    PB принимает YYYY-MM-DD.
    """
    if not age:
        return ""
    m = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", age.strip())
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    # Уже в ISO формате
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", age.strip()):
        return age.strip()
    return ""


def _resolve_group_id(preferences: list[str] | None) -> str:
    """
    Берёт первый матч из списка dietary preferences → group_id PB.
    Если ничего не подошло — возвращает PB_GROUP_DEFAULT.
    """
    if not preferences:
        return os.getenv("PB_GROUP_DEFAULT", "")
    for pref in preferences:
        gid = _DIET_GROUP_MAP.get(pref.lower(), "")
        if gid:
            return gid
    return os.getenv("PB_GROUP_DEFAULT", "")


# ─────────────────────────────────────────────
# Основной класс
# ─────────────────────────────────────────────

class TasteProfileSync:
    """
    Синхронизатор профилей между Food2Mood и PremiumBonus.

    Использование:
        sync = TasteProfileSync()

        # Отправить профиль в PB (первичная регистрация или обновление)
        result = await sync.push(profile_dict)

        # Получить лояльность из PB и обогатить профиль
        enriched = await sync.pull(phone)
    """

    def __init__(self) -> None:
        self.pb = PremiumBonusClient()

    async def push(self, profile: dict[str, Any]) -> dict[str, Any]:
        """
        Отправляет вкусовой профиль F2M → PremiumBonus.

        profile — dict из таблицы `profile` (asyncpg row → dict).

        Что отправляется:
          phone, fio → surname/name/middle_name
          sex → gender
          age (DD.MM.YYYY) → birth_date (YYYY-MM-DD)
          preferences → group_id (диетический сегмент)
          external_id = user_id (для обратной сверки)
        """
        phone = profile.get("phone") or ""
        if not phone:
            return {"success": False, "error_description": "phone отсутствует в профиле"}

        surname, name, middle_name = _parse_fio(profile.get("fio"))
        gender = _f2m_sex_to_pb_gender(profile.get("sex"))
        birth_date = _f2m_age_to_birth_date(profile.get("age"))

        preferences: list[str] = profile.get("preferences") or []
        group_id = _resolve_group_id(preferences)

        extra: dict[str, Any] = {}
        if group_id:
            extra["group_id"] = group_id

        user_id = profile.get("user_id")
        if user_id:
            extra["external_id"] = str(user_id)

        # Пробуем buyer-info — если уже есть, делаем edit, иначе register
        existing = await self.pb.get_buyer_info(phone)
        if existing.get("is_registered"):
            result = await self.pb.edit_buyer(
                phone,
                surname=surname,
                name=name,
                middle_name=middle_name,
                gender=gender,
                birth_date=birth_date,
                **extra,
            )
            result["_action"] = "updated"
        else:
            result = await self.pb.register_buyer(
                phone,
                surname=surname,
                name=name,
                middle_name=middle_name,
                gender=gender,
                birth_date=birth_date,
                registration_channel="Food2Mood",
                **extra,
            )
            result["_action"] = "registered"

        return result

    async def pull(self, phone: str) -> dict[str, Any]:
        """
        Получает данные покупателя из PB и возвращает обогащённый профиль.

        Возвращает dict с полями:
          pb_balance          — текущий баланс бонусов
          pb_group_name       — сегментная группа (строка)
          pb_card_number      — номер карты лояльности
          pb_bonus_inactive   — бонусы ожидают активации
          pb_is_registered    — зарегистрирован в PB
          pb_blocked          — заблокирован
          pb_purchase_count   — кол-во покупок (из purchase-list)
          pb_last_purchase_at — дата последней покупки
          synced_at           — время запроса
        """
        buyer = await self.pb.get_buyer_info(
            phone,
            extra_fields=["payments_amount"],
        )

        if not buyer.get("is_registered"):
            return {
                "pb_is_registered": False,
                "synced_at": datetime.utcnow().isoformat(),
            }

        # История покупок для дополнительного обогащения
        purchases_resp = await self.pb.get_buyer_purchases(phone)
        purchase_list: list[dict] = purchases_resp.get("list") or []
        last_purchase_at = ""
        if purchase_list:
            dates = [p.get("date") or p.get("created_at") or "" for p in purchase_list]
            dates = [d for d in dates if d]
            last_purchase_at = max(dates) if dates else ""

        return {
            "pb_is_registered": buyer.get("is_registered", False),
            "pb_blocked": buyer.get("blocked", False),
            "pb_balance": buyer.get("balance", 0),
            "pb_bonus_inactive": buyer.get("bonus_inactive", 0),
            "pb_balance_accumulated": buyer.get("balance_bonus_accumulated", 0),
            "pb_balance_present": buyer.get("balance_bonus_present", 0),
            "pb_card_number": buyer.get("card_number", ""),
            "pb_group_name": buyer.get("group_name", ""),
            "pb_client_id": buyer.get("client_id", ""),
            "pb_payments_amount": buyer.get("payments_amount", 0),
            "pb_purchase_count": len(purchase_list),
            "pb_last_purchase_at": last_purchase_at,
            "synced_at": datetime.utcnow().isoformat(),
        }

    async def push_and_pull(self, profile: dict[str, Any]) -> dict[str, Any]:
        """
        Отправляет профиль в PB и сразу возвращает актуальные данные лояльности.
        Удобно для онбординга: один вызов = регистрация + баланс.
        """
        phone = profile.get("phone") or ""
        push_result = await self.push(profile)
        loyalty = await self.pull(phone)
        return {
            "push": push_result,
            "loyalty": loyalty,
        }
