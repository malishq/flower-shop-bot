from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot import keyboards as kb
from bot import views
from bot.config import Settings
from bot.db import Database
from bot.services.cart import change_qty

router = Router(name="catalog")


@router.callback_query(kb.CatalogCb.filter(F.action == "send"))
async def catalog_send(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    if isinstance(callback.message, Message):
        await views.send_catalog(callback.message, db, settings, callback.from_user.id)
    await callback.answer()


@router.callback_query(kb.CatalogCb.filter(F.action == "menu"))
async def catalog_menu(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    if isinstance(callback.message, Message):
        await views.edit_to_catalog(callback.message, db, settings, callback.from_user.id)
    await callback.answer()


@router.callback_query(kb.CatalogCb.filter(F.action == "open"))
async def catalog_open(callback: CallbackQuery, callback_data: kb.CatalogCb, db: Database, settings: Settings) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    shown = await views.edit_to_card(callback.message, db, settings, callback.from_user.id, callback_data.slug, 0)
    if not shown:
        await callback.answer("В этой категории пока пусто", show_alert=True)
        return
    await callback.answer()


@router.callback_query(kb.CardCb.filter(F.action == "show"))
async def card_show(callback: CallbackQuery, callback_data: kb.CardCb, db: Database, settings: Settings) -> None:
    if isinstance(callback.message, Message):
        shown = await views.edit_to_card(callback.message, db, settings, callback.from_user.id, callback_data.slug, callback_data.index)
        if not shown:
            await views.edit_to_catalog(callback.message, db, settings, callback.from_user.id)
    await callback.answer()


@router.callback_query(kb.CardCb.filter(F.action.in_({"inc", "dec"})))
async def card_qty(callback: CallbackQuery, callback_data: kb.CardCb, db: Database, settings: Settings) -> None:
    delta = 1 if callback_data.action == "inc" else -1
    qty = max(1, change_qty(callback_data.qty, delta, settings.max_qty))
    if qty == callback_data.qty:
        await callback.answer(f"Не больше {settings.max_qty} шт." if delta > 0 else "Минимум 1 шт.")
        return
    if isinstance(callback.message, Message):
        payload = await views.card_payload(db, settings, callback.from_user.id, callback_data.slug, callback_data.index, qty)
        if payload is not None:
            await views.safe_edit_markup(callback.message, payload[2])
    await callback.answer()


@router.callback_query(kb.CardCb.filter(F.action == "add"))
async def card_add(callback: CallbackQuery, callback_data: kb.CardCb, db: Database, settings: Settings) -> None:
    products = await db.list_products(callback_data.slug)
    if not products:
        await callback.answer("Товар уже недоступен", show_alert=True)
        return
    product = products[callback_data.index % len(products)]
    total_qty = await db.add_to_cart(callback.from_user.id, product["id"], callback_data.qty, settings.max_qty)
    if isinstance(callback.message, Message):
        await views.edit_to_card(callback.message, db, settings, callback.from_user.id, callback_data.slug, callback_data.index, 1)
    await callback.answer(f"В корзине: {product['title']} × {total_qty}")


@router.callback_query(kb.CardCb.filter(F.action == "noop"))
async def card_noop(callback: CallbackQuery) -> None:
    await callback.answer()
