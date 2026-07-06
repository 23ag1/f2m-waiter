import sys
import os
import requests
from typing import Optional

BASE_URL = 'https://api-ru.iiko.services/api/1/'

def get_iiko_token(api_key: str) -> Optional[str]:
    try:
        url = f'{BASE_URL}access_token'
        response = requests.post(url, json={'apiLogin': api_key}, timeout=10)
        response.raise_for_status()
        token = response.json().get('token')
        print(f'[IIKO] ✅ Token получен: {token[:10]}...')
        return token
    except Exception as e:
        print(f'[IIKO] ❌ Ошибка получения token: {e}')
        return None

def get_iiko_stop_list(token: str, org_id: str) -> list:
    """Fetch stop list from iiko. Returns list of productId UUIDs."""
    try:
        url = f'{BASE_URL}stop_lists'
        response = requests.post(url, json={'organizationIds': [org_id]},
                                 headers={'Authorization': f'Bearer {token}'},
                                 timeout=15)
        response.raise_for_status()
        data = response.json()
        product_ids = []
        for tg in data.get('terminalGroupStopLists', []):
            items_wrapper = tg.get('items', [])
            # items_wrapper can be the TerminalGroupStopList directly or wrapped
            if isinstance(items_wrapper, dict):
                items_wrapper = [items_wrapper]
            for item_group in items_wrapper if isinstance(items_wrapper, list) else [items_wrapper]:
                if isinstance(item_group, dict):
                    for item in item_group.get('items', []):
                        pid = item.get('productId')
                        if pid and pid not in product_ids:
                            product_ids.append(pid)
        print(f'[IIKO] Stop list: {len(product_ids)} products')
        return product_ids
    except Exception as e:
        print(f'[IIKO] ❌ Ошибка получения stop list: {e}')
        return []


def get_organization_id(token: str) -> Optional[str]:
    try:
        url = f'{BASE_URL}organizations'
        response = requests.post(url, json={
            'organizationIds': None,
            'returnAdditionalInfo': False,
            'includeDisabled': False
        }, headers={'Authorization': f'Bearer {token}'}, timeout=10)
        response.raise_for_status()
        orgs = response.json().get('organizations', [])
        if orgs:
            org_id = orgs[0]['id']
            org_name = orgs[0].get('name', 'unknown')
            print(f'[IIKO] Организация: {org_name} ({org_id})')
            return org_id
        return None
    except Exception as e:
        print(f'[IIKO] ❌ Ошибка получения организации: {e}')
        return None

