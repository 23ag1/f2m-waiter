"""
Эндпоинты для ИИ-рассылки персонализированных сообщений.

Поток:
  1. POST /preview  — админ вводит текст → LLM извлекает фильтры → фильтрация profile → LLM генерирует сообщения → превью
  2. POST /send     — принимает превью → отправляет через Telegram Bot API
  3. GET  /history   — лог рассылок
"""

import os
import json
import asyncio
import logging
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .broadcast_service import (
    extract_filters,
    filter_profiles_pg,
    generate_messages_for_users,
    generate_message_for_profile,
    send_telegram_message,
    log_broadcast,
    get_broadcast_history,
    count_all_profiles,
    PROMPT_TEMPLATE_LABELS,
)

logger = logging.getLogger(__name__)
router = APIRouter()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# --------------- Pydantic models ---------------

class BroadcastPreviewRequest(BaseModel):
    admin_request: str = Field(..., description="Текст запроса администратора", min_length=3)
    model: str = Field("gigachat", description="LLM провайдер: gigachat | deepseek | bothub")
    template: str = Field("standard", description="Ключ шаблона промпта")
    sex: Optional[str] = Field(None, description="Фильтр пола: 'Мужчина' | 'Женщина' | null")
    age_min: Optional[int] = Field(None, ge=0, le=120)
    age_max: Optional[int] = Field(None, ge=0, le=120)
    last_visit: Optional[str] = Field(
        None,
        description="Бакет последнего посещения: week | month | 3months | earlier | null",
    )

class RecipientPreview(BaseModel):
    user_id: int
    user_name: Optional[str] = None
    age: Optional[str] = None
    sex: Optional[str] = None
    message: str
    reasons: List[str] = Field(default_factory=list)

class BroadcastPreviewResponse(BaseModel):
    filters: dict
    total_in_db: int
    total_matched: int
    total_after_llm: int
    recipients: List[RecipientPreview]

class SendItem(BaseModel):
    user_id: int
    message: str

class BroadcastSendRequest(BaseModel):
    admin_request: str = Field(..., description="Исходный запрос (для лога)")
    model: str = Field("gigachat")
    filters: dict = Field(default_factory=dict)
    recipients: List[SendItem]

class SendResult(BaseModel):
    user_id: int
    ok: bool
    error: Optional[str] = None

class BroadcastSendResponse(BaseModel):
    sent: int
    failed: int
    results: List[SendResult]

class BroadcastHistoryItem(BaseModel):
    id: int
    admin_request: str
    model: str
    filters: dict
    recipients_count: int
    sent_count: int
    skipped_count: int
    created_at: str


# --------------- helpers ---------------

def _get_db():
    from .main import db
    if db is None:
        raise HTTPException(status_code=503, detail="БД не инициализирована")
    return db


# --------------- endpoints ---------------

@router.get(
    "/templates",
    summary="Список доступных шаблонов промптов",
)
async def list_templates():
    return [{"key": k, "label": v} for k, v in PROMPT_TEMPLATE_LABELS.items()]


