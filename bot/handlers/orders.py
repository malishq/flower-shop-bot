from __future__ import annotations

from typing import Dict

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import keyboards as kb
from bot import views
from bot.config import Settings
from bot.db import Database
from bot.handlers.common import note_cancelled, reset_state
from bot.services.cart import Promo
from bot.services.format import order_text_for_customer, order_view

router = Router(name="orders")


async def orders_list_payload(db: Database, user_id: int):
    orders = [order_view(o) for o in await db.list_user_orders(user_id, limit=10)]
    if not orders:
        return "Заказов пока нет. Самое время выбрать букет.", kb.markup([[kb.btn("В каталог", kb.CatalogCb(action="send"))]])
    return "<b>Мои заказы</b>\nНажмите на заказ, чтобы посмотреть детали.", kb.orders_list(orders)


@router.message(Command("orders"))
@router.message(F.text == kb.BTN_ORDERS)
async def my_orders(message: Message, state: FSMContext, db: Database) -> None:
    await note_cancelled(message, await reset_state(state))
    text, markup = await orders_list_payload(db, message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(kb.OrdersCb.filter(F.action == "list"))
async def orders_back(callback: CallbackQuery, db: Database) -> None:
    if isinstance(callback.message, Message):
        text, markup = await orders_list_payload(db, callback.from_user.id)
        await views.safe_edit_text(callback.message, text, markup)
    await callback.answer()


@router.callback_query(kb.OrdersCb.filter(F.action.in_({"show", "open"})))
async def order_show(callback: CallbackQuery, callback_data: kb.OrdersCb, db: Database, settings: Settings) -> None:
    order = await db.get_order(callback_data.order_id)
    if order is None or order["user_id"] != callback.from_user.id or not isinstance(callback.message, Message):
        await callback.answer("Заказ не найден", show_alert=True)
        return
    lines = await db.get_order_lines(order["id"])
    text = order_text_for_customer(order_view(order), lines, settings.shop_address)
    if callback_data.action == "open":
        await callback.message.answer(text, reply_markup=kb.order_details(order["id"]))
    else:
        await views.safe_edit_text(callback.message, text, kb.order_details(order["id"]))
    await callback.answer()


@router.callback_query(kb.OrdersCb.filter(F.action == "repeat"))
async def order_repeat(callback: CallbackQuery, callback_data: kb.OrdersCb, db: Database, settings: Settings, promo_codes: Dict[str, Promo]) -> None:
    order = await db.get_order(callback_data.order_id)
    if order is None or order["user_id"] != callback.from_user.id:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    added, skipped = 0, []
    for line in await db.get_order_lines(order["id"]):
        product = await db.get_product(line.product_id)
        if product is None or not product["is_active"]:
            skipped.append(line.title)
            continue
        await db.add_to_cart(callback.from_user.id, line.product_id, line.qty, settings.max_qty)
        added += 1
    if not added:
        await callback.answer("Этих товаров сейчас нет в наличии", show_alert=True)
        return
    note = "Товары добавлены в корзину"
    if skipped:
        note += ". Нет в наличии: " + ", ".join(skipped)
    await callback.answer(note, show_alert=bool(skipped))
    if isinstance(callback.message, Message):
        await views.send_cart(callback.message, db, settings, promo_codes, callback.from_user.id)
