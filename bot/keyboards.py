from __future__ import annotations

from datetime import date
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Tuple

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from bot.services import statuses
from bot.services.cart import DELIVERY, PICKUP, CartLine
from bot.services.delivery import day_label, slot_label
from bot.services.format import money, order_short

BTN_CATALOG = "🌸 Каталог"
BTN_CART = "🛒 Корзина"
BTN_ORDERS = "📦 Мои заказы"
BTN_ABOUT = "ℹ️ О магазине"
BTN_HELP = "❓ Помощь"
BTN_CANCEL = "Отмена"
BTN_SHARE_PHONE = "📱 Отправить мой номер"

MENU_BUTTONS = (BTN_CATALOG, BTN_CART, BTN_ORDERS, BTN_ABOUT, BTN_HELP)


class CatalogCb(CallbackData, prefix="cat"):
    action: str
    slug: str = ""


class CardCb(CallbackData, prefix="card"):
    action: str
    slug: str
    index: int
    qty: int


class CartCb(CallbackData, prefix="cart"):
    action: str
    product_id: int = 0


class CheckoutCb(CallbackData, prefix="co"):
    step: str
    value: str = ""


class OrdersCb(CallbackData, prefix="ord"):
    action: str
    order_id: int = 0


class AdminCb(CallbackData, prefix="adm"):
    action: str
    order_id: int = 0
    value: str = ""


class StockCb(CallbackData, prefix="stk"):
    action: str
    slug: str = ""
    product_id: int = 0


def btn(text: str, data: CallbackData) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data.pack())


def markup(rows: Iterable[Iterable[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(row) for row in rows])


def chunks(items: Sequence[InlineKeyboardButton], size: int) -> List[List[InlineKeyboardButton]]:
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_CATALOG), KeyboardButton(text=BTN_CART)],
            [KeyboardButton(text=BTN_ORDERS), KeyboardButton(text=BTN_ABOUT)],
            [KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел",
    )


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_SHARE_PHONE, request_contact=True)], [KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="+7 999 123-45-67",
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True)


def cancel_checkout() -> InlineKeyboardButton:
    return btn("Отменить оформление", CheckoutCb(step="cancel"))


def _cart_label(count: int) -> str:
    return f"🛒 Корзина ({count})" if count else "🛒 Корзина"


def catalog_menu(categories: Iterable[Mapping[str, Any]], cart_count: int) -> InlineKeyboardMarkup:
    rows = [[btn(c["title"], CatalogCb(action="open", slug=c["slug"]))] for c in categories]
    rows.append([btn(_cart_label(cart_count), CartCb(action="open"))])
    return markup(rows)


def product_card(slug: str, index: int, total: int, price: int, qty: int, cart_count: int) -> InlineKeyboardMarkup:
    prev_index = (index - 1) % total
    next_index = (index + 1) % total
    return markup(
        [
            [
                btn("−", CardCb(action="dec", slug=slug, index=index, qty=qty)),
                btn(f"{qty} шт.", CardCb(action="noop", slug=slug, index=index, qty=qty)),
                btn("+", CardCb(action="inc", slug=slug, index=index, qty=qty)),
            ],
            [btn(f"В корзину · {money(price * qty)}", CardCb(action="add", slug=slug, index=index, qty=qty))],
            [
                btn("◀", CardCb(action="show", slug=slug, index=prev_index, qty=1)),
                btn(f"{index + 1} / {total}", CardCb(action="noop", slug=slug, index=index, qty=qty)),
                btn("▶", CardCb(action="show", slug=slug, index=next_index, qty=1)),
            ],
            [btn("К категориям", CatalogCb(action="menu")), btn(_cart_label(cart_count), CartCb(action="open"))],
        ]
    )


def _short(title: str, limit: int = 22) -> str:
    return title if len(title) <= limit else title[: limit - 1].rstrip() + "…"


def cart_keyboard(lines: Sequence[CartLine], promo_code: Optional[str]) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for line in lines:
        rows.append(
            [
                btn("−", CartCb(action="dec", product_id=line.product_id)),
                btn(f"{_short(line.title)} × {line.qty}", CartCb(action="noop", product_id=line.product_id)),
                btn("+", CartCb(action="inc", product_id=line.product_id)),
                btn("✕", CartCb(action="del", product_id=line.product_id)),
            ]
        )
    if not lines:
        rows.append([btn("В каталог", CatalogCb(action="send"))])
        return markup(rows)
    if promo_code:
        rows.append([btn(f"Убрать промокод {promo_code}", CartCb(action="promo_del"))])
    else:
        rows.append([btn("Ввести промокод", CartCb(action="promo"))])
    rows.append([btn("Оформить заказ", CheckoutCb(step="start"))])
    rows.append([btn("Очистить", CartCb(action="clear")), btn("В каталог", CatalogCb(action="send"))])
    return markup(rows)


def promo_cancel() -> InlineKeyboardMarkup:
    return markup([[btn("Отмена", CartCb(action="promo_cancel"))]])


