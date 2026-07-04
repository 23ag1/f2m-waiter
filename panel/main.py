import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from database import init_pool, close_pool
from routers.restaurant_admin import router as admin_router

app = FastAPI(title="Food2Mood Admin Panel")

_ALLOWED_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS or ["*"],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["X-Admin-Key", "Content-Type"],
)

PANEL_HTML = Path(__file__).parent / "static" / "index.html"
_panel_html_cache: str | None = None


@app.on_event("startup")
async def startup():
    global _panel_html_cache
    if not os.getenv("ADMIN_API_KEY"):
        raise RuntimeError("ADMIN_API_KEY env var is required")
    _panel_html_cache = PANEL_HTML.read_text(encoding="utf-8")
    await init_pool()


@app.on_event("shutdown")
async def shutdown():
    await close_pool()


@app.get("/", response_class=HTMLResponse)
async def panel():
    return _panel_html_cache


@app.get("/health")
def health():
    return {"ok": True}


app.include_router(admin_router, prefix="/api/v1")
