from __future__ import annotations

from html import escape
from typing import Any, Dict, Iterable, Mapping, Optional

from bot.services import statuses
from bot.services.cart import DELIVERY, CartLine, Promo, Totals
from bot.services.validation import format_phone


def money(value: int) -> str:
    return f"{int(value):,}".replace(",", " ") + " ₽"


def order_number(order_id: int) -> str:
    return f"№ {order_id}"


def plural(n: int, one: str, few: str, many: str) -> str:
    n = abs(n) % 100
    if 11 <= n <= 19:
        return many
    n %= 10
    if n == 1:
        return one
    if 2 <= n <= 4:
        return few
    return many


def lines_block(lines: Iterable[CartLine]) -> str:
    rows = []
    for i, line in enumerate(lines, 1):
        rows.append(f"{i}. {escape(line.title)} × {line.qty} — {money(line.total)}")
    return "\n".join(rows)


def totals_block(totals: Totals, promo: Optional[Promo], delivery_known: bool, delivery_price: int, free_from: int) -> str:
    rows = [f"Товары: {money(totals.subtotal)}"]
    if promo is not None:
        if totals.discount > 0:
            rows.append(f"Промокод {escape(promo.code)}: −{money(totals.discount)}")
        else:
            rows.append(f"Промокод {escape(promo.code)} сработает от {money(promo.min_total)}")
    if delivery_known:
        rows.append("Доставка: бесплатно" if totals.delivery == 0 else f"Доставка: {money(totals.delivery)}")
    else:
        hint = f"{money(delivery_price)}, бесплатно от {money(free_from)}" if free_from > 0 else money(delivery_price)
        rows.append(f"Доставка считается при оформлении ({hint}), самовывоз бесплатно")
    rows.append(f"<b>Итого: {money(totals.total)}</b>")
    return "\n".join(rows)


def cart_text(lines: Iterable[CartLine], totals: Totals, promo: Optional[Promo], delivery_price: int, free_from: int) -> str:
    items = list(lines)
    if not items:
        return "<b>Корзина</b>\n\nПока пусто. Загляните в каталог, там красиво."
    return "<b>Корзина</b>\n\n" + lines_block(items) + "\n\n" + totals_block(totals, promo, False, delivery_price, free_from)


def delivery_block(order: Mapping[str, Any], shop_address: str) -> str:
    when = f"{order['delivery_date_text']}, {order['delivery_slot']}"
    if order["delivery_type"] == DELIVERY:
        return f"Доставка: {escape(order['address'])}\nКогда: {when}"
    return f"Самовывоз: {escape(shop_address)}\nКогда: {when}"


def payment_title(payment: str) -> str:
    return "при получении" if payment == "cash" else "переводом"


def order_summary(order: Mapping[str, Any], lines: Iterable[CartLine], promo_code: Optional[str], shop_address: str) -> str:
    items = list(lines)
    rows = [lines_block(items), ""]
    rows.append(f"Товары: {money(order['subtotal'])}")
    if order["discount"]:
        rows.append(f"Промокод {escape(promo_code or '')}: −{money(order['discount'])}")
    if order["delivery_type"] == DELIVERY:
        rows.append("Доставка: бесплатно" if order["delivery_price"] == 0 else f"Доставка: {money(order['delivery_price'])}")
    rows.append(f"<b>Итого: {money(order['total'])}</b>")
    rows.append("")
    rows.append(f"Получатель: {escape(order['name'])}, {format_phone(order['phone'])}")
    rows.append(delivery_block(order, shop_address))
    rows.append(f"Оплата: {payment_title(order['payment'])}")
    if order.get("comment"):
        rows.append(f"Комментарий: {escape(order['comment'])}")
    return "\n".join(rows)


def order_text_for_customer(order: Mapping[str, Any], lines: Iterable[CartLine], shop_address: str) -> str:
    status = statuses.title(order["status"], order["delivery_type"])
    head = f"<b>Заказ {order_number(order['id'])}</b> · {statuses.ICONS[order['status']]} {status}\n{order['created_at_text']}\n\n"
    return head + order_summary(order, lines, order.get("promo_code"), shop_address)


def order_text_for_admin(order: Mapping[str, Any], lines: Iterable[CartLine], shop_address: str, user: Optional[Mapping[str, Any]] = None) -> str:
    status = statuses.title(order["status"], order["delivery_type"])
    head = f"{statuses.ICONS[order['status']]} <b>Заказ {order_number(order['id'])}</b> · {status}\n{order['created_at_text']}\n"
    who = ""
    if user:
        parts = [f"id {user['id']}"]
        if user.get("username"):
            parts.append("@" + escape(str(user["username"])))
        who = "Клиент: " + ", ".join(parts) + "\n"
    return head + who + "\n" + order_summary(order, lines, order.get("promo_code"), shop_address)


def order_short(order: Mapping[str, Any]) -> str:
    icon = statuses.ICONS[order["status"]]
    return f"{icon} {order_number(order['id'])} · {order['created_at_short']} · {money(order['total'])}"


def payment_instructions(order: Mapping[str, Any], transfer_details: str) -> str:
    if order["payment"] == "cash":
        if order["delivery_type"] == DELIVERY:
            return "Оплата при получении: наличными или картой курьеру."
        return "Оплата при получении в магазине: наличными или картой."
    return f"Оплата {transfer_details} Сумма: {money(order['total'])}, заказ {order_number(order['id'])}."


def order_view(row: Mapping[str, Any]) -> Dict[str, Any]:
    from datetime import date, datetime

    from bot.services.delivery import MONTHS_FULL, day_full

    order = dict(row)
    try:
        order["delivery_date_text"] = day_full(date.fromisoformat(order["delivery_date"]))
    except (ValueError, TypeError):
        order["delivery_date_text"] = str(order.get("delivery_date", ""))
    try:
        created = datetime.strptime(order["created_at"], "%Y-%m-%d %H:%M:%S")
        order["created_at_text"] = f"{created.day} {MONTHS_FULL[created.month - 1]}, {created.strftime('%H:%M')}"
        order["created_at_short"] = created.strftime("%d.%m")
    except (ValueError, TypeError):
        order["created_at_text"] = str(order.get("created_at", ""))
        order["created_at_short"] = order["created_at_text"]
    return order
