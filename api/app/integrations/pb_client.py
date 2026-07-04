from __future__ import annotations
import os
import re
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional, Dict

import httpx

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

    async def get_buyer_info(self, identificator: str, *, extra_fields: list[str] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"identificator": identificator}
        if self.sale_point_id:
            payload["sale_point_id"] = self.sale_point_id
        if extra_fields:
            payload["extra_fields"] = extra_fields
        return await self._post("buyer-info", payload)

    async def register_buyer(self, phone: str, **kwargs: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {"phone": self._normalize_phone(phone), **kwargs}
        return await self._retry("buyer-register", payload)

    async def edit_buyer(self, phone: str, **fields: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {"phone": self._normalize_phone(phone), **fields}
        return await self._retry("buyer-edit", payload)

    async def get_buyer_purchases(self, phone: str) -> dict[str, Any]:
        return await self._post("buyer/purchase-list", {"phone": self._normalize_phone(phone)})

    async def add_purchase(
        self,
        items: list[PurchaseItem],
        *,
        phone: str = "",
        identificator: str = "",
        external_purchase_id: str = "",
        write_off_bonus: float = 0.0,
        discount: float = 0.0,
        promocode: str = "",
        sale_channel: str = "",
        cashier_name: str = "",
        waiters_names: list[str] | None = None,
        purchase_status: str = "approved",
    ) -> dict[str, Any]:
        if not phone and not identificator:
            raise ValueError("Need phone or identificator")
        payload: dict[str, Any] = {"items": [i.to_dict() for i in items]}
        if phone:
            payload["phone"] = self._normalize_phone(phone)
        if identificator:
            payload["identificator"] = identificator
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


    async def get_buyer_info_detail(self, identificator: str) -> dict[str, Any]:
        payload: dict[str, Any] = {"identificator": identificator}
        if self.sale_point_id:
            payload["sale_point_id"] = self.sale_point_id
        return await self._post("buyer-info-detail", payload)