def get_terminal_group_id(token: str, organization_id: str) -> Optional[str]:
    try:
        url = f'{BASE_URL}terminal_groups'
        response = requests.post(url, json={
            'organizationIds': [organization_id],
            'includeDisabled': False
        }, headers={'Authorization': f'Bearer {token}'}, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        sleep_groups = data.get('terminalGroupsInSleep', [])
        sleep_ids = set()
        for group in sleep_groups:
            for item in group.get('items', []):
                sleep_ids.add(item.get('id'))
                
        groups = data.get('terminalGroups', [])
        for group in groups:
            for item in group.get('items', []):
                term_id = item.get('id')
                term_name = item.get('name', 'unknown')
                if term_id not in sleep_ids:
                    print(f'[IIKO] Активный терминал: {term_name} ({term_id})')
                    return term_id
        return None
    except Exception as e:
        print(f'[IIKO] ❌ Ошибка получения терминала: {e}')
        return None

def get_all_tables(token: str, terminal_id: str) -> list:
    """Возвращает список всех столов из iiko: [{id, name, number, section_name}]."""
    try:
        url = f'{BASE_URL}reserve/available_restaurant_sections'
        response = requests.post(url, json={
            'terminalGroupIds': [terminal_id],
            'returnSchema': False
        }, headers={'Authorization': f'Bearer {token}'}, timeout=10)
        response.raise_for_status()

        data = response.json()
        sections = data.get('restaurantSections', [])
        tables = []
        for section in sections:
            section_name = section.get('name', '')
            for table in section.get('tables', []):
                tables.append({
                    'id': table.get('id'),
                    'name': str(table.get('name', '')).strip(),
                    'number': int(table.get('number', 0)),
                    'section_name': section_name
                })
        tables.sort(key=lambda t: t['number'])
        print(f'[IIKO] Получено {len(tables)} столов')
        return tables
    except Exception as e:
        print(f'[IIKO] ❌ Ошибка получения столов: {e}')
        return []


def get_table_id(token: str, terminal_id: str, table_number: str) -> Optional[str]:
    try:
        url = f'{BASE_URL}reserve/available_restaurant_sections'
        response = requests.post(url, json={
            'terminalGroupIds': [terminal_id],
            'returnSchema': False
        }, headers={'Authorization': f'Bearer {token}'}, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        sections = data.get('restaurantSections', [])
        if not sections:
            return None
            
        for item in sections:
            for table in item.get('tables', []):
                name = str(table.get('name', '')).strip()
                number = str(table.get('number', '')).strip()
                if str(table_number) in (name, number):
                    print(f'[IIKO] ✅ Найден стол {table_number} с ID: {table["id"]}')
                    return table["id"]
                    
        print(f'[IIKO] ❌ Стол {table_number} не найден в iiko')
        return None
    except Exception as e:
        print(f'[IIKO] ❌ Ошибка поиска стола: {e}')
        return None

def _resolve_dish_entry_to_iiko_item(dish_name: str, dish_data: list, db, all_menu: list,
                                      amount_override: float = None, guest_id: str = None) -> Optional[dict]:
    """Строит один iiko item из одной записи корзины (dish_name -> dish_data).

    amount_override — если задано, используется вместо dish_data[1] (нужно для
    половинок при разделении блюда). guest_id — если задано, проставляется в
    item['guestId'] (используется iiko для разбивки чека между гостями).
    """
    quantity = amount_override if amount_override is not None else (dish_data[1] if len(dish_data) > 1 else 1)
    dish_id = dish_data[0] if len(dish_data) > 0 else None

    # Резолвим iiko_id прежде всего по dish_id (надёжно даже если ключ корзины —
    # не точное название блюда из Menu, например половинка "Плов (½)" при split).
    # Резолв по имени — фолбэк для dish_id=0/None (passthrough-блюда без каталожной записи).
    iiko_id = None
    if dish_id and dish_id != 0:
        for dish in all_menu:
            if dish[0] == dish_id and len(dish) > 10 and dish[10]:
                iiko_id = dish[10]
                break
    if not iiko_id:
        iiko_id = db.get_iiko_id_by_dish_name(dish_name)

    # Если в БД не нашли iiko_id, проверяем passthrough из корзины (index 3 может быть строкой iiko_id)
    passthrough_iiko_id = None
    if not iiko_id:
        # passthrough iiko_id хранится в index 3 как строка (не список модификаторов)
        if len(dish_data) > 3 and isinstance(dish_data[3], str):
            passthrough_iiko_id = dish_data[3]
            iiko_id = passthrough_iiko_id
            print(f'[IIKO] 📦 {dish_name} — используем passthrough iiko_id: {iiko_id}')

    if not iiko_id:
        print(f'[IIKO] ⚠️ {dish_name} — iiko_id не найден, пропускаем')
        return None

    # Находим цену блюда (обязательно для add_items)
    price = 0
    if dish_id and dish_id != 0:
        for dish in all_menu:
            if dish[0] == dish_id:
                price = float(dish[8]) if len(dish) > 8 and dish[8] else 0
                break
    item = {
        'productId': iiko_id,
        'type': 'Product',
        'amount': quantity,
        'price': price
    }
    if guest_id:
        item['guestId'] = guest_id

    # Append modifiers if present
    # Для passthrough-блюд модификаторы в index 2, для обычных — index 3 (список)
    if passthrough_iiko_id:
        # passthrough: [dish_id=0, quantity, modifiers_list, iiko_id_str]
        basket_mods_raw = dish_data[2] if len(dish_data) > 2 else []
    else:
        basket_mods_raw = dish_data[3] if len(dish_data) > 3 and isinstance(dish_data[3], list) else []

    basket_mods = basket_mods_raw if isinstance(basket_mods_raw, list) else []
    if basket_mods:
        iiko_modifiers = []
        for mod in basket_mods:
            if mod is None:
                continue
            mod_id = mod.get('modifier_id') or mod.get('productId') if isinstance(mod, dict) else None
            mod_amount = mod.get('amount', 1) if isinstance(mod, dict) else 1
            if mod_id:
                mod_entry = {'productId': mod_id, 'amount': mod_amount}
                group_id = mod.get('group_id') or mod.get('productGroupId') if isinstance(mod, dict) else None
                if group_id:
                    mod_entry['productGroupId'] = group_id
                iiko_modifiers.append(mod_entry)
        if iiko_modifiers:
            item['modifiers'] = iiko_modifiers
            print(f'[IIKO] 🔧 {dish_name}: {len(iiko_modifiers)} модификатор(ов)')

    # Append comment if present (index 4 in basket array for normal, not applicable for passthrough)
    comment_idx = 4 if not passthrough_iiko_id else None
    dish_comment = dish_data[comment_idx] if comment_idx and len(dish_data) > comment_idx and isinstance(dish_data[comment_idx], str) else ""
    if dish_comment:
        item['comment'] = dish_comment[:255]

    print(f'[IIKO] ✅ {dish_name} → {iiko_id} (x{quantity}, price={price}{", guest=" + guest_id if guest_id else ""})')
    return item


def _split_marker(dish_data: list) -> Optional[dict]:
    """Index 5 of a basket entry, when present, marks it as one half of a dish
    split between two guests: {'split_guest_id': <client_id>}. See split_dish_between_guests()."""
    if len(dish_data) > 5 and isinstance(dish_data[5], dict) and dish_data[5].get('split_guest_id') is not None:
        return dish_data[5]
    return None


def resolve_basket_to_iiko_items(basket: dict, db) -> list:
    all_menu = db.menu_get()
    items = []
    for dish_name, dish_data in basket.items():
        marker = _split_marker(dish_data)
        guest_id = str(marker['split_guest_id']) if marker else None
        item = _resolve_dish_entry_to_iiko_item(dish_name, dish_data, db, all_menu, guest_id=guest_id)
        if item:
            items.append(item)
    return items


def get_active_order_for_table(token: str, organization_id: str, table_id: str) -> Optional[str]:
    """Ищет активный заказ на столе. Возвращает order_id или None."""
    try:
        url = f'{BASE_URL}order/by_table'
        payload = {
            'organizationIds': [organization_id],
            'tableIds': [table_id],
            'statuses': ['New', 'Bill']
        }
        response = requests.post(
            url, json=payload,
            headers={'Authorization': f'Bearer {token}'},
            timeout=15
        )
        response.raise_for_status()
        orders_data = response.json().get('orders', [])

        for order_entry in orders_data:
            if order_entry.get('creationStatus') == 'Success':
                order_obj = order_entry.get('order', {})
                order_id = order_obj.get('id')
                if order_id:
                    print(f'[IIKO] Найден активный заказ {order_id} на столе')
                    return order_id
        return None
    except Exception as e:
        print(f'[IIKO] ❌ Ошибка поиска активного заказа: {e}')
        return None


def get_order_item_statuses(token: str, organization_id: str, table_id: str) -> dict:
    """Опрашивает order/by_table и возвращает статус каждой позиции активного заказа.

    Статусы iiko (OrderItemStatus): PrintedNotCooking, CookingStarted,
    CookingCompleted, Served. Также возвращает статус самого заказа (New/Bill/...),
    который на фронте маппится в 'precheck', когда напечатан пречек (статус Bill).

    Возвращает {'order_id', 'order_status', 'items': [{'productId', 'status', 'amount', 'guestId'}]}.
    Пустые значения (order_id=None, items=[]) — если активного заказа нет.
    """
    try:
        url = f'{BASE_URL}order/by_table'
        payload = {
            'organizationIds': [organization_id],
            'tableIds': [table_id],
            'statuses': ['New', 'Bill']
        }
        response = requests.post(
            url, json=payload,
            headers={'Authorization': f'Bearer {token}'},
            timeout=15
        )
        response.raise_for_status()
        orders_data = response.json().get('orders', [])

        for order_entry in orders_data:
            if order_entry.get('creationStatus') != 'Success':
                continue
            order_obj = order_entry.get('order', {})
            order_id = order_obj.get('id')
            if not order_id:
                continue
            items_out = []
            for it in order_obj.get('items', []):
                items_out.append({
                    'productId': it.get('productId'),
                    'status': it.get('status'),
                    'amount': it.get('amount'),
                    'guestId': it.get('guestId'),
                })
            return {
                'order_id': order_id,
                'order_status': order_obj.get('status'),
                'items': items_out,
            }
        return {'order_id': None, 'order_status': None, 'items': []}
    except Exception as e:
        print(f'[IIKO] ❌ Ошибка получения статусов позиций: {e}')
        return {'order_id': None, 'order_status': None, 'items': []}


def add_items_to_iiko_order(token: str, organization_id: str, order_id: str, items: list) -> Optional[dict]:
    """Дозаказ: добавляет позиции к существующему заказу с автопечатью сервис-чека."""
    try:
        url = f'{BASE_URL}order/add_items'
        payload = {
            'organizationId': organization_id,
            'orderId': order_id,
            'items': items,
            'addOrderItemsSettings': {
                'servicePrint': True
            }
        }
        print(f'[IIKO] Дозаказ: {len(items)} позиций к заказу {order_id}')
        response = requests.post(
            url, json=payload,
            headers={'Authorization': f'Bearer {token}'},
            timeout=15
        )
        response.raise_for_status()
        result = response.json()
        print(f'[IIKO] ✅ Дозаказ отправлен, correlationId={result.get("correlationId")}')
        return result
    except requests.exceptions.HTTPError as e:
        print(f'[IIKO] ❌ HTTP ошибка дозаказа: {e}')
        if e.response is not None:
            print(f'[IIKO] Response: {e.response.text}')
        return None
    except Exception as e:
        print(f'[IIKO] ❌ Ошибка дозаказа: {e}')
        return None

def create_iiko_order(token: str, organization_id: str, terminal_group_id: str,
                      items: list, table_id: str = None, table_number: str = None, guests_count: int = 1, comment: str = None, waiter_id: int = None) -> Optional[dict]:
    try:
        url = f'{BASE_URL}order/create'

        order_data = {'items': items}
        if table_id:
            order_data['tableIds'] = [table_id]
        elif table_number:
            order_data['tabName'] = f'Стол {table_number}'

        if guests_count and guests_count > 0:
            order_data['guests'] = {'count': guests_count}

        external_data = []
        if comment:
            external_data.append({'key': 'waiter_comment', 'value': comment[:255]})
        if waiter_id:
            external_data.append({'key': 'waiter_id', 'value': str(waiter_id)})
        if external_data:
            order_data['externalData'] = external_data
        
        payload = {
            'organizationId': organization_id,
            'terminalGroupId': terminal_group_id,
            'order': order_data,
            'createOrderSettings': {
                'servicePrint': True
            }
        }
        
        print(f'[IIKO] Отправка заказа: {len(items)} позиций, стол: {table_number} (tableId: {table_id}), гости: {guests_count}')
        
        response = requests.post(
            url,
            json=payload,
            headers={'Authorization': f'Bearer {token}'},
            timeout=15
        )
        response.raise_for_status()
        result = response.json()
        print(f'[IIKO] ✅ Заказ создан, ожидаем подтверждения от POS...')
        return result
        
    except requests.exceptions.HTTPError as e:
        print(f'[IIKO] ❌ HTTP ошибка создания заказа: {e}')
        if e.response is not None:
            print(f'[IIKO] Response: {e.response.text}')
        return None
    except Exception as e:
        print(f'[IIKO] ❌ Ошибка создания заказа: {e}')
        return None

async def send_order_to_iiko(basket: dict, waiter_id: int, table_number: str, db, guests_count: int = 1) -> bool:
    try:
        restaurant = db.get_waiter_restaurant(waiter_id)
        if not restaurant:
            return False
            
        iiko_key = db.get_iiko_key(restaurant)
        if not iiko_key:
            print(f'[IIKO] Ключ для {restaurant} не найден, пропуск отправки')
            return False
            
        token = get_iiko_token(iiko_key)
        if not token:
            return False
            
        org_id = get_organization_id(token)
        if not org_id:
            return False
            
        terminal_id = get_terminal_group_id(token, org_id)
        if not terminal_id:
            return False
            
        items = resolve_basket_to_iiko_items(basket, db)
        if not items:
            return False

        table_id = get_table_id(token, terminal_id, table_number)

        # Проверяем, есть ли уже активный заказ на этом столе
        existing_order_id = get_active_order_for_table(token, org_id, table_id) if table_id else None

        if existing_order_id:
            print(f'[IIKO] Стол {table_number} уже имеет заказ {existing_order_id}, делаем дозаказ')
            result = add_items_to_iiko_order(token, org_id, existing_order_id, items)
        else:
            result = create_iiko_order(token, org_id, terminal_id, items, table_id=table_id, table_number=table_number, guests_count=guests_count, waiter_id=waiter_id)

        return result is not None
        
    except Exception as e:
        print(f'[IIKO] ❌ Критическая ошибка: {e}')
        return False

def print_iiko_bill(token: str, organization_id: str, terminal_group_id: str, table_id: str = None, table_number: str = None) -> bool:
    try:
        if not table_id:
            table_id = get_table_id(token, terminal_group_id, table_number)
            if not table_id:
                print(f"[IIKO] ❌ Не удалось найти table_id для стола {table_number}")
                return False

        order_id = get_active_order_for_table(token, organization_id, table_id)
        if not order_id:
            print(f"[IIKO] ❌ Активный заказ для стола {table_number} не найден")
            return False

        print(f"[IIKO] Печать пречека для заказа {order_id}, стол {table_number}")

        print_url = f'{BASE_URL}order/print_bill'
        print_response = requests.post(
            print_url,
            json={'organizationId': organization_id, 'orderId': order_id},
            headers={'Authorization': f'Bearer {token}'},
            timeout=15
        )
        print_response.raise_for_status()
        print(f"[IIKO] ✅ Пречек для стола {table_number} отправлен на печать")
        return True
    except Exception as e:
        print(f"[IIKO] ❌ Ошибка при печати пречека: {e}")
        return False

