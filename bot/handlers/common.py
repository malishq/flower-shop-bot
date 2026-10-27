from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot import keyboards as kb
from bot import texts, views
from bot.config import Settings
from bot.db import Database

router = Router(name="common")


async def reset_state(state: FSMContext) -> bool:
    current = await state.get_state()
    await state.clear()
    return bool(current and current.startswith("Checkout"))


async def note_cancelled(message: Message, cancelled: bool) -> None:
    if cancelled:
        await message.answer("Оформление заказа прервано. Корзина сохранена.", reply_markup=kb.main_menu())


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db: Database, settings: Settings) -> None:
    await reset_state(state)
    user = message.from_user
    await db.upsert_user(user.id, user.first_name or "", user.username, settings.now().strftime("%Y-%m-%d %H:%M:%S"))
    await message.answer(texts.greeting(settings, user.first_name or ""), reply_markup=kb.main_menu())


@router.message(Command("help"))
@router.message(F.text == kb.BTN_HELP)
async def cmd_help(message: Message, state: FSMContext, settings: Settings) -> None:
    await note_cancelled(message, await reset_state(state))
    await message.answer(texts.help_text(settings, settings.is_admin(message.from_user.id)), reply_markup=kb.main_menu())


@router.message(F.text == kb.BTN_ABOUT)
async def show_about(message: Message, state: FSMContext, settings: Settings) -> None:
    await note_cancelled(message, await reset_state(state))
    await message.answer(texts.about(settings), reply_markup=kb.main_menu())


@router.message(Command("catalog"))
@router.message(F.text == kb.BTN_CATALOG)
async def open_catalog(message: Message, state: FSMContext, db: Database, settings: Settings) -> None:
    await note_cancelled(message, await reset_state(state))
    await views.send_catalog(message, db, settings, message.from_user.id)


@router.message(Command("cart"))
@router.message(F.text == kb.BTN_CART)
async def open_cart(message: Message, state: FSMContext, db: Database, settings: Settings, promo_codes: dict) -> None:
    await note_cancelled(message, await reset_state(state))
    await views.send_cart(message, db, settings, promo_codes, message.from_user.id)