@router.post(
    "/preview",
    response_model=BroadcastPreviewResponse,
    summary="Превью рассылки: фильтрация + генерация сообщений",
)
async def broadcast_preview(req: BroadcastPreviewRequest):
    db = _get_db()

    # 1. LLM → фильтры
    try:
        filters = await asyncio.to_thread(
            extract_filters, req.admin_request, req.model
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ошибка извлечения фильтров: {e}")

    # Нормализация: LLM иногда возвращает массив там, где ожидается строка.
    for _k in ("sex", "style", "temp_state", "temp_category"):
        _v = filters.get(_k)
        if isinstance(_v, list):
            filters[_k] = _v[0] if _v else None

    # Валидация энумов: LLM может галлюцинировать значения вне словаря → стираем.
    _ALLOWED_STYLE = {"диетическое", "стандартное", "веганство", "вегетарианство"}
    _sv = filters.get("style")
    if isinstance(_sv, str) and _sv.strip().lower() not in _ALLOWED_STYLE:
        logger.info(f"Невалидный style от LLM: {_sv!r} — сбрасываю")
        filters["style"] = None

    # Страховка: выкидываем из blacklist общие слова, по которым фильтровать бессмысленно
    _GENERIC_BLACKLIST = {
        "овощи", "овощ", "салат", "салаты", "гарнир", "гарниры",
        "соус", "соусы", "зелень", "масло", "растительное масло",
        "оливковое масло", "соль", "перец", "специи", "приправы",
        "хлеб", "вода", "сахар",
    }
    bl = filters.get("blacklist_ingredients")
    if isinstance(bl, list):
        filters["blacklist_ingredients"] = [
            x for x in bl
            if isinstance(x, str) and x.strip().lower() not in _GENERIC_BLACKLIST
        ]

    # UI перекрывает LLM для сегментных полей (sex/age/last_visit).
    # Пустые строки и None из UI означают «фильтра нет».
    filters["sex"] = req.sex or None
    filters["age_min"] = req.age_min
    filters["age_max"] = req.age_max
    filters["last_visit"] = req.last_visit or None

    # 2. PostgreSQL → подходящие профили
    try:
        total_in_db = count_all_profiles(db)
        profiles = filter_profiles_pg(db, filters)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка фильтрации: {e}")

    total_matched = len(profiles)

    if not profiles:
        return BroadcastPreviewResponse(
            filters=filters,
            total_in_db=total_in_db,
            total_matched=0,
            total_after_llm=0,
            recipients=[],
        )

    # 3. LLM → персональные сообщения
    try:
        messages = await asyncio.to_thread(
            generate_messages_for_users, req.admin_request, profiles, req.model, req.template
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ошибка генерации сообщений: {e}")

    recipients = [
        RecipientPreview(
            user_id=m["user_id"],
            user_name=m.get("fio"),
            age=m.get("age"),
            sex=m.get("sex"),
            message=m["message"],
            reasons=m.get("reasons") or [],
        )
        for m in messages
    ]

    return BroadcastPreviewResponse(
        filters=filters,
        total_in_db=total_in_db,
        total_matched=total_matched,
        total_after_llm=len(recipients),
        recipients=recipients,
    )


@router.post(
    "/preview/stream",
    summary="Потоковое превью: NDJSON с пошаговым прогрессом генерации",
)
async def broadcast_preview_stream(req: BroadcastPreviewRequest):
    """
    Отдаёт NDJSON-поток событий:
      {"event":"filters", "filters":{...}}
      {"event":"matched", "total_in_db":N, "total_matched":M}
      {"event":"recipient", "index":i, "generated":k, "total":M, "recipient":{...}}
      {"event":"skip", "index":i, "total":M}
      {"event":"done", "total_in_db":N, "total_matched":M, "total_after_llm":K}
      {"event":"error", "detail":"..."}
    """
    db = _get_db()

    async def _stream():
        def _emit(obj):
            return json.dumps(obj, ensure_ascii=False) + "\n"

        # 1. LLM → фильтры
        try:
            filters = await asyncio.to_thread(
                extract_filters, req.admin_request, req.model
            )
        except Exception as e:
            yield _emit({"event": "error", "detail": f"Ошибка извлечения фильтров: {e}"})
            return

        # нормализация + валидация (зеркало batch-версии)
        for _k in ("sex", "style", "temp_state", "temp_category"):
            _v = filters.get(_k)
            if isinstance(_v, list):
                filters[_k] = _v[0] if _v else None

        _ALLOWED_STYLE = {"диетическое", "стандартное", "веганство", "вегетарианство"}
        _sv = filters.get("style")
        if isinstance(_sv, str) and _sv.strip().lower() not in _ALLOWED_STYLE:
            filters["style"] = None

        if isinstance(filters.get("blacklist_ingredients"), list):
            _GENERIC = {
                "овощи", "овощ", "салат", "салаты", "гарнир", "гарниры",
                "соус", "соусы", "зелень", "масло", "растительное масло",
                "оливковое масло", "соль", "перец", "специи", "приправы",
                "хлеб", "вода", "сахар",
            }
            filters["blacklist_ingredients"] = [
                x for x in filters["blacklist_ingredients"]
                if isinstance(x, str) and x.strip().lower() not in _GENERIC
            ]

        # UI-перекрытие
        filters["sex"] = req.sex or None
        filters["age_min"] = req.age_min
        filters["age_max"] = req.age_max
        filters["last_visit"] = req.last_visit or None

        yield _emit({"event": "filters", "filters": filters})

        # 2. фильтрация профилей
        try:
            total_in_db = await asyncio.to_thread(count_all_profiles, db)
            profiles = await asyncio.to_thread(filter_profiles_pg, db, filters)
        except Exception as e:
            yield _emit({"event": "error", "detail": f"Ошибка фильтрации: {e}"})
            return

        total_matched = len(profiles)
        yield _emit({"event": "matched", "total_in_db": total_in_db, "total_matched": total_matched})

        # 3. генерация — по одному юзеру, с прогрессом
        generated = 0
        for i, profile in enumerate(profiles):
            try:
                msg = await asyncio.to_thread(
                    generate_message_for_profile,
                    req.admin_request, profile, req.model, req.template,
                )
            except Exception as e:
                logger.warning(f"Ошибка генерации для user_id={profile.get('user_id')}: {e}")
                msg = None

            if msg:
                generated += 1
                yield _emit({
                    "event": "recipient",
                    "index": i,
                    "generated": generated,
                    "total": total_matched,
                    "recipient": {
                        "user_id": msg["user_id"],
                        "user_name": msg.get("fio"),
                        "age": msg.get("age"),
                        "sex": msg.get("sex"),
                        "message": msg["message"],
                        "reasons": msg.get("reasons") or [],
                    },
                })
            else:
                yield _emit({"event": "skip", "index": i, "total": total_matched})

        yield _emit({
            "event": "done",
            "total_in_db": total_in_db,
            "total_matched": total_matched,
            "total_after_llm": generated,
        })

    return StreamingResponse(
        _stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/send",
    response_model=BroadcastSendResponse,
    summary="Отправить рассылку через Telegram Bot API",
)
async def broadcast_send(req: BroadcastSendRequest):
    if not BOT_TOKEN:
        raise HTTPException(status_code=500, detail="BOT_TOKEN не задан в .env")

    db = _get_db()
    results: List[SendResult] = []
    sent = 0
    failed = 0

    async with httpx.AsyncClient() as client:
        for item in req.recipients:
            ok, err = await send_telegram_message(
                client, BOT_TOKEN, item.user_id, item.message
            )
            results.append(SendResult(user_id=item.user_id, ok=ok, error=err))
            if ok:
                sent += 1
            else:
                failed += 1
            # Telegram rate limit: ~30 msg/sec
            await asyncio.sleep(0.05)

    # Логируем
    try:
        log_broadcast(
            db,
            admin_request=req.admin_request,
            model=req.model,
            filters=req.filters,
            recipients_count=len(req.recipients),
            sent_count=sent,
            skipped_count=failed,
        )
    except Exception as e:
        logger.warning(f"Не удалось записать лог рассылки: {e}")

    return BroadcastSendResponse(sent=sent, failed=failed, results=results)


@router.get(
    "/history",
    response_model=List[BroadcastHistoryItem],
    summary="История рассылок",
)
async def broadcast_history(limit: int = 50):
    db = _get_db()
    try:
        rows = get_broadcast_history(db, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения истории: {e}")

    return [
        BroadcastHistoryItem(
            id=r["id"],
            admin_request=r["admin_request"],
            model=r["model"],
            filters=json.loads(r["filters"]) if isinstance(r["filters"], str) else r["filters"],
            recipients_count=r["recipients_count"],
            sent_count=r["sent_count"],
            skipped_count=r["skipped_count"],
            created_at=str(r["created_at"]),
        )
        for r in rows
    ]
