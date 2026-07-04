from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Dict, Any, List, Optional
import json
import base64

from backend.schemas.waiter import (
    WaiterLogin, WaiterRegister, WaiterLoginResponse,
    QRScanRequest, ClientResponse,
    DishModifyRequest, DishRemoveRequest,
    PrintBillRequest, OrderSendRequest,
    CreateTableSessionRequest, SendSessionRequest
)

# Using existing Database logic to not break the system
from iiko_f.iiko_order import (
    send_order_to_iiko, get_iiko_token, get_organization_id,
    get_terminal_group_id, print_iiko_bill, get_all_tables,
    get_table_id, get_active_order_for_table, resolve_basket_to_iiko_items,
    create_iiko_order, add_items_to_iiko_order, get_iiko_stop_list
)

import time
import os
import uuid as _uuid
import asyncio
import httpx

router = APIRouter()

_F2M_ENGINE_URL = os.getenv("F2M_ENGINE_URL", "").rstrip("/")

_background_tasks: set = set()

def _schedule_event(coro) -> None:
    """Keep a strong reference to async task so GC cannot collect it before it runs."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

async def _fire_event(event_type: str, user_id: int, dish_id: str):
    """Fire-and-forget event to f2m-engine. Never blocks or raises."""
    if not _F2M_ENGINE_URL:
        return
    try:
        payload = {
            "source_system": "waiter",
            "event_uuid": str(_uuid.uuid4()),
            "user_id": user_id,
            "event_type": event_type,
            "object_type": "dish",
            "object_id": str(dish_id),
            "payload_json": {},
        }
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(f"{_F2M_ENGINE_URL}/events/ingest", json=payload)
    except Exception:
        pass  # never break waiter flow


async def _sync_stop_list_to_engine(dish_ids: list[int]) -> None:
    """Push POS stop-list dish ids to f2m-engine settings without breaking waiter flow."""
    if not _F2M_ENGINE_URL:
        return
    try:
        payload = {"stop_list_dish_ids": [str(dish_id) for dish_id in dish_ids]}
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.patch(f"{_F2M_ENGINE_URL}/config/settings", json=payload)
    except Exception:
        pass

# In-memory cache for stop-lists (restaurant -> {data, timestamp})
_stop_list_cache: Dict[str, Dict[str, Any]] = {}
STOP_LIST_TTL = 60  # seconds

# Restaurant passwords loaded from env RESTAURANT_PASSWORDS_JSON={"IQ":"...",...}
import json as _json_pwd
RESTAURANT_PASSWORDS: Dict[str, str] = _json_pwd.loads(
    os.getenv("RESTAURANT_PASSWORDS_JSON", "{}")
)

_db_instance = None

def get_db():
    if _db_instance is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    return _db_instance

@router.post("/login", response_model=WaiterLoginResponse)
async def login(data: WaiterLogin, db = Depends(get_db)):
    """Login by 5-digit PIN (new) or by telegram ID (legacy fallback)."""
    pin = data.pin_code.strip()

    # 1. Try PIN-based login
    result = db.cursor.execute("SELECT waiter_id FROM waiters WHERE pin_code = ?", (pin,)).fetchone()
    if result:
        return WaiterLoginResponse(success=True, waiter_token=str(result[0]), message="Успешный вход")

    raise HTTPException(status_code=401, detail="Неверный PIN-код")

@router.post("/register", response_model=WaiterLoginResponse)
async def register(data: WaiterRegister, db = Depends(get_db)):
    """Register a new waiter: restaurant password → name → 5-digit PIN."""
    # 1. Validate restaurant password
    restaurant = None
    for rest_name, pwd in RESTAURANT_PASSWORDS.items():
        if data.restaurant_password == pwd:
            restaurant = rest_name
            break
    if not restaurant:
        raise HTTPException(status_code=400, detail="Неверный пароль ресторана")

    # 2. Validate PIN format
    pin = data.pin_code.strip()
    if len(pin) != 5 or not (pin.isdigit() and pin.isascii()):
        raise HTTPException(status_code=400, detail="PIN должен быть 5-значным числом")

    # 3. Check PIN uniqueness
    existing = db.cursor.execute("SELECT waiter_id FROM waiters WHERE pin_code = ?", (pin,)).fetchone()
    if existing:
        raise HTTPException(status_code=400, detail="Этот PIN уже занят, выберите другой")

    # 4. Generate unique waiter_id
    import random
    waiter_id = random.randint(100000, 999999)
    while db.check_waiter_exists(waiter_id):
        waiter_id = random.randint(100000, 999999)

    # 5. Create waiter
    name = data.name.strip() or "Официант"
    db.add_waiter(waiter_id, "", user_first_name=name, user_last_name="", user_surname="", restaurant=restaurant)
    db.cursor.execute("UPDATE waiters SET pin_code = ? WHERE waiter_id = ?", (pin, waiter_id))
    db.connection.commit()

    return WaiterLoginResponse(success=True, waiter_token=str(waiter_id), message="Регистрация успешна")

import re

def _extract_client_id(payload: str) -> Optional[int]:
    """
    Extracts client_id from various QR/deep-link formats:
    1. Plain: "or144"
    2. Full URL: "https://t.me/Bot?start=b3IxNDQ="  (base64 of "or144")
    3. Full URL with raw: "https://t.me/Bot?start=or144"
    4. Just base64: "b3IxNDQ="
    """
    # Step 1: If it's a Telegram deep-link URL, extract the ?start= parameter
    start_match = re.search(r"[?&]start=([A-Za-z0-9_=+/-]+)", payload)
    candidates = [payload]
    if start_match:
        candidates = [start_match.group(1)]  # focus on the start= value
    
    for candidate in candidates:
        # Try plain "or" + digits first
        or_match = re.search(r"or(\d+)", candidate)
        if or_match:
            return int(or_match.group(1))
        
        # Try base64 decoding (Telegram deep-link encodes payload in base64)
        try:
            # Pad the base64 string if needed
            padded = candidate + "=" * (-len(candidate) % 4)
            decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
            or_match = re.search(r"or(\d+)", decoded)
            if or_match:
                return int(or_match.group(1))
        except Exception:
            pass
    
    return None

@router.post("/scan-qr", response_model=ClientResponse)
async def scan_qr(data: QRScanRequest, waiter_token: str = Header(None, alias="waiter-token"), db = Depends(get_db)):
    """Extract client ID from QR code payload and link it to a table if specified."""
    payload = data.qr_payload.strip()
    if not waiter_token or not (waiter_token.isdigit() and waiter_token.isascii()):
        raise HTTPException(status_code=401, detail="waiter-token обязателен")
    waiter_id = int(waiter_token)
    
    client_id = _extract_client_id(payload)
    if client_id is not None:
        if not db.check_basket_exists(client_id):
            db.create_basket(client_id)
            
        # If table_number is provided, try to link guest to it immediately
        if data.table_number:
            existing_table = db.execute(
                "SELECT id FROM waiter_active_tables WHERE waiter_id = %s AND table_number = %s AND status = 'open'",
                (waiter_id, data.table_number)
            ).fetchone()
            
            if existing_table:
                db.add_guest_to_table(existing_table[0], client_id)
                return ClientResponse(success=True, client_id=client_id, message=f"Гость {client_id} добавлен к столу {data.table_number}")

        return ClientResponse(success=True, client_id=client_id, message="Клиент найден")
    
    raise HTTPException(status_code=400, detail="Неверный формат QR-кода. Ожидается or123 или Telegram deep-link.")

@router.get("/menu")
async def get_waiter_menu(waiter_token: str = Header(None, alias="waiter-token"), db = Depends(get_db)):
    """Return menu items grouped by categories, filtered by waiter's restaurant"""
    if not waiter_token or not (waiter_token.isdigit() and waiter_token.isascii()):
        raise HTTPException(status_code=401, detail="waiter-token обязателен")
    waiter_id = int(waiter_token)
    restaurant = db.get_waiter_restaurant(waiter_id)

    all_menu = db.menu_get()

    # Filter by restaurant if known (index 3 = Restaurant)
    if restaurant:
        all_menu = [dish for dish in all_menu if dish[3] and dish[3].strip().lower() == restaurant.strip().lower()]

    # Group by category
    cat_order = []
    cat_map = {}
    for dish in all_menu:
        cat = dish[1] or "Без категории"
        if cat not in cat_map:
            cat_order.append(cat)
            cat_map[cat] = []
        cat_map[cat].append({
            "id": dish[0],
            "category": cat,
            "name": dish[2],
            "description": dish[4] if len(dish) > 4 else "",
            "price": dish[8] if len(dish) > 8 and dish[8] else 0,
            "image": dish[6] if len(dish) > 6 else None
        })

    result = [{"category_name": cat, "dishes": cat_map[cat]} for cat in cat_order if cat_map[cat]]

    return {"menu": result}

