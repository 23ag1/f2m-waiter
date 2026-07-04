"""
FastAPI entry point — только ИИ-рассылка.
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Broadcast Demo",
    description="Персонализированные рассылки: фильтрация по профилю + LLM-генерация.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- DB ----
db = None


@app.on_event("startup")
def _init_db():
    global db
    from .db import Database
    db = Database()
    logger.info("PostgreSQL подключение инициализировано")


@app.on_event("shutdown")
def _close_db():
    if db is not None:
        db.close()


# ---- Routers ----
from .broadcast_endpoints import router as broadcast_router  # noqa: E402

app.include_router(broadcast_router, prefix="/api/v1/broadcast", tags=["broadcast"])


# ---- Health ----
@app.get("/health")
def health():
    return {"ok": True}


# ---- Static frontend (раздаётся отдельным контейнером в docker-compose,
#       но оставим опциональное монтирование если FRONTEND_DIR задан) ----
FRONTEND_DIR = os.getenv("FRONTEND_DIR")
if FRONTEND_DIR and os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
