from __future__ import annotations
import os
import logging
from datetime import datetime
from typing import Any

from app.integrations.pb_client import PremiumBonusClient

logger = logging.getLogger("pb_sync")

_DIET_GROUP_MAP: dict[str, str] = {
    "vegetarian": os.getenv("PB_GROUP_VEGETARIAN", ""),
    "vegan": os.getenv("PB_GROUP_VEGETARIAN", ""),
    "low-calorie": os.getenv("PB_GROUP_LOW_CAL", ""),
    "no-pork": os.getenv("PB_GROUP_NO_PORK", ""),
}


class TasteProfileSync:
    def __init__(self) -> None:
        self.pb = PremiumBonusClient()

    async def pull(self, phone: str) -> dict[str, Any]:
        buyer = await self.pb.get_buyer_info(phone, extra_fields=["payments_amount"])

        if not buyer.get("is_registered"):
            return {
                "pb_is_registered": False,
                "synced_at": datetime.utcnow().isoformat(),
            }

        detail = await self.pb.get_buyer_info_detail(phone)
        purchases = detail.get("purchases") or []
        last_purchase_at = detail.get("last_purchase_date") or ""

        return {
            "pb_is_registered": buyer.get("is_registered", False),
            "pb_blocked": buyer.get("blocked", False),
            "pb_balance": buyer.get("balance", 0),
            "pb_bonus_inactive": buyer.get("bonus_inactive", 0),
            "pb_balance_accumulated": buyer.get("balance_bonus_accumulated", 0),
            "pb_balance_present": buyer.get("balance_bonus_present", 0),
            "pb_card_number": buyer.get("card_number") or "",
            "pb_group_name": buyer.get("group_name", ""),
            "pb_client_id": str(buyer.get("client_id", "")),
            "pb_payments_amount": buyer.get("payments_amount", 0),
            "pb_purchase_count": len(purchases),
            "pb_last_purchase_at": last_purchase_at,
            "synced_at": datetime.utcnow().isoformat(),
        }
