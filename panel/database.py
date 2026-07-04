import os
import asyncio
import asyncpg

_pool: asyncpg.Pool | None = None
_pool_lock = asyncio.Lock()


def _dsn() -> str:
    return (
        f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ.get('POSTGRES_HOST','postgres')}:{os.environ.get('POSTGRES_PORT','5432')}"
        f"/{os.environ.get('POSTGRES_DB','f2m_platform')}"
    )


async def init_pool():
    global _pool
    async with _pool_lock:
        if _pool is None:
            _pool = await asyncpg.create_pool(_dsn(), min_size=2, max_size=10)
            await _ensure_admin_schema(_pool)


async def close_pool():
    global _pool
    async with _pool_lock:
        if _pool is not None:
            await _pool.close()
            _pool = None


async def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized -- check app startup sequence")
    return _pool


async def _ensure_admin_schema(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS menu_tag_overrides (
                dish_id BIGINT NOT NULL,
                tag TEXT NOT NULL,
                action TEXT NOT NULL CHECK (action IN ('add', 'remove')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (dish_id, tag)
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_rules (
                id BIGSERIAL PRIMARY KEY,
                rule_type TEXT NOT NULL DEFAULT 'restaurant',
                rule_text TEXT NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS iiko_keys (
                id BIGSERIAL PRIMARY KEY,
                restaurant_name TEXT NOT NULL UNIQUE,
                api_key TEXT NOT NULL,
                organization_id TEXT,
                terminal_group_id TEXT,
                client_secret TEXT,
                app_id TEXT,
                owner TEXT NOT NULL DEFAULT 'client',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
