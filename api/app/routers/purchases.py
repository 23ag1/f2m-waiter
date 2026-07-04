import asyncio
import json
import logging

from app.integrations.pb_client import PremiumBonusClient

logger = logging.getLogger("purchases_sync")


def init_purchases_table(db_pool):
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS profile_purchases (
                    purchase_id TEXT PRIMARY KEY,
                    external_id TEXT,
                    phone TEXT NOT NULL,
                    purchase_date TIMESTAMPTZ,
                    purchase_amount NUMERIC DEFAULT 0,
                    payment_amount NUMERIC DEFAULT 0,
                    bonus_write_on NUMERIC DEFAULT 0,
                    bonus_write_off NUMERIC DEFAULT 0,
                    status TEXT DEFAULT '',
                    sale_point_name TEXT DEFAULT '',
                    items JSONB DEFAULT '[]',
                    synced_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_pp_phone ON profile_purchases(phone)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_pp_phone_date ON profile_purchases(phone, purchase_date DESC)"
            )
        conn.commit()
    finally:
        db_pool.putconn(conn)


async def sync_purchases(phone: str, db_pool):
    await asyncio.sleep(20)
    try:
        pb = PremiumBonusClient()

        detail = await pb.get_buyer_info_detail(phone)
        purchases = detail.get("purchases") or []
        if not purchases:
            return

        all_ids = [p["id"] for p in purchases if p.get("id")]
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT purchase_id FROM profile_purchases WHERE purchase_id = ANY(%s)",
                    (all_ids,),
                )
                existing = {row[0] for row in cur.fetchall()}
        finally:
            db_pool.putconn(conn)

        new_purchases = [p for p in purchases if p.get("id") and p["id"] not in existing]
        if not new_purchases:
            logger.debug("no new purchases for %s", phone)
            return

        for p in new_purchases:
            purchase_id = p["id"]
            external_id = p.get("external_id") or ""

            items = []
            if external_id:
                info = await pb._post("purchase-info", {"external_purchase_id": external_id})
                if info.get("success"):
                    items = info.get("items") or []

            bonus_write_on = (
                float(p.get("bonus_accumulated_write_on") or 0)
                + float(p.get("bonus_present_write_on") or 0)
                + float(p.get("bonus_action_write_on") or 0)
            )
            bonus_write_off = (
                float(p.get("bonus_accumulated_write_off") or 0)
                + float(p.get("bonus_present_write_off") or 0)
                + float(p.get("bonus_action_write_off") or 0)
            )

            conn = db_pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO profile_purchases (
                            purchase_id, external_id, phone, purchase_date,
                            purchase_amount, payment_amount,
                            bonus_write_on, bonus_write_off,
                            status, sale_point_name, items, synced_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
                        ON CONFLICT (purchase_id) DO NOTHING
                        """,
                        (
                            purchase_id,
                            external_id or None,
                            phone,
                            p.get("date"),
                            float(p.get("purchase_amount") or 0),
                            float(p.get("payment_amount") or 0),
                            bonus_write_on,
                            bonus_write_off,
                            p.get("status") or "",
                            p.get("sale_point_name") or "",
                            json.dumps(items, ensure_ascii=False),
                        ),
                    )
                conn.commit()
                logger.info(
                    "saved purchase %s for %s: %d items",
                    purchase_id, phone, len(items),
                )
            except Exception as e:
                conn.rollback()
                logger.error("purchase DB error %s: %s", purchase_id, e)
            finally:
                db_pool.putconn(conn)

    except Exception as e:
        logger.error("sync_purchases failed for %s: %s", phone, e)
