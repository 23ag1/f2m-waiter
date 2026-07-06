from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class WaiterLogin(BaseModel):
    pin_code: str

class WaiterRegister(BaseModel):
    restaurant_password: str
    name: str
    pin_code: str

class WaiterLoginResponse(BaseModel):
    success: bool
    waiter_token: str
    message: str

class QRScanRequest(BaseModel):
    qr_payload: str
    table_number: Optional[str] = None

class ClientResponse(BaseModel):
    success: bool
    client_id: Optional[int] = None
    message: str

class ModifierSelection(BaseModel):
    modifier_id: str
    name: str
    amount: int = 1
    group_id: Optional[str] = None

class DishModifyRequest(BaseModel):
    dish_id: int
    delta: int  # +1 or -1
    modifiers: Optional[List[ModifierSelection]] = None
    comment: Optional[str] = None  # comment for dish (max 255 chars for iiko)

class DishRemoveRequest(BaseModel):
    dish_id: int

class PrintBillRequest(BaseModel):
    table_number: str

class OrderSendRequest(BaseModel):
    table_number: str

class CreateTableSessionRequest(BaseModel):
    iiko_table_id: str
    table_number: str
    guests_count: int = 1
    order_type: str = "new"  # "new" or "add"

class SendSessionRequest(BaseModel):
    table_id: int  # waiter_active_tables.id
    order_comment: Optional[str] = None  # general order comment

class SendCourseRequest(BaseModel):
    table_id: int  # waiter_active_tables.id
    dish_ids: List[int]  # Menu.Dish_id positions to fire on the kitchen now

class SplitDishRequest(BaseModel):
    source_client_id: int  # guest currently holding the whole (unsplit) dish
    dish_id: int
    target_client_ids: List[int]  # exactly 2 guests to split the dish between
