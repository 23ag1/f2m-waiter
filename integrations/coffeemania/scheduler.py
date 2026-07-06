"""
Планировщик пуллера Кофемании.

Два независимых цикла:
  - меню (Dishes)       - MENU_INTERVAL_SEC     (по умолчанию 3600 = раз в час)
  - стоп-листы (Restrictions) - STOPLIST_INTERVAL_SEC (по умолчанию 900 = раз в 15 мин)

Оба джоба запускаются один раз на старте, дальше - по своим интервалам.
Ошибка одного пула не роняет процесс и не мешает другому.
"""
from __future__ import annotations

import logging
import os
import time

from puller import pull_menu, pull_stoplists

log = logging.getLogger("coffeemania_scheduler")

MENU_INTERVAL = int(os.getenv("MENU_INTERVAL_SEC", "3600"))
STOPLIST_INTERVAL = int(os.getenv("STOPLIST_INTERVAL_SEC", "900"))


def _safe(fn, name: str) -> None:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - процесс не должен падать из-за одного пула
        log.error("%s failed: %s", name, exc)


def main() -> None:
    log.info("puller start: menu every %ds, stoplists every %ds", MENU_INTERVAL, STOPLIST_INTERVAL)
    next_menu = 0.0
    next_stop = 0.0
    tick = max(5, min(30, STOPLIST_INTERVAL))
    while True:
        now = time.time()
        if now >= next_menu:
            _safe(pull_menu, "pull_menu")
            next_menu = time.time() + MENU_INTERVAL
        if now >= next_stop:
            _safe(pull_stoplists, "pull_stoplists")
            next_stop = time.time() + STOPLIST_INTERVAL
        time.sleep(tick)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    main()
