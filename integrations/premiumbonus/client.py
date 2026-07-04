from __future__ import annotations
import os
import re
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional, Dict

import httpx

logging.basicConfig(
    filename="PremiumBonusClient.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("PremiumBonusClient")

BASE_URL = "https://api.premiumbonus.su/v2"


@dataclass
class PurchaseItem:
    name: str
    amount: float
    quantity: float = 1.0
    external_item_id: str = ""
    discount: float = 0.0
    type: str = ""
    groups: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "amount": self.amount,
            "quantity": self.quantity,
        }
        if self.external_item_id:
            d["external_item_id"] = self.external_item_id
        if self.discount:
            d["discount"] = self.discount
        if self.type:
            d["type"] = self.type
        if self.groups:
            d["groups"] = self.groups
        if self.tags:
            d["tags"] = self.tags
        return d


class PremiumBonusClient:
    """
    Клиент для двусторонней интеграции с PremiumBonus API v2.

    Env vars:
        PREMIUMBONUS_API_TOKEN  — Bearer-токен (обязательно)
        PREMIUMBONUS_BASE_URL   — базовый URL (по умолчанию https://api.premiumbonus.su/v2)
        PREMIUMBONUS_SALE_POINT_ID — ID точки продаж (опционально, если токен без привязки)
    """

    def __init__(self) -> None:
        self.base_url = (os.getenv("PREMIUMBONUS_BASE_URL") or BASE_URL).rstrip("/")
        self.api_token = (os.getenv("PREMIUMBONUS_API_TOKEN") or "").strip()
        self.sale_point_id = (os.getenv("PREMIUMBONUS_SALE_POINT_ID") or "").strip()

        self.headers = {
            "Authorization": self.api_token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        if not self.api_token:
            logger.warning("PREMIUMBONUS_API_TOKEN is empty — all requests will fail")

    # ──────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────

    @staticmethod
    def _normalize_phone(value: Any) -> str:
        digits = "".join(filter(str.isdigit, str(value or "")))
        return digits if len(digits) == 11 else digits[-10:].zfill(11) if digits else ""

    @staticmethod
    def _extract_error(response: httpx.Response) -> str:
        try:
            body = response.json()
            return body.get("error_description") or str(body)[:500]
        except Exception:
            return response.text[:500]

    def _with_sale_point(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.sale_point_id and "sale_point_id" not in payload:
            payload["sale_point_id"] = self.sale_point_id
        return payload

    async def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                response = await client.post(url, headers=self.headers, json=payload)
                data = response.json()
                if response.status_code in (200, 201):
                    logger.info("OK | %s", endpoint)
                    return data
                error = self._extract_error(response)
                logger.error("FAIL | %s | %s | %s", response.status_code, endpoint, error)
                return {"success": False, "error_description": error}
            except Exception as exc:
                logger.error("Exception | %s | %s", endpoint, exc)
                return {"success": False, "error_description": str(exc)}

    async def _retry(self, endpoint: str, payload: dict[str, Any], attempts: int = 3) -> dict[str, Any]:
        last: dict[str, Any] = {}
        for attempt in range(attempts):
            last = await self._post(endpoint, payload)
            if last.get("success") is not False:
                return last
            if attempt < attempts - 1:
                await asyncio.sleep(2)
        return last

    # ──────────────────────────────────────────────
    # Покупатель (Buyer)
    # ──────────────────────────────────────────────

    async def register_buyer(
        self,
        phone: str,
        *,
        name: str = "",
        surname: str = "",
        middle_name: str = "",
        email: str = "",
        birth_date: str = "",
        gender: str = "",
        card_number: str = "",
        external_id: str = "",
        phone_checked: bool = False,
        registration_channel: str = "",
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        POST /buyer-register
        Регистрация нового покупателя в системе лояльности.
        """
        payload: dict[str, Any] = {"phone": self._normalize_phone(phone)}
        if name:
            payload["name"] = name
        if surname:
            payload["surname"] = surname
        if middle_name:
            payload["middle_name"] = middle_name
        if email:
            payload["email"] = email
        if birth_date:
            payload["birth_date"] = birth_date
        if gender:
            payload["gender"] = gender
        if card_number:
            payload["card_number"] = card_number
        if external_id:
            payload["external_id"] = external_id
        if phone_checked:
            payload["phone_checked"] = phone_checked
        if registration_channel:
            payload["registration_channel"] = registration_channel
        if extra:
            payload.update(extra)
        return await self._retry("buyer-register", payload)

    async def get_buyer_info(
        self,
        identificator: str,
        *,
        extra_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        POST /buyer-info
        Получение профиля покупателя и баланса бонусов.
        identificator — телефон, email, номер карты или код из SMS.
        """
        payload: dict[str, Any] = {"identificator": identificator}
        if self.sale_point_id:
            payload["sale_point_id"] = self.sale_point_id
        if extra_fields:
            payload["extra_fields"] = extra_fields
        return await self._post("buyer-info", payload)

    async def edit_buyer(self, phone: str, **fields: Any) -> dict[str, Any]:
        """
        POST /buyer-edit
        Обновление данных покупателя.
        """
        payload: dict[str, Any] = {"phone": self._normalize_phone(phone), **fields}
        return await self._retry("buyer-edit", payload)

    async def get_buyer_bonus(self, phone: str) -> dict[str, Any]:
        """
        POST /buyer-bonus
        Получение бонусных пакетов и баланса покупателя.
        """
        return await self._post("buyer-bonus", {"phone": self._normalize_phone(phone)})

    async def get_buyer_purchases(self, phone: str) -> dict[str, Any]:
        """
        POST /buyer/purchase-list
        История покупок покупателя.
        """
        return await self._post("buyer/purchase-list", {"phone": self._normalize_phone(phone)})

    # ──────────────────────────────────────────────
    # Покупки (Purchase)
    # ──────────────────────────────────────────────

    async def purchase_request(
        self,
        identificator: str,
        items: list[PurchaseItem],
        *,
        promocode: str = "",
        sale_channel: str = "",
        discount: float = 0.0,
    ) -> dict[str, Any]:
        """
        POST /purchase-request
        Получение информации о покупателе + максимальной доступной выгоды
        (скидки + бонусы) перед оформлением покупки.
        """
        payload: dict[str, Any] = {
            "identificator": identificator,
            "items": [i.to_dict() for i in items],
        }
        self._with_sale_point(payload)
        if promocode:
            payload["promocode"] = promocode
        if sale_channel:
            payload["sale_channel"] = sale_channel
        if discount:
            payload["discount"] = discount
        return await self._post("purchase-request", payload)

    async def purchase_dry_run(
        self,
        phone: str,
        items: list[PurchaseItem],
        *,
        write_off_bonus: float = 0.0,
        promocode: str = "",
        sale_channel: str = "",
        discount: float = 0.0,
    ) -> dict[str, Any]:
        """
        POST /purchase-dry-run
        Эмуляция проведения покупки без реального начисления бонусов.
        """
        payload: dict[str, Any] = {
            "phone": self._normalize_phone(phone),
            "items": [i.to_dict() for i in items],
        }
        self._with_sale_point(payload)
        if write_off_bonus:
            payload["write_off_bonus"] = write_off_bonus
        if promocode:
            payload["promocode"] = promocode
        if sale_channel:
            payload["sale_channel"] = sale_channel
        if discount:
            payload["discount"] = discount
        return await self._post("purchase-dry-run", payload)

    async def add_purchase(
        self,
        items: list[PurchaseItem],
        *,
        identificator: str = "",
        phone: str = "",
        external_purchase_id: str = "",
        write_off_bonus: float = 0.0,
        discount: float = 0.0,
        promocode: str = "",
        sale_channel: str = "",
        cashier_name: str = "",
        waiters_names: list[str] | None = None,
        purchase_status: str = "approved",
    ) -> dict[str, Any]:
        """
        POST /purchase
        Добавление покупки и начисление бонусов.
        """
        if not identificator and not phone:
            raise ValueError("Нужен identificator или phone")
        payload: dict[str, Any] = {"items": [i.to_dict() for i in items]}
        if identificator:
            payload["identificator"] = identificator
        if phone:
            payload["phone"] = self._normalize_phone(phone)
        self._with_sale_point(payload)
        if external_purchase_id:
            payload["external_purchase_id"] = external_purchase_id
        if write_off_bonus:
            payload["write_off_bonus"] = write_off_bonus
        if discount:
            payload["discount"] = discount
        if promocode:
            payload["promocode"] = promocode
        if sale_channel:
            payload["sale_channel"] = sale_channel
        if cashier_name:
            payload["cashier_name"] = cashier_name
        if waiters_names:
            payload["waiters_names"] = waiters_names
        if purchase_status:
            payload["purchase_status"] = purchase_status
        return await self._retry("purchase", payload)

    async def cancel_purchase(
        self,
        *,
        purchase_id: str = "",
        external_purchase_id: str = "",
    ) -> dict[str, Any]:
        """
        POST /cancel-purchase
        Отмена покупки и возврат бонусов.
        """
        if not purchase_id and not external_purchase_id:
            raise ValueError("Нужен purchase_id или external_purchase_id")
        payload: dict[str, Any] = {}
        if purchase_id:
            payload["purchase_id"] = purchase_id
        if external_purchase_id:
            payload["external_purchase_id"] = external_purchase_id
        return await self._retry("cancel-purchase", payload)

    async def get_purchase_info(self, external_purchase_id: str) -> dict[str, Any]:
        """
        POST /purchase-info
        Информация о конкретной покупке.
        """
        return await self._post("purchase-info", {"external_purchase_id": external_purchase_id})

    async def write_off_request(
        self,
        phone: str,
        items: list[PurchaseItem],
        *,
        promocode: str = "",
        sale_channel: str = "",
        discount: float = 0.0,
    ) -> dict[str, Any]:
        """
        POST /write-off-request
        Получение максимально доступной выгоды (скидки + бонусы) для списания.
        """
        payload: dict[str, Any] = {
            "phone": self._normalize_phone(phone),
            "items": [i.to_dict() for i in items],
        }
        self._with_sale_point(payload)
        if promocode:
            payload["promocode"] = promocode
        if sale_channel:
            payload["sale_channel"] = sale_channel
        if discount:
            payload["discount"] = discount
        return await self._post("write-off-request", payload)

    # ──────────────────────────────────────────────
    # Коды подтверждения (OTP)
    # ──────────────────────────────────────────────

    async def send_otp(self, phone: str) -> dict[str, Any]:
        """
        POST /send-register-code
        Отправка OTP-кода подтверждения на телефон.
        """
        return await self._post("send-register-code", {"phone": self._normalize_phone(phone)})

    async def verify_otp(self, phone: str, code: str) -> dict[str, Any]:
        """
        POST /verify-confirmation-code
        Проверка кода подтверждения регистрации или списания бонусов.
        """
        return await self._post(
            "verify-confirmation-code",
            {"phone": self._normalize_phone(phone), "code": code},
        )

    async def send_write_off_otp(self, phone: str) -> dict[str, Any]:
        """
        POST /send-write-off-confirmation-code
        Отправка кода для подтверждения списания бонусов.
        """
        return await self._post(
            "send-write-off-confirmation-code",
            {"phone": self._normalize_phone(phone)},
        )

    # ──────────────────────────────────────────────
    # Push-уведомления
    # ──────────────────────────────────────────────

    async def send_push(
        self,
        phone: str,
        *,
        title: str = "",
        message: str = "",
        image: str = "",
    ) -> dict[str, Any]:
        """
        POST /send-push
        Отправка PUSH-уведомления покупателю в мобильное приложение PremiumBonus.
        """
        payload: dict[str, Any] = {"phone": self._normalize_phone(phone)}
        if title:
            payload["title"] = title
        if message:
            payload["message"] = message
        if image:
            payload["image"] = image
        return await self._post("send-push", payload)

    # ──────────────────────────────────────────────
    # Промокоды
    # ──────────────────────────────────────────────

    async def activate_promocode(self, phone: str, code: str) -> dict[str, Any]:
        """
        POST /promocode/activate-promocode
        Активация промокода для покупателя.
        """
        return await self._post(
            "promocode/activate-promocode",
            {"phone": self._normalize_phone(phone), "code": code},
        )

    # ──────────────────────────────────────────────
    # Карта
    # ──────────────────────────────────────────────

    async def activate_card(
        self,
        *,
        phone: str = "",
        card_number: str = "",
    ) -> dict[str, Any]:
        """
        POST /card-activate
        Привязка физической или виртуальной карты к покупателю.
        """
        payload: dict[str, Any] = {}
        if phone:
            payload["phone"] = self._normalize_phone(phone)
        if card_number:
            payload["card_number"] = card_number
        self._with_sale_point(payload)
        return await self._post("card-activate", payload)

    async def get_card_info(self, card_number: str) -> dict[str, Any]:
        """
        POST /card-get-info
        Информация о карте.
        """
        return await self._post("card-get-info", {"card_number": card_number})