@router.get("/basket/{client_id}")
async def get_client_basket(client_id: int, db = Depends(get_db)):
    """Fetches the basket details and calculates cost"""
    if not db.check_basket_exists(client_id):
         return {"basket": [], "total_cost": 0, "mood": "Не указано", "remark": ""}
         
    basket = db.get_basket(client_id)
    if not isinstance(basket, dict):
        basket = {}
        
    all_menu = db.menu_get()
    
    items = []
    total_cost = 0
    for dish_name, dish_data in basket.items():
        if not dish_data: continue
        dish_id = dish_data[0]
        quantity = dish_data[1]
        
        # find price
        dish_price = 0
        for menu_dish in all_menu:
            if menu_dish[0] == dish_id:
                dish_price = menu_dish[8] if len(menu_dish) > 8 and menu_dish[8] else 0
                break
                
        if dish_price:
            total_cost += int(dish_price) * quantity
            
        # Extract modifiers if present (index 3 in basket array)
        item_modifiers = dish_data[3] if len(dish_data) > 3 and isinstance(dish_data[3], list) else []
        # Extract comment if present (index 4 in basket array)
        item_comment = dish_data[4] if len(dish_data) > 4 and isinstance(dish_data[4], str) else ""

        items.append({
            "dish_id": dish_id,
            "dish_name": dish_name,
            "quantity": quantity,
            "price": dish_price,
            "subtotal": int(dish_price) * quantity,
            "modifiers": item_modifiers,
            "comment": item_comment
        })
        
    mood = db.get_temp_users_mood(client_id) or "Не указано"
        
    return {
        "basket": items,
        "total_cost": total_cost,
        "mood": mood,
        "remark": "" # Remakrs would be tied to waiter theoretically
    }

@router.post("/basket/{client_id}/modify")
async def modify_basket(client_id: int, data: DishModifyRequest, db = Depends(get_db)):
    basket = db.get_basket(client_id)
    if not isinstance(basket, dict):
        basket = {}

    # Check BEFORE modifying: fire add_to_cart only on first add
    dish_was_not_in_basket = not any(d and d[0] == data.dish_id for d in basket.values())

    dish_name_found = None
    for dish_name, dish_data in basket.items():
        if dish_data and dish_data[0] == data.dish_id:
            dish_name_found = dish_name
            break
            
    if dish_name_found:
        new_qty = basket[dish_name_found][1] + data.delta
        if new_qty <= 0:
            basket.pop(dish_name_found, None)
        else:
            basket[dish_name_found][1] = new_qty
            # Update modifiers if provided
            if data.modifiers is not None:
                while len(basket[dish_name_found]) < 4:
                    basket[dish_name_found].append([])
                basket[dish_name_found][3] = [m.model_dump() for m in data.modifiers]
            # Update comment if provided
            if data.comment is not None:
                while len(basket[dish_name_found]) < 5:
                    basket[dish_name_found].append([] if len(basket[dish_name_found]) < 4 else "")
                basket[dish_name_found][4] = data.comment
    elif data.delta > 0:
        # Add a new dish
        all_menu = db.menu_get()
        dish_info = next((d for d in all_menu if d[0] == data.dish_id), None)
        if dish_info:
            mods = [m.model_dump() for m in data.modifiers] if data.modifiers else []
            comment = data.comment or ""
            basket[dish_info[2]] = [data.dish_id, data.delta, [None]*data.delta, mods, comment]

    db.set_basket(client_id, basket)

    if data.delta > 0 and dish_was_not_in_basket:
        _schedule_event(_fire_event("add_to_cart", client_id, str(data.dish_id)))

    return {"success": True, "message": "Корзина обновлена"}

