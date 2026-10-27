from __future__ import annotations

import logging
from datetime import timedelta
from typing import Union

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, Message

from bot import keyboards as kb
from bot import views
from bot.config import Settings
from bot.db import Database
from bot.services import statuses
from bot.services.format import money, order_text_for_admin, order_view, plural

logger = logging.getLogger(__name__)
router = Router(name="admin")


class IsAdmin(BaseFilter):
    async def __call__(self, event: Union[Message, CallbackQuery], settings: Settings) -> bool:
        return event.from_user is not None and settings.is_admin(event.from_user.id)


router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


async def orders_payload(db: Database, status_filter: str):
    orders = [order_view(o) for o in await db.list_active_orders(status_filter or None)]
    title = dict(kb.ADMIN_FILTERS).get(status_filter, "Все")
    if orders:
        count = len(orders)
        text = f"<b>Активные заказы · {title}</b>\n{count} {plural(count, 'заказ', 'заказа', 'заказов')}. Нажмите, чтобы открыть."
    else:
        text = f"<b>Активные заказы · {title}</b>\nПока пусто."
    return text, kb.admin_orders(orders, status_filter)


async def order_payload(db: Database, settings: Settings, order_id: int, back_filter: str):
    order = await db.get_order(order_id)
    if order is None:
        return None
    order = order_view(order)
    lines = await db.get_order_lines(order_id)
    user = await db.get_user(order["user_id"])
    return order_text_for_admin(order, lines, settings.shop_address, user), kb.admin_order(order, back_filter)


@router.message(Command("orders"))
async def admin_orders(message: Message, db: Database) -> None:
    text, markup = await orders_payload(db, "")
    await message.answer(text, reply_markup=markup)


@router.callback_query(kb.AdminCb.filter(F.action == "list"))
async def admin_orders_filter(callback: CallbackQuery, callback_data: kb.AdminCb, db: Database) -> None:
    if isinstance(callback.message, Message):
        text, markup = await orders_payload(db, callback_data.value)
        await views.safe_edit_text(callback.message, text, markup)
    await callback.answer()


@router.callback_query(kb.AdminCb.filter(F.action == "show"))
async def admin_order_show(callback: CallbackQuery, callback_data: kb.AdminCb, db: Database, settings: Settings) -> None:
    payload = await order_payload(db, settings, callback_data.order_id, callback_data.value)
    if payload is None or not isinstance(callback.message, Message):
        await callback.answer("Заказ не найден", show_alert=True)
        return
    await views.safe_edit_text(callback.message, payload[0], payload[1])
    await callback.answer()


@router.callback_query(kb.AdminCb.filter(F.action == "status"))
async def admin_set_status(callback: CallbackQuery, callback_data: kb.AdminCb, db: Database, settings: Settings, bot: Bot) -> None:
    order = await db.get_order(callback_data.order_id)
    new_status = callback_data.value
    if order is None:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    if not statuses.can_transition(order["status"], new_status):
        await callback.answer(
            f"Сейчас заказ «{statuses.title(order['status'], order['delivery_type'])}», этот переход невозможен",
            show_alert=True,
        )
        payload = await order_payload(db, settings, order["id"], "")
        if payload and isinstance(callback.message, Message):
            await views.safe_edit_text(callback.message, payload[0], payload[1])
        return
    now = settings.now().strftime("%Y-%m-%d %H:%M:%S")
    await db.set_order_status(order["id"], new_status, now)
    text = statuses.customer_message(new_status, order["id"], order["delivery_type"], settings.shop_address, settings.shop_phone)
    try:
        await bot.send_message(order["user_id"], text)
    except Exception as error:
        logger.warning("Не удалось уведомить клиента %s о заказе %s: %s", order["user_id"], order["id"], error)
    payload = await order_payload(db, settings, order["id"], "")
    if payload and isinstance(callback.message, Message):
        await views.safe_edit_text(callback.message, payload[0], payload[1])
    await callback.answer(f"Статус: {statuses.title(new_status, order['delivery_type'])}")


@router.message(Command("stats"))
async def admin_stats(message: Message, db: Database, settings: Settings) -> None:
    now = settings.now()
    periods = (
        ("Сегодня", now.replace(hour=0, minute=0, second=0, microsecond=0)),
        ("7 дней", now - timedelta(days=7)),
        ("30 дней", now - timedelta(days=30)),
    )
    rows = ["<b>Статистика</b> (без отменённых)\n"]
    for title, since in periods:
        count, revenue = await db.stats_since(since.strftime("%Y-%m-%d %H:%M:%S"))
        rows.append(f"{title}: {count} {plural(count, 'заказ', 'заказа', 'заказов')}, {money(revenue)}")
    by_status = await db.count_by_status()
    active = [f"{statuses.ICONS[s]} {statuses.TITLES[s]}: {by_status.get(s, 0)}" for s in statuses.ACTIVE]
    rows.append("\nВ работе:\n" + "\n".join(active))
    rows.append(f"\nВсего завершено: {by_status.get(statuses.DONE, 0)}, отменено: {by_status.get(statuses.CANCELLED, 0)}")
    await message.answer("\n".join(rows))


async def stock_payload(db: Database, slug: str):
    categories = await db.list_categories()
    if not categories:
        return "Каталог пуст.", None
    if slug not in {c["slug"] for c in categories}:
        slug = categories[0]["slug"]
    products = await db.list_products(slug, only_active=False)
    text = "<b>Наличие товаров</b>\nНажмите на товар, чтобы скрыть его из каталога или вернуть."
    return text, kb.stock_keyboard(categories, products, slug)


@router.message(Command("stock"))
async def admin_stock(message: Message, db: Database) -> None:
    text, markup = await stock_payload(db, "")
    await message.answer(text, reply_markup=markup)


@router.callback_query(kb.StockCb.filter(F.action == "cat"))
async def admin_stock_category(callback: CallbackQuery, callback_data: kb.StockCb, db: Database) -> None:
    if isinstance(callback.message, Message):
        text, markup = await stock_payload(db, callback_data.slug)
        await views.safe_edit_text(callback.message, text, markup)
    await callback.answer()


@router.callback_query(kb.StockCb.filter(F.action == "toggle"))
async def admin_stock_toggle(callback: CallbackQuery, callback_data: kb.StockCb, db: Database) -> None:
    product = await db.get_product(callback_data.product_id)
    if product is None:
        await callback.answer("Товар не найден", show_alert=True)
        return
    active = not product["is_active"]
    await db.set_product_active(product["id"], active)
    if isinstance(callback.message, Message):
        text, markup = await stock_payload(db, callback_data.slug)
        await views.safe_edit_text(callback.message, text, markup)
    await callback.answer(f"{product['title']}: {'в каталоге' if active else 'скрыт'}")
