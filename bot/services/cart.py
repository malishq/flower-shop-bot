from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

PERCENT = "percent"
FIXED = "fixed"
DELIVERY = "delivery"
PICKUP = "pickup"


@dataclass(frozen=True)
class CartLine:
    product_id: int
    title: str
    price: int
    qty: int

    @property
    def total(self) -> int:
        return self.price * self.qty


@dataclass(frozen=True)
class Promo:
    code: str
    kind: str
    value: int
    min_total: int = 0

    def describe(self) -> str:
        if self.kind == PERCENT:
            return f"скидка {self.value}%"
        return f"скидка {self.value} ₽"


@dataclass(frozen=True)
class Totals:
    subtotal: int
    discount: int
    delivery: int

    @property
    def total(self) -> int:
        return max(self.subtotal - self.discount, 0) + self.delivery


def parse_promo_codes(raw: str) -> Dict[str, Promo]:
    codes: Dict[str, Promo] = {}
    for chunk in raw.split(","):
        parts = [p.strip() for p in chunk.split(":")]
        if len(parts) < 2 or not parts[0] or not parts[1]:
            continue
        code = parts[0].upper()
        value_raw = parts[1]
        kind = PERCENT if value_raw.endswith("%") else FIXED
        try:
            value = int(value_raw.rstrip("%"))
            min_total = int(parts[2]) if len(parts) > 2 and parts[2] else 0
        except ValueError:
            continue
        if value <= 0 or (kind == PERCENT and value > 100):
            continue
        codes[code] = Promo(code=code, kind=kind, value=value, min_total=min_total)
    return codes


def find_promo(codes: Dict[str, Promo], text: str) -> Optional[Promo]:
    return codes.get(text.strip().upper())


def subtotal(lines: Iterable[CartLine]) -> int:
    return sum(line.total for line in lines)


def promo_discount(amount: int, promo: Optional[Promo]) -> int:
    if promo is None or amount <= 0 or amount < promo.min_total:
        return 0
    if promo.kind == PERCENT:
        discount = amount * promo.value // 100
    else:
        discount = promo.value
    return min(discount, amount)


def delivery_cost(delivery_type: str, amount: int, price: int, free_from: int) -> int:
    if delivery_type != DELIVERY:
        return 0
    if free_from > 0 and amount >= free_from:
        return 0
    return price


def calc_totals(
    lines: Iterable[CartLine],
    promo: Optional[Promo],
    delivery_type: str,
    delivery_price: int,
    free_delivery_from: int,
) -> Totals:
    items = list(lines)
    base = subtotal(items)
    discount = promo_discount(base, promo)
    delivery = delivery_cost(delivery_type, base - discount, delivery_price, free_delivery_from)
    return Totals(subtotal=base, discount=discount, delivery=delivery)


def change_qty(qty: int, delta: int, max_qty: int = 20) -> int:
    return max(0, min(max_qty, qty + delta))


def items_count(lines: Iterable[CartLine]) -> int:
    return sum(line.qty for line in lines)
