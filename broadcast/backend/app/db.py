"""
Минимальный PostgreSQL wrapper. Эмулирует API, на который рассчитан broadcast_service:
  - db.connection.execute(sql, params) → cursor
  - cursor.fetchall() / fetchone() → строки с доступом по имени колонки (case-insensitive)
"""

import os
import re as _re
import threading

import psycopg2
from psycopg2 import pool
from psycopg2.extras import DictCursor


class CaseInsensitiveRow:
    """Доступ к колонкам по имени без учёта регистра."""

    def __init__(self, row):
        self._row = row
        self._lower_keys = {k.lower(): k for k in row.keys()}

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._row[key]
        if isinstance(key, str):
            k_low = key.lower()
            if k_low in self._lower_keys:
                return self._row[self._lower_keys[k_low]]
        return self._row[key]

    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, IndexError):
            return default

    def keys(self):
        return self._row.keys()

    def __len__(self):
        return len(self._row)

    def __iter__(self):
        return iter(self._row)


class CursorWrapper:
    """Обёртка курсора. Возвращает соединение в пул после fetchall/fetchone."""

    def __init__(self, cursor, conn=None, db_pool=None):
        self.cursor = cursor
        self._conn = conn
        self._pool = db_pool

    def _release(self):
        if self._conn is not None and self._pool is not None:
            try:
                self.cursor.close()
            except Exception:
                pass
            self._pool.putconn(self._conn)
            self._conn = None

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def execute(self, query, params=()):
        query = _re.sub(r"'[^']*'|(\?)", lambda m: "%s" if m.group(1) else m.group(0), query)
        self.cursor.execute(query, params)
        return self

    def fetchall(self):
        rows = self.cursor.fetchall() or []
        self._release()
        return [CaseInsensitiveRow(r) for r in rows]

    def fetchone(self):
        row = self.cursor.fetchone()
        self._release()
        return CaseInsensitiveRow(row) if row is not None else None

    def close(self):
        self._release()

    def __del__(self):
        self._release()


class ConnectionAdapter:
    """Пул psycopg2-соединений. Берёт соединение на запрос и сразу возвращает."""

    def __init__(self, host, port, user, password, dbname, minconn=2, maxconn=20):
        self._pool = pool.ThreadedConnectionPool(
            minconn, maxconn,
            host=host, port=port, user=user, password=password, dbname=dbname,
            cursor_factory=DictCursor,
        )

    def _get_conn(self):
        conn = self._pool.getconn()
        conn.autocommit = True
        return conn

    def cursor(self):
        conn = self._get_conn()
        return CursorWrapper(conn.cursor(), conn, self._pool)

    def execute(self, query, params=()):
        cur = self.cursor()
        try:
            cur.execute(query, params)
        except Exception:
            cur.close()
            raise
        return cur

    def commit(self):
        pass  # autocommit=True; explicit commit not needed

    def close(self):
        self._pool.closeall()


class Database:
    """Обёртка, повторяющая минимальный контракт из исходного проекта Food2Mood."""

    def __init__(self):
        self._connection = ConnectionAdapter(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            dbname=os.getenv("POSTGRES_DB", "f2m_platform"),
        )

    @property
    def connection(self):
        return self._connection

    def close(self):
        self._connection.close()
