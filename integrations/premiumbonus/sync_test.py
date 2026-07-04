"""
Ручное тестирование PremiumBonusClient.
Запуск: python sync_test.py

Требует .env файл рядом (или переменные окружения).
"""

import asyncio
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv не установлен — env vars должны быть уже в окружении

from client import PremiumBonusClient, PurchaseItem

TEST_PHONE = os.getenv("TEST_PHONE", "79001234567")


async def run_tests() -> None:
    client = PremiumBonusClient()
    print(f"Base URL : {client.base_url}")
    print(f"Token set: {'yes' if client.api_token else 'NO — set PREMIUMBONUS_API_TOKEN'}")
    print(f"Test phone: {TEST_PHONE}")
    print()

    # 1. Информация о покупателе
    print("=== buyer-info ===")
    info = await client.get_buyer_info(TEST_PHONE)
    _print(info)

    # 2. Баланс бонусов
    print("\n=== buyer-bonus ===")
    bonus = await client.get_buyer_bonus(TEST_PHONE)
    _print(bonus)

    # 3. История покупок
    print("\n=== buyer/purchase-list ===")
    purchases = await client.get_buyer_purchases(TEST_PHONE)
    _print(purchases)

    # 4. Эмуляция покупки
    print("\n=== purchase-dry-run ===")
    items = [
        PurchaseItem(name="Бургер классик", amount=590.0, quantity=1, external_item_id="sku-001"),
        PurchaseItem(name="Картофель фри", amount=220.0, quantity=2, external_item_id="sku-002"),
    ]
    dry = await client.purchase_dry_run(TEST_PHONE, items, sale_channel="mobile_app")
    _print(dry)

    # 5. Запрос доступной выгоды
    print("\n=== purchase-request ===")
    pr = await client.purchase_request(TEST_PHONE, items, sale_channel="mobile_app")
    _print(pr)

    # 6. Отправка OTP
    print("\n=== send-register-code ===")
    otp = await client.send_otp(TEST_PHONE)
    _print(otp)


def _print(data: dict) -> None:
    import json
    print(json.dumps(data, ensure_ascii=False, indent=2))


async def run_profile_sync_tests() -> None:
    from profile_sync import TasteProfileSync

    sync = TasteProfileSync()
    print("\n" + "=" * 50)
    print("=== TasteProfileSync ===")

    # Пример профиля из F2M БД (asyncpg row → dict)
    mock_profile: dict = {
        "user_id": 123456,
        "phone": TEST_PHONE,
        "fio": "Иванов Иван Иванович",
        "sex": "male",
        "age": "15.08.1990",                    # DD.MM.YYYY из QuestionnaireRequest
        "preferences": ["вегетарианство", "мало калорий"],  # TasteStep2
        "avoid": ["грибы", "лук", "острое"],     # TasteStep3
        "hate": ["морепродукты"],                # TasteStep1 (аллергии)
        "novelty": "mixed",                      # TasteStep4
    }

    print("\n--- push (F2M → PB) ---")
    push_result = await sync.push(mock_profile)
    _print(push_result)

    print("\n--- pull (PB → F2M) ---")
    loyalty = await sync.pull(TEST_PHONE)
    _print(loyalty)

    print("\n--- push_and_pull (онбординг) ---")
    combined = await sync.push_and_pull(mock_profile)
    _print(combined)


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode == "profile":
        asyncio.run(run_profile_sync_tests())
    elif mode == "client":
        asyncio.run(run_tests())
    else:
        asyncio.run(run_tests())
        asyncio.run(run_profile_sync_tests())
