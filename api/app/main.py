import os
from psycopg2 import pool
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter
from app.routers import premium_bonus
from app.routers import coffeemania
from app.routers.loyalty import init_loyalty_table
from app.routers.purchases import init_purchases_table

app = FastAPI(title="Food2Mood Platform API")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    db_pool = pool.ThreadedConnectionPool(
        minconn=2,
        maxconn=10,
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ.get("POSTGRES_PORT", 5432)),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    )
    app.state.db_pool = db_pool
    premium_bonus.init_db(db_pool)
    init_loyalty_table(db_pool)
    init_purchases_table(db_pool)
    coffeemania.init_coffeemania_tables(db_pool)


@app.on_event("shutdown")
def shutdown():
    app.state.db_pool.closeall()


app.include_router(premium_bonus.router, prefix="/api/v1/premium-bonus", tags=["premium-bonus"])
app.include_router(coffeemania.router, prefix="/api/coffeemania", tags=["coffeemania"])


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    return {"status": "ok"}