@router.post("/basket/{client_id}/remove")
async def remove_dish(client_id: int, data: DishRemoveRequest, db = Depends(get_db)):
    basket = db.get_basket(client_id)
    if not isinstance(basket, dict):
        return {"success": True}
        
    dish_name_to_remove = None
    for dish_name, dish_data in basket.items():
        if dish_data and dish_data[0] == data.dish_id:
            dish_name_to_remove = dish_name
            break
            
    if dish_name_to_remove:
        basket.pop(dish_name_to_remove, None)
        db.set_basket(client_id, basket)
        
    return {"success": True, "message": "Блюдо удалено"}

@router.post("/order/send-table")
async def send_table_order(data: PrintBillRequest, waiter_token: str = Header(None, alias="waiter-token"), db = Depends(get_db)):
    """Send consolidated order for all guests at the table."""
    if not waiter_token or not (waiter_token.isdigit() and waiter_token.isascii()):
        raise HTTPException(status_code=401, detail="waiter-token обязателен")
    waiter_id = int(waiter_token)
    
    # 1. Find active table
    existing_table = db.execute(
        "SELECT id FROM waiter_active_tables WHERE waiter_id = %s AND table_number = %s AND status = 'open'",
        (waiter_id, data.table_number)
    ).fetchone()
    
    if not existing_table:
        raise HTTPException(status_code=404, detail="Активный стол не найден")
        
    table_id = existing_table[0]
    
    # 2. Get all guests and their baskets
    guests = db.get_table_guests(table_id)
    if not guests:
        raise HTTPException(status_code=400, detail="У стола нет гостей")
        
    combined_basket = {}
    total_guests_count = len(guests)
    
    for g in guests:
        # g: (id, client_id, basket_snapshot, name, created_at)
        client_id = g[1]
        g_basket = db.get_basket(client_id)
        if g_basket:
            # Merge baskets (handle duplicate keys by adding prefixes or combining)
            # For simplicity, if same dish added by different guests, we combine them for iiko
            # but in the future we might want separate lines.
            for dish_name, dish_data in g_basket.items():
                if dish_name in combined_basket:
                    combined_basket[dish_name][1] += dish_data[1] # Sum quantity
                else:
                    combined_basket[dish_name] = dish_data
                    
    if not combined_basket:
        raise HTTPException(status_code=400, detail="Корзины всех гостей пусты")
        
    # 3. Send to iiko
    success = await send_order_to_iiko(combined_basket, waiter_id, data.table_number, db, guests_count=total_guests_count)
    if not success:
         raise HTTPException(status_code=500, detail="Ошибка при отправке заказа в iiko")

    return {"success": True, "message": f"Заказ для стола {data.table_number} отправлен (гостей: {total_guests_count})"}

@router.post("/order/{client_id}/send")
async def send_order(client_id: int, data: PrintBillRequest, waiter_token: str = Header(None, alias="waiter-token"), db = Depends(get_db)):
    basket = db.get_basket(client_id)
    if not isinstance(basket, dict) or not basket:
        raise HTTPException(status_code=400, detail="Корзина пуста")
        
    if not waiter_token or not (waiter_token.isdigit() and waiter_token.isascii()):
        raise HTTPException(status_code=401, detail="waiter-token обязателен")
    waiter_id = int(waiter_token)
    
    success = await send_order_to_iiko(basket, waiter_id, data.table_number, db)
    if not success:
         raise HTTPException(status_code=500, detail="Ошибка при отправке заказа в iiko")

    # Save active table for dashboard
    try:
        # Calculate total for snapshot
        all_menu = db.menu_get()
        total = 0
        for dish_name, dish_data in basket.items():
            if not dish_data: continue
            dish_id = dish_data[0]
            quantity = dish_data[1]
            for m in all_menu:
                if m[0] == dish_id:
                    price = int(m[8]) if len(m) > 8 and m[8] else 0
                    total += price * quantity
                    break
        db.create_active_table(waiter_id, client_id, data.table_number, json.dumps(basket, ensure_ascii=False), total)
    except Exception as e:
        print(f"[WAITER] Warning: could not save active table: {e}")

    # Feedback loop: fire purchase_paid for each dish in basket
    for dish_name, dish_data in basket.items():
        if dish_data and len(dish_data) >= 1:
            dish_id = dish_data[0]
            qty = dish_data[1] if len(dish_data) > 1 else 1
            for _ in range(max(1, int(qty))):
                _schedule_event(_fire_event("purchase_paid", client_id, str(dish_id)))

    return {"success": True, "message": "Заказ отправлен"}

@router.post("/order/{client_id}/print-bill")
async def print_bill(client_id: int, data: PrintBillRequest, waiter_token: str = Header(None, alias="waiter-token"), db = Depends(get_db)):
    if not waiter_token or not (waiter_token.isdigit() and waiter_token.isascii()):
        raise HTTPException(status_code=401, detail="waiter-token обязателен")
    waiter_id = int(waiter_token)
    restaurant = db.get_waiter_restaurant(waiter_id)
    if not restaurant:
        raise HTTPException(status_code=400, detail="Ресторан не найден")
        
    iiko_key = db.get_iiko_key(restaurant)
    if not iiko_key:
        raise HTTPException(status_code=400, detail="iiko API ключ не настроен")
        
    token = get_iiko_token(iiko_key)
    org_id = get_organization_id(token) if token else None
    terminal_id = get_terminal_group_id(token, org_id) if token and org_id else None
    
    if token and org_id and terminal_id:
        success = print_iiko_bill(token, org_id, terminal_id, table_number=data.table_number)
        if success:
            # Close the active table
            try:
                db.close_active_table_by_number(waiter_id, data.table_number)
            except Exception as e:
                print(f"[WAITER] Warning: could not close active table: {e}")
            return {"success": True, "message": f"Пречек отправлен на стол {data.table_number}"}
            
    raise HTTPException(status_code=500, detail="Ошибка при печати пречека в iiko")