def checkout_cancel() -> InlineKeyboardMarkup:
    return markup([[cancel_checkout()]])


def checkout_name(suggestion: Optional[str]) -> InlineKeyboardMarkup:
    rows = []
    if suggestion:
        rows.append([btn(f"Я — {suggestion}", CheckoutCb(step="name_use"))])
    rows.append([cancel_checkout()])
    return markup(rows)


def checkout_delivery(delivery_price: int, qualifies: bool) -> InlineKeyboardMarkup:
    label = "Доставка курьером · бесплатно" if qualifies else f"Доставка курьером · {money(delivery_price)}"
    return markup(
        [
            [btn(label, CheckoutCb(step="delivery", value=DELIVERY))],
            [btn("Самовывоз · бесплатно", CheckoutCb(step="delivery", value=PICKUP))],
            [cancel_checkout()],
        ]
    )


def checkout_dates(days: Sequence[date], today: date) -> InlineKeyboardMarkup:
    buttons = [btn(day_label(day, today), CheckoutCb(step="date", value=day.isoformat())) for day in days]
    rows = chunks(buttons, 2)
    rows.append([cancel_checkout()])
    return markup(rows)


def checkout_slots(slots: Sequence[Tuple[Any, Any]]) -> InlineKeyboardMarkup:
    buttons = []
    for slot in slots:
        value = f"{slot[0].strftime('%H%M')}-{slot[1].strftime('%H%M')}"
        buttons.append(btn(slot_label(slot), CheckoutCb(step="slot", value=value)))
    rows = chunks(buttons, 2)
    rows.append([btn("Другая дата", CheckoutCb(step="back_date")), cancel_checkout()])
    return markup(rows)


def checkout_comment() -> InlineKeyboardMarkup:
    return markup([[btn("Без комментария", CheckoutCb(step="comment_skip"))], [cancel_checkout()]])


def checkout_payment() -> InlineKeyboardMarkup:
    return markup(
        [
            [btn("При получении", CheckoutCb(step="payment", value="cash")), btn("Переводом", CheckoutCb(step="payment", value="transfer"))],
            [cancel_checkout()],
        ]
    )


def checkout_confirm() -> InlineKeyboardMarkup:
    return markup(
        [
            [btn("Подтвердить заказ", CheckoutCb(step="confirm"))],
            [btn("Заполнить заново", CheckoutCb(step="restart"))],
            [cancel_checkout()],
        ]
    )


def after_order(order_id: int) -> InlineKeyboardMarkup:
    return markup([[btn("Посмотреть заказ", OrdersCb(action="open", order_id=order_id))]])


def orders_list(orders: Sequence[Mapping[str, Any]]) -> InlineKeyboardMarkup:
    return markup([[btn(order_short(o), OrdersCb(action="show", order_id=o["id"]))] for o in orders])


def order_details(order_id: int) -> InlineKeyboardMarkup:
    return markup([[btn("Повторить заказ", OrdersCb(action="repeat", order_id=order_id))], [btn("К списку", OrdersCb(action="list"))]])


def admin_order(order: Mapping[str, Any], back_filter: str = "") -> InlineKeyboardMarkup:
    buttons = []
    for status in statuses.next_statuses(order["status"], order["delivery_type"]):
        text = f"{statuses.ICONS[status]} {statuses.action_title(status, order['delivery_type'])}"
        buttons.append(btn(text, AdminCb(action="status", order_id=order["id"], value=status)))
    rows = chunks(buttons, 2)
    rows.append([btn("К списку заказов", AdminCb(action="list", value=back_filter))])
    return markup(rows)


ADMIN_FILTERS: Tuple[Tuple[str, str], ...] = (
    ("", "Все"),
    (statuses.NEW, "Новые"),
    (statuses.ACCEPTED, "Принятые"),
    (statuses.ASSEMBLED, "Собранные"),
    (statuses.DELIVERING, "В пути"),
)


def admin_orders(orders: Sequence[Mapping[str, Any]], current: str) -> InlineKeyboardMarkup:
    filters = [btn(f"• {title}" if value == current else title, AdminCb(action="list", value=value)) for value, title in ADMIN_FILTERS]
    rows = [filters[:3], filters[3:]]
    for order in orders:
        rows.append([btn(order_short(order), AdminCb(action="show", order_id=order["id"], value=current))])
    return markup(rows)


def stock_keyboard(categories: Sequence[Mapping[str, Any]], products: Sequence[Mapping[str, Any]], current: str) -> InlineKeyboardMarkup:
    tabs = [btn(f"• {c['title']}" if c["slug"] == current else c["title"], StockCb(action="cat", slug=c["slug"])) for c in categories]
    rows = chunks(tabs, 2)
    for product in products:
        mark = "✅" if product["is_active"] else "⛔"
        rows.append([btn(f"{mark} {product['title']} · {money(product['price'])}", StockCb(action="toggle", slug=current, product_id=product["id"]))])
    return markup(rows)
