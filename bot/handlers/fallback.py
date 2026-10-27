from __future__ import annotations

from aiogram import Router
from aiogram.types import CallbackQuery, Message

from bot import keyboards as kb

router = Router(name="fallback")


@router.message()
async def unknown_message(message: Message) -> None:
    await message.answer("Не понял вас. Выберите раздел в меню ниже.", reply_markup=kb.main_menu())


@router.callback_query()
async def unknown_callback(callback: CallbackQuery) -> None:
    await callback.answer("Кнопка устарела, откройте раздел заново.", show_alert=True)
