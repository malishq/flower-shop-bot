from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import aiosqlite

from bot.services import statuses
from bot.services.cart import CartLine

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    first_name TEXT,
    username TEXT,
    promo_code TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS categories (
    slug TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    sort INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    category TEXT NOT NULL REFERENCES categories(slug),
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price INTEGER NOT NULL,
    image TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    sort INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS cart_items (
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty INTEGER NOT NULL,
    PRIMARY KEY (user_id, product_id)
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    delivery_type TEXT NOT NULL,
    address TEXT NOT NULL DEFAULT '',
    delivery_date TEXT NOT NULL,
    delivery_slot TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    payment TEXT NOT NULL,
    promo_code TEXT,
    subtotal INTEGER NOT NULL,
    discount INTEGER NOT NULL DEFAULT 0,
    delivery_price INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    price INTEGER NOT NULL,
    qty INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
"""

FIRST_ORDER_NUMBER = 1000


class Database:
    def __init__(self, path: Path):
        self.path = path
        self._conn: Optional[aiosqlite.Connection] = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("База данных не подключена")
        return self._conn

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON")
        await self._conn.execute("PRAGMA journal_mode = WAL")

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def init(self) -> None:
        await self.conn.executescript(SCHEMA)
        await self.conn.execute(
            "INSERT INTO sqlite_sequence(name, seq) SELECT 'orders', ? "
            "WHERE NOT EXISTS (SELECT 1 FROM sqlite_sequence WHERE name = 'orders')",
            (FIRST_ORDER_NUMBER,),
        )
        await self.conn.commit()

    async def seed_catalog(self, path: Path) -> int:
        data = json.loads(path.read_text(encoding="utf-8"))
        for category in data["categories"]:
            await self.conn.execute(
                "INSERT INTO categories(slug, title, sort) VALUES (?, ?, ?) "
                "ON CONFLICT(slug) DO UPDATE SET title = excluded.title, sort = excluded.sort",
                (category["slug"], category["title"], category.get("sort", 0)),
            )
        for product in data["products"]:
            image = product.get("image") or f"{product['slug']}.png"
            await self.conn.execute(
                "INSERT INTO products(id, category, slug, title, description, price, image, sort) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET category = excluded.category, slug = excluded.slug, "
                "title = excluded.title, description = excluded.description, price = excluded.price, "
                "image = excluded.image, sort = excluded.sort",
                (
                    product["id"], product["category"], product["slug"], product["title"],
                    product.get("description", ""), product["price"], image, product.get("sort", 0),
                ),
            )
        await self.conn.commit()
        return len(data["products"])

    async def upsert_user(self, user_id: int, first_name: str, username: Optional[str], now: str) -> None:
        await self.conn.execute(
            "INSERT INTO users(id, first_name, username, created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET first_name = excluded.first_name, username = excluded.username",
            (user_id, first_name, username, now),
        )
        await self.conn.commit()

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        async with self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def set_user_promo(self, user_id: int, code: Optional[str]) -> None:
        await self.conn.execute("UPDATE users SET promo_code = ? WHERE id = ?", (code, user_id))
        await self.conn.commit()

    async def get_user_promo(self, user_id: int) -> Optional[str]:
        user = await self.get_user(user_id)
        return user["promo_code"] if user else None

    async def list_categories(self) -> List[Dict[str, Any]]:
        async with self.conn.execute("SELECT * FROM categories ORDER BY sort, title") as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def get_category(self, slug: str) -> Optional[Dict[str, Any]]:
        async with self.conn.execute("SELECT * FROM categories WHERE slug = ?", (slug,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def list_products(self, category: Optional[str] = None, only_active: bool = True) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM products"
        where, params = [], []
        if category:
            where.append("category = ?")
            params.append(category)
        if only_active:
            where.append("is_active = 1")
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY sort, id"
        async with self.conn.execute(sql, params) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def get_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        async with self.conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def set_product_active(self, product_id: int, active: bool) -> None:
        await self.conn.execute("UPDATE products SET is_active = ? WHERE id = ?", (1 if active else 0, product_id))
        await self.conn.commit()

    async def get_cart(self, user_id: int) -> List[CartLine]:
        await self.conn.execute(
            "DELETE FROM cart_items WHERE user_id = ? AND product_id IN (SELECT id FROM products WHERE is_active = 0)",
            (user_id,),
        )
        sql = (
            "SELECT c.product_id, p.title, p.price, c.qty FROM cart_items c "
            "JOIN products p ON p.id = c.product_id WHERE c.user_id = ? ORDER BY p.sort, p.id"
        )
        async with self.conn.execute(sql, (user_id,)) as cur:
            rows = await cur.fetchall()
        return [CartLine(product_id=r["product_id"], title=r["title"], price=r["price"], qty=r["qty"]) for r in rows]

    async def cart_count(self, user_id: int) -> int:
        async with self.conn.execute(
            "SELECT COALESCE(SUM(c.qty), 0) FROM cart_items c JOIN products p ON p.id = c.product_id "
            "WHERE c.user_id = ? AND p.is_active = 1",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def add_to_cart(self, user_id: int, product_id: int, qty: int, max_qty: int) -> int:
        async with self.conn.execute(
            "SELECT qty FROM cart_items WHERE user_id = ? AND product_id = ?", (user_id, product_id)
        ) as cur:
            row = await cur.fetchone()
        current = row["qty"] if row else 0
        new_qty = min(max_qty, current + qty)
        await self.set_cart_qty(user_id, product_id, new_qty)
        return new_qty

    async def set_cart_qty(self, user_id: int, product_id: int, qty: int) -> None:
        if qty <= 0:
            await self.conn.execute(
                "DELETE FROM cart_items WHERE user_id = ? AND product_id = ?", (user_id, product_id)
            )
        else:
            await self.conn.execute(
                "INSERT INTO cart_items(user_id, product_id, qty) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, product_id) DO UPDATE SET qty = excluded.qty",
                (user_id, product_id, qty),
            )
        await self.conn.commit()

    async def get_cart_qty(self, user_id: int, product_id: int) -> int:
        async with self.conn.execute(
            "SELECT qty FROM cart_items WHERE user_id = ? AND product_id = ?", (user_id, product_id)
        ) as cur:
            row = await cur.fetchone()
        return row["qty"] if row else 0

    async def clear_cart(self, user_id: int) -> None:
        await self.conn.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
        await self.conn.execute("UPDATE users SET promo_code = NULL WHERE id = ?", (user_id,))
        await self.conn.commit()

    async def create_order(self, fields: Dict[str, Any], lines: Iterable[CartLine]) -> int:
        columns = list(fields.keys())
        placeholders = ", ".join("?" for _ in columns)
        cur = await self.conn.execute(
            f"INSERT INTO orders({', '.join(columns)}) VALUES ({placeholders})",
            [fields[c] for c in columns],
        )
        order_id = cur.lastrowid
        await self.conn.executemany(
            "INSERT INTO order_items(order_id, product_id, title, price, qty) VALUES (?, ?, ?, ?, ?)",
            [(order_id, line.product_id, line.title, line.price, line.qty) for line in lines],
        )
        await self.conn.execute("DELETE FROM cart_items WHERE user_id = ?", (fields["user_id"],))
        await self.conn.execute("UPDATE users SET promo_code = NULL WHERE id = ?", (fields["user_id"],))
        await self.conn.commit()
        return int(order_id)

    async def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        async with self.conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def get_order_lines(self, order_id: int) -> List[CartLine]:
        async with self.conn.execute(
            "SELECT product_id, title, price, qty FROM order_items WHERE order_id = ? ORDER BY id", (order_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [CartLine(product_id=r["product_id"], title=r["title"], price=r["price"], qty=r["qty"]) for r in rows]

    async def list_user_orders(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        async with self.conn.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def list_active_orders(self, status: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
        if status:
            sql, params = "SELECT * FROM orders WHERE status = ? ORDER BY id DESC LIMIT ?", (status, limit)
        else:
            marks = ", ".join("?" for _ in statuses.ACTIVE)
            sql = f"SELECT * FROM orders WHERE status IN ({marks}) ORDER BY id DESC LIMIT ?"
            params = (*statuses.ACTIVE, limit)
        async with self.conn.execute(sql, params) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def set_order_status(self, order_id: int, status: str, now: str) -> None:
        await self.conn.execute(
            "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?", (status, now, order_id)
        )
        await self.conn.commit()

    async def stats_since(self, since: str) -> Tuple[int, int]:
        async with self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(total), 0) FROM orders WHERE created_at >= ? AND status != ?",
            (since, statuses.CANCELLED),
        ) as cur:
            row = await cur.fetchone()
        return int(row[0]), int(row[1])

    async def count_by_status(self) -> Dict[str, int]:
        async with self.conn.execute("SELECT status, COUNT(*) AS n FROM orders GROUP BY status") as cur:
            rows = await cur.fetchall()
        return {r["status"]: int(r["n"]) for r in rows}
