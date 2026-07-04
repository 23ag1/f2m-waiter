import re
from enum import Enum
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from app.routers.loyalty import sync_loyalty
from app.routers.purchases import sync_purchases
from pydantic import BaseModel, Field, field_validator
from app.limiter import limiter

router = APIRouter()

_PHONE_RE = re.compile(r'^\d{10,15}$')


class CallbackType(str, Enum):
    change_balance = "ChangeBalance"


class PremiumBonusPayload(BaseModel):
    callback: CallbackType = Field(..., description="Тип события от PremiumBonus")
    phone: str = Field(..., description="Номер телефона клиента (только цифры, 10-15 символов)", example="79001234567")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = re.sub(r'[+\s\-()\.]', '', v)
        if not _PHONE_RE.match(cleaned):
            raise ValueError("Invalid phone number format")
        return cleaned


class CallbackResponse(BaseModel):
    status: str = Field(..., example="ok")


def init_db(db_pool):
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS premium_bonus_callbacks (
                    id SERIAL PRIMARY KEY,
                    callback VARCHAR(255) NOT NULL,
                    phone VARCHAR(20) NOT NULL,
                    raw_payload JSONB,
                    received_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        conn.commit()
    finally:
        db_pool.putconn(conn)


@router.post(
    "/callback",
    response_model=CallbackResponse,
    summary="Получить callback от PremiumBonus",
    description="Принимает событие от системы лояльности PremiumBonus. Требует заголовок `X-API-Key`.",
    responses={
        403: {"description": "Запрос с неразрешённого IP-адреса"},
        422: {"description": "Ошибка валидации (неверный формат телефона или неизвестный тип callback)"},
        429: {"description": "Превышен лимит запросов (30/мин с одного IP)"},
    },
)
@limiter.limit("30/minute")
def receive_callback(
    request: Request,
    payload: PremiumBonusPayload,
    background_tasks: BackgroundTasks,
):
    db_pool = request.app.state.db_pool
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO premium_bonus_callbacks (callback, phone, raw_payload)
                VALUES (%s, %s, %s::jsonb)
                """,
                (payload.callback, payload.phone, payload.model_dump_json()),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500)
    finally:
        db_pool.putconn(conn)
    background_tasks.add_task(sync_loyalty, payload.phone, db_pool)
    background_tasks.add_task(sync_purchases, payload.phone, db_pool)
    return CallbackResponse(status="ok")