# ====== ACTIVE TABLES ======

@router.get("/active-tables")
async def get_active_tables(waiter_token: str = Header(None, alias="waiter-token"), db = Depends(get_db)):
    """Return list of open tables for the waiter with their guests."""
    if not waiter_token or not (waiter_token.isdigit() and waiter_token.isascii()):
        raise HTTPException(status_code=401, detail="waiter-token обязателен")
    waiter_id = int(waiter_token)
    rows = db.get_active_tables(waiter_id)
    
    tables = []
    for row in rows:
        # row: (id, waiter_id, client_id, table_number, basket_snapshot, total_price, created_at)
        table_id = row[0]
        guests_rows = db.get_table_guests(table_id)
        
        guests = []
        total_dish_count = 0
        all_dish_names = []
        
        for idx, g in enumerate(guests_rows):
            # g: (id, client_id, basket_snapshot, name, created_at)
            client_id = g[1]
            # Read live basket instead of stale snapshot
            g_basket = db.get_basket(client_id)
            if not isinstance(g_basket, dict):
                g_basket = {}

            g_dish_count = sum(d[1] if isinstance(d, list) and len(d) > 1 else 1 for d in g_basket.values())
            total_dish_count += g_dish_count
            all_dish_names.extend(list(g_basket.keys()))

            guests.append({
                "client_id": g[1],
                "name": g[3] or f"Гость {idx + 1}",
                "dish_count": g_dish_count
            })

        tables.append({
            "id": table_id,
            "table_number": row[3],
            "total_price": row[5] or 0,
            "dish_count": total_dish_count,
            "dish_names": all_dish_names[:5],
            "created_at": str(row[6]) if row[6] else "",
            "guests": guests
        })
    
    return {"tables": tables}

@router.get("/table/{table_id}/guests")
async def get_table_guests_endpoint(table_id: int, waiter_token: str = Header(None, alias="waiter-token"), db = Depends(get_db)):
    """Return all guests for a table with their basket contents."""
    guests_rows = db.get_table_guests(table_id)
    all_menu = db.menu_get()

    guests = []
    for idx, g in enumerate(guests_rows):
        client_id = g[1]
        basket = db.get_basket(client_id)
        if not isinstance(basket, dict):
            basket = {}

        items = []
        guest_total = 0
        for dish_name, dish_data in basket.items():
            if not dish_data and dish_data != 0:
                continue
            if isinstance(dish_data, (int, float)):
                quantity = int(dish_data)
                dish_id = None
                item_mods = []
                item_comment = ""
            else:
                dish_id = dish_data[0]
                quantity = dish_data[1]
                item_mods = dish_data[3] if len(dish_data) > 3 and isinstance(dish_data[3], list) else []
                item_comment = dish_data[4] if len(dish_data) > 4 and isinstance(dish_data[4], str) else ""
            dish_price = 0
            resolved_id = dish_id
            for menu_dish in all_menu:
                if (dish_id and menu_dish[0] == dish_id) or (not dish_id and menu_dish[2] and menu_dish[2].strip().lower() == dish_name.strip().lower()):
                    dish_price = menu_dish[8] if len(menu_dish) > 8 and menu_dish[8] else 0
                    resolved_id = menu_dish[0]
                    break
            if dish_price:
                guest_total += int(dish_price) * quantity
            items.append({
                "dish_id": resolved_id,
                "dish_name": dish_name,
                "quantity": quantity,
                "price": dish_price,
                "subtotal": int(dish_price) * quantity,
                "modifiers": item_mods,
                "comment": item_comment
            })

        mood = db.get_temp_users_mood(client_id) or "Не указано"
        guests.append({
            "client_id": client_id,
            "name": g[3] or f"Гость {idx + 1}",
            "mood": mood,
            "basket": items,
            "total_cost": guest_total
        })

    return {"guests": guests}

@router.post("/table/{table_id}/close")
async def close_table(table_id: int, waiter_token: str = Header(None, alias="waiter-token"), db = Depends(get_db)):
    """Manually close a table"""
    db.close_active_table(table_id)
    return {"success": True, "message": "Стол закрыт"}

@router.post("/table/{table_id}/add-guest")
async def add_guest_to_table_endpoint(table_id: int, waiter_token: str = Header(None, alias="waiter-token"), db = Depends(get_db)):
    """Add a new guest slot to an existing table."""
    existing_guests = db.get_table_guests(table_id)
    new_idx = len(existing_guests)
    
    # Generate unique guest number based on max existing + 1
    max_number = 0
    for g in existing_guests:
        num = g[5] or 0 # guest_number is at index 5
        if num > max_number:
            max_number = num
    
    new_number = max_number + 1
    new_name = f"Гость {new_number}"
    
    # Generate a truly unique client_id
    import time
    # Using millisecond timestamp + random or counter for client_id
    temp_client_id = -(int(time.time() * 1000) % 1000000000)
    
    if not db.check_basket_exists(temp_client_id):
        db.create_basket(temp_client_id)
    db.add_guest_to_table(table_id, temp_client_id, name=new_name, guest_number=new_number)
    db.connection.commit()
    
    return {
        "success": True,
        "guest": {
            "client_id": temp_client_id,
            "name": new_name,
            "guest_number": new_number,
            "slot_index": len(existing_guests)
        }
    }

