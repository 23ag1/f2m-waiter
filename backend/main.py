import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db_postgres import Database
from backend.api.endpoints import waiter as waiter_router

db = Database()

app = FastAPI(title="Food2Mood Waiter API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # token is passed in header, not cookie
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_database():
    return db

# Inject db instance into router module before including it
import backend.api.endpoints.waiter as _waiter_module
_waiter_module._db_instance = db

app.include_router(waiter_router.router, prefix="/api/v1/waiter", tags=["waiter"])

@app.get("/health")
def health():
    return {"status": "ok"}
