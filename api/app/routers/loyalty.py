import asyncio
import logging
from app.integrations.pb_sync import TasteProfileSync

logger = logging.getLogger("loyalty_sync")


def init_loyalty_table(db_pool):
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS profile_loyalty (
                    phone TEXT PRIMARY KEY,
                    pb_is_registered BOOLEAN DEFAULT FALSE,
                    pb_blocked BOOLEAN DEFAULT FALSE,
                    pb_balance NUMERIC DEFAULT 0,
                    pb_bonus_inactive NUMERIC DEFAULT 0,
                    pb_balance_accumulated NUMERIC DEFAULT 0,
                    pb_balance_present NUMERIC DEFAULT 0,
                    pb_card_number TEXT DEFAULT '',
                    pb_group_name TEXT DEFAULT '',
                    pb_client_id TEXT DEFAULT '',
                    pb_payments_amount NUMERIC DEFAULT 0,
                    pb_purchase_count INTEGER DEFAULT 0,
                    pb_last_purchase_at TEXT DEFAULT '',
                    synced_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        conn.commit()
    finally:
        db_pool.putconn(conn)


async def sync_loyalty(phone: str, db_pool):
    await asyncio.sleep(20)
    try:
        data = await TasteProfileSync().pull(phone)
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO profile_loyalty (
                        phone, pb_is_registered, pb_blocked, pb_balance,
                        pb_bonus_inactive, pb_balance_accumulated, pb_balance_present,
                        pb_card_number, pb_group_name, pb_client_id,
                        pb_payments_amount, pb_purchase_count, pb_last_purchase_at, synced_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (phone) DO UPDATE SET
                        pb_is_registered   = EXCLUDED.pb_is_registered,
                        pb_blocked         = EXCLUDED.pb_blocked,
                        pb_balance         = EXCLUDED.pb_balance,
                        pb_bonus_inactive  = EXCLUDED.pb_bonus_inactive,
                        pb_balance_accumulated = EXCLUDED.pb_balance_accumulated,
                        pb_balance_present = EXCLUDED.pb_balance_present,
                        pb_card_number     = EXCLUDED.pb_card_number,
                        pb_group_name      = EXCLUDED.pb_group_name,
                        pb_client_id       = EXCLUDED.pb_client_id,
                        pb_payments_amount = EXCLUDED.pb_payments_amount,
                        pb_purchase_count  = EXCLUDED.pb_purchase_count,
                        pb_last_purchase_at = EXCLUDED.pb_last_purchase_at,
                        synced_at          = NOW()
                """, (
                    phone,
                    data.get("pb_is_registered", False),
                    data.get("pb_blocked", False),
                    data.get("pb_balance", 0),
                    data.get("pb_bonus_inactive", 0),
                    data.get("pb_balance_accumulated", 0),
                    data.get("pb_balance_present", 0),
                    data.get("pb_card_number", ""),
                    data.get("pb_group_name", ""),
                    data.get("pb_client_id", ""),
                    data.get("pb_payments_amount", 0),
                    data.get("pb_purchase_count", 0),
                    data.get("pb_last_purchase_at", ""),
                ))
            conn.commit()
            logger.info("loyalty synced for %s: balance=%s group=%s", phone, data.get("pb_balance"), data.get("pb_group_name"))
        except Exception as e:
            conn.rollback()
            logger.error("loyalty DB error for %s: %s", phone, e)
        finally:
            db_pool.putconn(conn)
    except Exception as e:
        logger.error("loyalty sync failed for %s: %s", phone, e)