@router.post("/table/{table_id}/remove-guest")
async def remove_guest_from_table(table_id: int, data: dict, waiter_token: str = Header(None, alias="waiter-token"), db = Depends(get_db)):
    """Remove a guest from an active table."""
    client_id = data.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id required")
    db.cursor.execute("DELETE FROM waiter_active_table_guests WHERE active_table_id = ? AND client_id = ?", (table_id, client_id))
    db.connection.commit()
    # Clear basket
    try:
        db.set_basket(client_id, {})
    except Exception:
        pass
    remaining = db.get_table_guests(table_id)
    db.cursor.execute("UPDATE waiter_active_tables SET guests_count = ? WHERE id = ?", (len(remaining), table_id))
    db.connection.commit()

    guests = []
    for idx, g in enumerate(remaining):
        name = g[3]
        guest_number = g[5]
        if not name:
            name = f"Гость {guest_number or (idx + 1)}"
        guests.append({
            "client_id": g[1],
            "name": name,
            "slot_index": idx,
            "guest_number": guest_number
        })

    return {"success": True, "message": "Гость удалён", "remaining": guests}

# ====== DISH DETAILS & RECOMMENDATIONS ======

@router.get("/menu/{dish_id}")
async def get_dish_detail(dish_id: int, db = Depends(get_db)):
    """Return full details for a single dish"""
    all_menu = db.menu_get()
    dish_info = next((d for d in all_menu if d[0] == dish_id), None)
    if not dish_info:
        raise HTTPException(status_code=404, detail="Блюдо не найдено")
    return {
        "id": dish_info[0],
        "category": dish_info[1],
        "name": dish_info[2],
        "description": dish_info[3] if len(dish_info) > 3 else "",
        "weight": dish_info[4] if len(dish_info) > 4 else "",
        "ingredients": dish_info[5] if len(dish_info) > 5 else "",
        "image": dish_info[6] if len(dish_info) > 6 else None,
        "price": dish_info[8] if len(dish_info) > 8 and dish_info[8] else 0,
    }

@router.get("/menu/{dish_id}/modifiers")
async def get_dish_modifiers(dish_id: int, db = Depends(get_db)):
    """Return modifiers available for a dish, grouped by modifier group."""
    flat = db.get_dish_modifiers(dish_id)
    # Group flat modifier list into [{group_id, group_name, required, min_selected, max_selected, options:[...]}]
    groups_map: dict = {}
    for m in flat:
        gid = m.get("group_id") or "default"
        if gid not in groups_map:
            groups_map[gid] = {
                "group_id": gid,
                "group_name": m.get("group_name", ""),
                "required": (m.get("min_quantity", 0) or 0) > 0,
                "min_selected": m.get("min_quantity", 0) or 0,
                "max_selected": m.get("max_quantity", 1) or 1,
                "options": []
            }
        groups_map[gid]["options"].append({
            "id": m.get("modifier_id", ""),
            "name": m.get("name", ""),
            "min_amount": m.get("min_quantity", 0) or 0,
            "max_amount": m.get("max_quantity", 1) or 1,
            "default_amount": m.get("default_quantity", 0) or 0,
            "price": m.get("price", 0) or 0,
        })
    return {"dish_id": dish_id, "modifiers": list(groups_map.values())}

@router.get("/stop-list")
async def get_stop_list(waiter_token: str = Header(None, alias="waiter-token"), db = Depends(get_db)):
    """Return list of stopped dish IDs from iiko, cached for 60s."""
    if not waiter_token or not (waiter_token.isdigit() and waiter_token.isascii()):
        raise HTTPException(status_code=401, detail="waiter-token обязателен")
    waiter_id = int(waiter_token)
    restaurant = db.get_waiter_restaurant(waiter_id)
    if not restaurant:
        return {"stopped_dish_ids": []}

    now = time.time()
    cached = _stop_list_cache.get(restaurant)
    if cached and (now - cached["timestamp"]) < STOP_LIST_TTL:
        return {"stopped_dish_ids": cached["data"]}

    try:
        iiko_key = db.get_iiko_key(restaurant)
        if not iiko_key:
            return {"stopped_dish_ids": []}
        token = get_iiko_token(iiko_key)
        if not token:
            return {"stopped_dish_ids": []}
        org_id = get_organization_id(token)
        if not org_id:
            return {"stopped_dish_ids": []}

        # Get iiko product UUIDs that are stopped
        stopped_product_ids = get_iiko_stop_list(token, org_id)
        if not stopped_product_ids:
            _stop_list_cache[restaurant] = {"data": [], "timestamp": now}
            _schedule_event(_sync_stop_list_to_engine([]))
            return {"stopped_dish_ids": []}

        # Match iiko product UUIDs to our Dish_id via iiko_id column (index 10)
        all_menu = db.menu_get()
        stopped_set = set(stopped_product_ids)
        dish_ids = [dish[0] for dish in all_menu if dish[10] and str(dish[10]) in stopped_set]

        _stop_list_cache[restaurant] = {"data": dish_ids, "timestamp": now}
        _schedule_event(_sync_stop_list_to_engine(dish_ids))
        return {"stopped_dish_ids": dish_ids}
    except Exception as e:
        print(f"❌ [STOP-LIST] Error fetching from iiko: {e}")
        return {"stopped_dish_ids": []}

