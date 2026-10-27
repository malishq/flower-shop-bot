from __future__ import annotations

import logging

from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)

USER_TEXT = "Что-то пошло не так. Попробуйте ещё раз или нажмите /start."


async def on_error(event: ErrorEvent) -> None:
    logger.exception("Ошибка при обработке апдейта %s", event.update.update_id, exc_info=event.exception)
    try:
        if event.update.callback_query:
            await event.update.callback_query.answer(USER_TEXT, show_alert=True)
        elif event.update.message:
            await event.update.message.answer(USER_TEXT)
    except Exception as error:
        logger.warning("Не удалось сообщить пользователю об ошибке: %s", error)
