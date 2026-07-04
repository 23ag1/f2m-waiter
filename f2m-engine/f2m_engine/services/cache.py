from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_MISS = object()


class RecommendationCache:
    """Thin Redis wrapper for recommendation results.

    Falls back to no-op if Redis is unavailable — engine keeps working, just slower.
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._client = None
        url = redis_url or os.getenv("REDIS_URL")
        if not url:
            logger.info("REDIS_URL not set — cache disabled")
            return
        try:
            import redis as _redis
            self._client = _redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
            self._client.ping()
            logger.info("Redis cache connected: %s", url)
        except Exception as exc:
            logger.warning("Redis unavailable, cache disabled: %s", exc)
            self._client = None

    # ── public ──────────────────────────────────────────────────────────

    def get(self, user_id: int) -> dict[str, Any] | None:
        if self._client is None:
            return None
        try:
            raw = self._client.get(self._key(user_id))
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.warning("cache.get failed: %s", exc)
            return None

    def set(self, user_id: int, data: dict[str, Any], ttl: int = 3600) -> None:
        if self._client is None:
            return
        try:
            self._client.setex(self._key(user_id), ttl, json.dumps(data, ensure_ascii=False))
        except Exception as exc:
            logger.warning("cache.set failed: %s", exc)

    def invalidate_user(self, user_id: int) -> None:
        """Call after a new event or questionnaire for this user."""
        if self._client is None:
            return
        try:
            self._client.delete(self._key(user_id))
        except Exception as exc:
            logger.warning("cache.invalidate_user failed: %s", exc)

    def invalidate_all(self) -> None:
        """Call after profile rebuild or settings change."""
        if self._client is None:
            return
        try:
            cursor = 0
            pattern = "recs:*"
            while True:
                cursor, keys = self._client.scan(cursor, match=pattern, count=200)
                if keys:
                    self._client.delete(*keys)
                if cursor == 0:
                    break
            logger.info("cache: invalidated all recs:* keys")
        except Exception as exc:
            logger.warning("cache.invalidate_all failed: %s", exc)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    # ── private ─────────────────────────────────────────────────────────

    @staticmethod
    def _key(user_id: int) -> str:
        return f"recs:{user_id}"