@router.get("/recommendations/{client_id}")
async def get_recommendations(
    client_id: int,
    hunger: Optional[str] = None,
    allergies: Optional[str] = None,
    waiter_token: str = Header(None, alias="waiter-token"),
    db = Depends(get_db),
):
    """
    Recommendation engine — 3-tier priority:
    1. ЦВП (user_temp_sort): pre-ranked menu from taste profile — if exists
    2. Profile-based scoring: prefer/hate/mood signals from profile table
    3. New guest fallback: most popular dishes ordered today (CRM layer)
    Always excludes categories already in basket and dishes ordered in past 3 visits (CRM repeat penalty).
    """
    import psycopg2, os
    from datetime import datetime, timedelta
    from collections import Counter

    basket = db.get_basket(client_id)
    all_menu = db.menu_get()

    waiter_id = int(waiter_token) if waiter_token and waiter_token.isdigit() else None
    restaurant = db.get_waiter_restaurant(waiter_id) if waiter_id else None
    if restaurant:
        all_menu = [dish for dish in all_menu if dish[3] and dish[3].strip().lower() == restaurant.strip().lower()]

    basket_dish_names = {d.strip().lower() for d in basket.keys()} if isinstance(basket, dict) else set()
    basket_categories = set()
    for m in all_menu:
        if m[2] and m[2].strip().lower() in basket_dish_names and m[1]:
            basket_categories.add(m[1])

    # --- CRM layer: recent orders for repeat penalty ---
    try:
        pg_conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "db"),
            port=os.environ.get("POSTGRES_PORT", 5432),
            dbname=os.environ.get("POSTGRES_DB", "food2mood"),
            user=os.environ.get("POSTGRES_USER", "postgres"),
            password=os.environ.get("POSTGRES_PASSWORD", ""),
        )
        cur = pg_conn.cursor()

        # Dishes ordered in last 3 visits — penalise repeats
        cur.execute(
            "SELECT basket FROM orders_history WHERE user_id=%s ORDER BY created_at DESC LIMIT 3",
            (client_id,)
        )
        recent_baskets = [r[0] for r in cur.fetchall() if r[0]]
        recent_dishes: set = set()
        for b in recent_baskets:
            try:
                parsed = json.loads(b) if isinstance(b, str) else b
                if isinstance(parsed, dict):
                    recent_dishes.update(k.strip().lower() for k in parsed.keys())
            except Exception:
                pass

        # Popular dishes ordered today (for new guest fallback)
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cur.execute(
            "SELECT basket FROM orders_history WHERE created_at >= %s",
            (today_start,)
        )
        dish_counter: Counter = Counter()
        for (b,) in cur.fetchall():
            try:
                parsed = json.loads(b) if isinstance(b, str) else b
                if isinstance(parsed, dict):
                    for dish_name, qty in parsed.items():
                        dish_counter[dish_name.strip().lower()] += (qty if isinstance(qty, int) else 1)
            except Exception:
                pass

        # ЦВП profile: prefer/hate/user_temp_sort
        cur.execute(
            "SELECT prefer, hate, mood, user_temp_sort FROM profile WHERE user_id=%s",
            (client_id,)
        )
        profile_row = cur.fetchone()

        pg_conn.close()
    except Exception as e:
        print(f"[WAITER REC] CRM layer error: {e}")
        recent_dishes = set()
        dish_counter = Counter()
        profile_row = None

    # Parse allergy list from query param
    allergen_list = [a.strip().lower() for a in (allergies or "").split(",") if a.strip()]

    # Hearty keywords for высокий hunger boost
    _HEARTY_KW = ["говяд", "стейк", "рибай", "баран", "свинин", "утк", "бургер", "котлет", "шашлык"]

    def _build_result(ranked_dishes, limit=6):
        """Build recommendation list from scored dishes, skipping basket/repeat items."""
        seen_cats = set()
        result = []
        for m, score in ranked_dishes:
            cat = m[1] or ""
            name = m[2] or ""
            desc = (m[4] or "").lower()
            if not name or not cat:
                continue
            if cat in basket_categories:
                continue
            if name.strip().lower() in basket_dish_names:
                continue
            if cat in seen_cats:
                continue
            # Hunger filter: low appetite — skip Горячее
            if hunger == "низкий" and "горяч" in cat.lower():
                continue
            # Allergy filter: skip dish if allergen found in name or description
            if allergen_list:
                name_l = name.lower()
                if any(a in name_l or a in desc for a in allergen_list):
                    continue
            seen_cats.add(cat)
            # Add contextual tags
            tags: list = []
            if hunger == "высокий" and any(kw in name.lower() or kw in desc for kw in _HEARTY_KW):
                tags = ["высокий аппетит"]
            result.append({
                "id": m[0],
                "name": name,
                "price": m[8] if m[8] else 0,
                "image": None,
                "category": cat,
                "tags": tags,
            })
            if len(result) >= limit:
                break
        return result

    try:
        # === TIER 1: ЦВП — pre-ranked menu from taste profile ===
        user_temp_sort = db.get_user_temp_sort(client_id)
        if user_temp_sort:
            try:
                ranked_menu = json.loads(user_temp_sort)
                categories = ranked_menu.get("categories", [])
                if categories:
                    basket_cat_ids = set()
                    for cat in categories:
                        for dish in cat.get("dishes", []):
                            if dish.get("dish_name", "").strip().lower() in basket_dish_names:
                                basket_cat_ids.add(cat.get("category_iiko_id", ""))
                    recommended = []
                    seen_cats = set()
                    for cat in categories:
                        if cat.get("category_iiko_id", "") in basket_cat_ids:
                            continue
                        cat_name = cat.get("category_name", "")
                        if cat_name in seen_cats:
                            continue
                        for dish in cat.get("dishes", []):
                            d_name = dish.get("dish_name", "").strip()
                            if d_name.lower() in basket_dish_names:
                                continue
                            menu_match = next(
                                (m for m in all_menu if m[2] and m[2].strip().lower() == d_name.lower()),
                                None
                            )
                            if menu_match:
                                seen_cats.add(cat_name)
                                recommended.append({
                                    "id": menu_match[0],
                                    "name": d_name,
                                    "price": menu_match[8] if len(menu_match) > 8 and menu_match[8] else 0,
                                    "image": None,
                                    "category": cat_name,
                                })
                                break
                        if len(recommended) >= 6:
                            break
                    if recommended:
                        return {"recommendations": recommended, "source": "cvp"}
            except Exception:
                pass

        # === TIER 2: Profile-based scoring (prefer/hate/mood) ===
        if profile_row:
            prefer_raw = profile_row[0] or ""
            hate_raw   = profile_row[1] or ""
            prefer_tags = {t.strip().lower() for t in prefer_raw.split(",") if t.strip() and t.strip() not in ("", "пусто")}
            hate_tags   = {t.strip().lower() for t in hate_raw.split(",")   if t.strip() and t.strip() not in ("", "пусто")}
        if profile_row:
            if prefer_tags or hate_tags:
                scored = []
                for m in all_menu:
                    ingredients = (m[4] or "").lower()
                    name_lower = (m[2] or "").lower()
                    score = 0.0
                    for tag in prefer_tags:
                        if tag in ingredients or tag in name_lower:
                            score += 1.0
                    for tag in hate_tags:
                        if tag in ingredients or tag in name_lower:
                            score -= 3.0
                    if m[2] and m[2].strip().lower() in recent_dishes:
                        score -= 0.5
                    # Hunger boost: high appetite → prefer hearty/meat dishes
                    if hunger == "высокий":
                        for kw in _HEARTY_KW:
                            if kw in name_lower or kw in ingredients:
                                score += 0.5
                                break
                    scored.append((m, score))
                scored.sort(key=lambda x: x[1], reverse=True)
                recommended = _build_result(scored)
                if recommended:
                    return {"recommendations": recommended, "source": "profile"}

        # === TIER 3: New guest — most popular today (CRM fallback) ===
        if dish_counter:
            menu_by_name = {m[2].strip().lower(): m for m in all_menu if m[2]}
            popular_scored = []
            for dish_name, count in dish_counter.most_common():
                m = menu_by_name.get(dish_name)
                if m:
                    repeat_penalty = -0.3 if dish_name in recent_dishes else 0.0
                    popular_scored.append((m, count + repeat_penalty))
            popular_scored.sort(key=lambda x: x[1], reverse=True)
            recommended = _build_result(popular_scored)
            if recommended:
                return {"recommendations": recommended, "source": "popular_today"}

        # Last resort: 1 dish per unrepresented category
        scored_plain = [(m, 0.0) for m in all_menu]
        return {"recommendations": _build_result(scored_plain), "source": "category_fallback"}

    except Exception as e:
        print(f"[WAITER REC] Error: {e}")
        import traceback; traceback.print_exc()
        return {"recommendations": []}


