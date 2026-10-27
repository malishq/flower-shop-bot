from pathlib import Path

import pytest

from bot.db import Database
from bot.services import statuses

CATALOG = Path(__file__).resolve().parent.parent / "data" / "catalog.json"


@pytest.fixture
async def db(tmp_path):
    database = Database(tmp_path / "test.db")
    await database.connect()
    await database.init()
    await database.seed_catalog(CATALOG)
    yield database
    await database.close()


def order_fields(user_id, total=540, status=statuses.NEW, created="2026-10-28 10:00:00"):
    return {
        "user_id": user_id, "status": status, "name": "Никита", "phone": "+79991234567",
        "delivery_type": "delivery", "address": "ул. Садовая, 12", "delivery_date": "2026-10-29",
        "delivery_slot": "13:00–16:00", "comment": "", "payment": "cash", "promo_code": None,
        "subtotal": total - 350, "discount": 0, "delivery_price": 350, "total": total,
        "created_at": created, "updated_at": created,
    }


async def test_seed_is_idempotent_and_keeps_stock_flag(db):
    products = await db.list_products()
    assert len(products) == 15 and len(await db.list_categories()) == 4
    await db.set_product_active(1, False)
    await db.seed_catalog(CATALOG)
    assert (await db.get_product(1))["is_active"] == 0
    assert len(await db.list_products("bouquets")) == 4


async def test_cart_operations(db):
    await db.upsert_user(7, "Ник", "nick", "2026-10-28 10:00:00")
    assert await db.add_to_cart(7, 1, 2, max_qty=20) == 2
    assert await db.add_to_cart(7, 1, 30, max_qty=20) == 20
    await db.set_cart_qty(7, 13, 1)
    assert await db.cart_count(7) == 21
    await db.set_cart_qty(7, 1, 0)
    assert [line.product_id for line in await db.get_cart(7)] == [13]
    await db.set_product_active(13, False)
    assert await db.get_cart(7) == [] and await db.cart_count(7) == 0


async def test_order_numbers_start_from_1001_and_cart_is_cleared(db):
    await db.upsert_user(7, "Ник", None, "2026-10-28 10:00:00")
    await db.set_user_promo(7, "FLORA10")
    await db.add_to_cart(7, 13, 1, 20)
    lines = await db.get_cart(7)
    order_id = await db.create_order(order_fields(7), lines)
    assert order_id == 1001
    assert await db.cart_count(7) == 0 and await db.get_user_promo(7) is None
    assert (await db.get_order_lines(order_id))[0].title == "Открытка ручной работы"
    assert [o["id"] for o in await db.list_user_orders(7)] == [1001]


async def test_statuses_and_stats(db):
    first = await db.create_order(order_fields(7, total=1000), [])
    second = await db.create_order(order_fields(8, total=2000, created="2026-10-20 10:00:00"), [])
    third = await db.create_order(order_fields(9, total=4000), [])
    await db.set_order_status(third, statuses.CANCELLED, "2026-10-28 11:00:00")
    await db.set_order_status(first, statuses.ACCEPTED, "2026-10-28 11:00:00")
    assert await db.stats_since("2026-10-28 00:00:00") == (1, 1000)
    assert await db.stats_since("2026-10-01 00:00:00") == (2, 3000)
    assert [o["id"] for o in await db.list_active_orders()] == [second, first]
    assert [o["id"] for o in await db.list_active_orders(statuses.ACCEPTED)] == [first]
    assert await db.count_by_status() == {statuses.ACCEPTED: 1, statuses.NEW: 1, statuses.CANCELLED: 1}
