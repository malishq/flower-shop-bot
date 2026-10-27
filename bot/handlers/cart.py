from __future__ import annotations

from typing import Dict

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot import keyboards as kb
from bot import views
from bot.config import Settings
from bot.db import Database
from bot.services.cart import Promo, change_qty, find_promo

router = Router(name="cart")


class PromoState(StatesGroup):
    code = State()


@router.callback_query(kb.CartCb.filter(F.action == "open"))
async def cart_open(callback: CallbackQuery, db: Database, settings: Settings, promo_codes: Dict[str, Promo]) -> None:
    if isinstance(callback.message, Message):
        await views.send_cart(callback.message, db, settings, promo_codes, callback.from_user.id)
    await callback.answer()


@router.callback_query(kb.CartCb.filter(F.action.in_({"inc", "dec", "del"})))
async def cart_change(callback: CallbackQuery, callback_data: kb.CartCb, db: Database, settings: Settings, promo_codes: Dict[str, Promo]) -> None:
    user_id = callback.from_user.id
    current = await db.get_cart_qty(user_id, callback_data.product_id)
    if callback_data.action == "del":
        new_qty = 0
    else:
        new_qty = change_qty(current, 1 if callback_data.action == "inc" else -1, settings.max_qty)
    if new_qty == current and callback_data.action == "inc":
        await callback.answer(f"Не больше {settings.max_qty} шт.")
        return
    await db.set_cart_qty(user_id, callback_data.product_id, new_qty)
    if isinstance(callback.message, Message):
        await views.edit_cart(callback.message, db, settings, promo_codes, user_id)
    await callback.answer("Удалено" if new_qty == 0 else None)


@router.callback_query(kb.CartCb.filter(F.action == "clear"))
async def cart_clear(callback: CallbackQuery, db: Database, settings: Settings, promo_codes: Dict[str, Promo]) -> None:
    await db.clear_cart(callback.from_user.id)
    if isinstance(callback.message, Message):
        await views.edit_cart(callback.message, db, settings, promo_codes, callback.from_user.id)
    await callback.answer("Корзина очищена")


@router.callback_query(kb.CartCb.filter(F.action == "promo"))
async def promo_ask(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PromoState.code)
    if isinstance(callback.message, Message):
        prompt = await callback.message.answer("Введите промокод:", reply_markup=kb.promo_cancel())
        await state.update_data(promo_prompt_id=prompt.message_id)
    await callback.answer()


@router.callback_query(kb.CartCb.filter(F.action == "promo_cancel"))
async def promo_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        await views.safe_delete(callback.message)
    await callback.answer("Без промокода")


@router.message(PromoState.code, F.text)
async def promo_enter(message: Message, state: FSMContext, db: Database, settings: Settings, promo_codes: Dict[str, Promo]) -> None:
    promo = find_promo(promo_codes, message.text or "")
    if promo is None:
        await message.answer("Такого промокода нет. Проверьте написание и попробуйте ещё раз.", reply_markup=kb.promo_cancel())
        return
    await state.clear()
    await db.set_user_promo(message.from_user.id, promo.code)
    await message.answer(f"Промокод {promo.code} применён: {promo.describe()}.")
    await views.send_cart(message, db, settings, promo_codes, message.from_user.id)


@router.callback_query(kb.CartCb.filter(F.action == "promo_del"))
async def promo_delete(callback: CallbackQuery, db: Database, settings: Settings, promo_codes: Dict[str, Promo]) -> None:
    await db.set_user_promo(callback.from_user.id, None)
    if isinstance(callback.message, Message):
        await views.edit_cart(callback.message, db, settings, promo_codes, callback.from_user.id)
    await callback.answer("Промокод убран")


@router.callback_query(kb.CartCb.filter(F.action == "noop"))
async def cart_noop(callback: CallbackQuery) -> None:
    await callback.answer()