# ====== NEW ORDER WIZARD ======

def _get_iiko_credentials(waiter_id: int, db):
    """Helper: resolve waiter -> restaurant -> iiko token/org/terminal."""
    restaurant = db.get_waiter_restaurant(waiter_id)
    if not restaurant:
        raise HTTPException(status_code=400, detail="Ресторан не найден для официанта")
    iiko_key = db.get_iiko_key(restaurant)
    if not iiko_key:
        raise HTTPException(status_code=400, detail="iiko API ключ не настроен")
    token = get_iiko_token(iiko_key)
    if not token:
        raise HTTPException(status_code=502, detail="Не удалось получить iiko токен")
    org_id = get_organization_id(token)
    if not org_id:
        raise HTTPException(status_code=502, detail="Не удалось получить организацию iiko")
    terminal_id = get_terminal_group_id(token, org_id)
    if not terminal_id:
        raise HTTPException(status_code=502, detail="Не удалось получить терминал iiko")
    return token, org_id, terminal_id


@router.get("/iiko-tables")
async def get_iiko_tables(waiter_token: str = Header(None, alias="waiter-token"), db = Depends(get_db)):
    """Return all tables from iiko for table selection step."""
    if not waiter_token or not (waiter_token.isdigit() and waiter_token.isascii()):
        raise HTTPException(status_code=401, detail="waiter-token обязателен")
    waiter_id = int(waiter_token)
    token, org_id, terminal_id = _get_iiko_credentials(waiter_id, db)
    tables = get_all_tables(token, terminal_id)
    return {"tables": tables}


@router.post("/order/create-table-session")
async def create_table_session(data: CreateTableSessionRequest, waiter_token: str = Header(None, alias="waiter-token"), db = Depends(get_db)):
    """Step 2 of wizard: create an active table session with N guest slots."""
    if not waiter_token or not (waiter_token.isdigit() and waiter_token.isascii()):
        raise HTTPException(status_code=401, detail="waiter-token обязателен")
    waiter_id = int(waiter_token)

    # Check if this waiter already has this table open or in draft
    existing = db.cursor.execute(
        "SELECT id FROM waiter_active_tables WHERE waiter_id = ? AND table_number = ? AND status IN ('open', 'draft')",
        (waiter_id, data.table_number)
    ).fetchone()

    if existing:
        table_id = existing[0]
        # Update with new info
        db.cursor.execute(
            "UPDATE waiter_active_tables SET iiko_table_id = ?, guests_count = ?, order_type = ? WHERE id = ?",
            (data.iiko_table_id, data.guests_count, data.order_type, table_id)
        )
        db.connection.commit()
    else:
        # Create new active table with guest slots (draft until order is sent)
        db.cursor.execute("""
            INSERT INTO waiter_active_tables (waiter_id, client_id, table_number, basket_snapshot, total_price, status, iiko_table_id, guests_count, order_type)
            VALUES (?, 0, ?, '{}', 0, 'draft', ?, ?, ?)
        """, (waiter_id, data.table_number, data.iiko_table_id, data.guests_count, data.order_type))
        db.connection.commit()
        row = db.cursor.execute(
            "SELECT id FROM waiter_active_tables WHERE waiter_id = ? AND table_number = ? AND status = 'draft'",
            (waiter_id, data.table_number)
        ).fetchone()
        table_id = row[0]

    # Create guest slots (empty profiles for waiter to fill)
    existing_guests = db.get_table_guests(table_id)
    existing_count = len(existing_guests)

    import time
    # If existing has more guests than requested, remove extras
    if existing_count > data.guests_count:
        extras = existing_guests[data.guests_count:]
        for g in extras:
            extra_client_id = g[1]
            db.cursor.execute(
                "DELETE FROM waiter_active_table_guests WHERE active_table_id = ? AND client_id = ?",
                (table_id, extra_client_id)
            )
            try:
                db.set_basket(extra_client_id, {})
            except Exception:
                pass
        db.connection.commit()

    for i in range(existing_count, data.guests_count):
        guest_number = i + 1
        name = f"Гость {guest_number}"
        # Unique client_id based on timestamp and index to avoid collision
        temp_client_id = -(int(time.time() * 1000) % 100000000 + i)
        if not db.check_basket_exists(temp_client_id):
            db.create_basket(temp_client_id)
        db.add_guest_to_table(table_id, temp_client_id, name=name, guest_number=guest_number)

    # Reload guests to return
    guests_rows = db.get_table_guests(table_id)
    guests = []
    for idx, g in enumerate(guests_rows):
        # g = (id, client_id, basket_snapshot, name, created_at, guest_number)
        name = g[3]
        guest_number = g[5]
        if not name:
            name = f"Гость {guest_number or (idx + 1)}"
        
        guests.append({
            "client_id": g[1],
            "name": name,
            "slot_index": idx,
            "guest_number": guest_number
        })

    return {
        "success": True,
        "table_id": table_id,
        "table_number": data.table_number,
        "guests": guests,
        "order_type": data.order_type
    }


@router.post("/order/send-session")
async def send_session_order(data: SendSessionRequest, waiter_token: str = Header(None, alias="waiter-token"), db = Depends(get_db)):
    """Final step: send all guest baskets from the session to iiko."""
    if not waiter_token or not (waiter_token.isdigit() and waiter_token.isascii()):
        raise HTTPException(status_code=401, detail="waiter-token обязателен")
    waiter_id = int(waiter_token)

    # Get table info (could be draft or open)
    table_row = db.cursor.execute(
        "SELECT id, table_number, iiko_table_id, guests_count, order_type, sent_snapshot FROM waiter_active_tables WHERE id = ? AND status IN ('open', 'draft')",
        (data.table_id,)
    ).fetchone()

    if not table_row:
        raise HTTPException(status_code=404, detail="Активный стол не найден")

    table_number = table_row[1]
    iiko_table_id = table_row[2]
    guests_count = table_row[3] or 1
    order_type = table_row[4] or "new"
    prev_sent_raw = table_row[5]

    # Parse previously sent snapshot
    prev_sent = {}
    if prev_sent_raw:
        try:
            prev_sent = json.loads(prev_sent_raw)
        except:
            prev_sent = {}

    # Collect all guest baskets
    guests = db.get_table_guests(data.table_id)
    if not guests:
        raise HTTPException(status_code=400, detail="У стола нет гостей")

    combined_basket = {}
    for g in guests:
        client_id = g[1]
        g_basket = db.get_basket(client_id)
        if g_basket and isinstance(g_basket, dict):
            for dish_name, dish_data in g_basket.items():
                if dish_name in combined_basket:
                    combined_basket[dish_name][1] += dish_data[1]
                else:
                    combined_basket[dish_name] = list(dish_data)

    if not combined_basket:
        raise HTTPException(status_code=400, detail="Корзины всех гостей пусты")

    # Compute delta: only new/increased items
    delta_basket = {}
    for dish_name, dish_data in combined_basket.items():
        prev_qty = prev_sent.get(dish_name, [None, 0])[1] if dish_name in prev_sent else 0
        current_qty = dish_data[1]
        diff = current_qty - prev_qty
        if diff > 0:
            delta_entry = list(dish_data)
            delta_entry[1] = diff
            delta_basket[dish_name] = delta_entry

    is_first_send = not prev_sent
    has_delta = bool(delta_basket)

    if not has_delta and not is_first_send:
        # Nothing new to send
        return {"success": True, "message": f"Нет новых блюд для отправки (стол {table_number})"}

    send_basket = delta_basket if not is_first_send else combined_basket

    # MOCK MODE: skip real iiko calls, just pretend success
    IIKO_MOCK = True

    if IIKO_MOCK:
        result = {"mock": True}
        print(f"[IIKO MOCK] Стол {table_number}: заказ НЕ отправлен в iiko (мок)")
    else:
        token, org_id, terminal_id = _get_iiko_credentials(waiter_id, db)
        items = resolve_basket_to_iiko_items(send_basket, db)
        if not items:
            raise HTTPException(status_code=400, detail="Не удалось подготовить позиции для iiko (нет iiko_id у блюд)")

        order_comment = data.order_comment or None

        if not is_first_send and iiko_table_id:
            existing_order_id = get_active_order_for_table(token, org_id, iiko_table_id)
            if existing_order_id:
                result = add_items_to_iiko_order(token, org_id, existing_order_id, items)
            else:
                result = create_iiko_order(token, org_id, terminal_id, items, table_id=iiko_table_id, table_number=table_number, guests_count=guests_count, comment=order_comment)
        else:
            result = create_iiko_order(token, org_id, terminal_id, items, table_id=iiko_table_id, table_number=table_number, guests_count=guests_count, comment=order_comment)

        if not result:
            raise HTTPException(status_code=500, detail="Ошибка отправки заказа в iiko")

    delta_count = sum(d[1] for d in send_basket.values())
    print(f"[IIKO] Стол {table_number}: {'первая отправка' if is_first_send else 'дозаказ'}, блюд: {delta_count}")

    # Update table total + save sent snapshot
    all_menu = db.menu_get()
    total = 0
    for dish_name, dish_data in combined_basket.items():
        if not dish_data:
            continue
        dish_id = dish_data[0]
        quantity = dish_data[1]
        for m in all_menu:
            if m[0] == dish_id:
                price = int(m[8]) if len(m) > 8 and m[8] else 0
                total += price * quantity
                break
    db.cursor.execute(
        "UPDATE waiter_active_tables SET total_price = ?, basket_snapshot = ?, sent_snapshot = ?, status = 'open' WHERE id = ?",
        (total, json.dumps(combined_basket, ensure_ascii=False), json.dumps(combined_basket, ensure_ascii=False), data.table_id)
    )
    db.connection.commit()

    msg = f"Заказ для стола {table_number} отправлен (гостей: {guests_count})"
    if not is_first_send:
        msg = f"Дозаказ для стола {table_number}: +{delta_count} позиций"
    return {"success": True, "message": msg}
