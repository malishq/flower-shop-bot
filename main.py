from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from bot.config import Settings, load_settings
from bot.db import Database
from bot.handlers import admin, cart, catalog, checkout, common, errors, fallback, orders
from bot.services.cart import parse_promo_codes

logger = logging.getLogger("flora")

USER_COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="catalog", description="Каталог"),
    BotCommand(command="cart", description="Корзина"),
    BotCommand(command="orders", description="Мои заказы"),
    BotCommand(command="help", description="Помощь"),
]

ADMIN_COMMANDS = [
    BotCommand(command="orders", description="Активные заказы"),
    BotCommand(command="stats", description="Статистика продаж"),
    BotCommand(command="stock", description="Наличие товаров"),
    BotCommand(command="catalog", description="Каталог"),
    BotCommand(command="cart", description="Корзина"),
    BotCommand(command="help", description="Помощь"),
    BotCommand(command="start", description="Главное меню"),
]


async def _try(label: str, coro) -> None:
    try:
        await coro
    except TelegramAPIError as error:
        logger.warning("%s: %s", label, error)


async def on_startup(bot: Bot, settings: Settings) -> None:
    await _try("Команды пользователя", bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeDefault()))
    for admin_id in settings.admin_ids:
        await _try(f"Команды администратора {admin_id}", bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id)))
    await _try(
        "Описание бота",
        bot.set_my_description(
            f"{settings.shop_name}: букеты, композиции в коробке и растения с доставкой. "
            "Выберите цветы в каталоге, оформите заказ за минуту и следите за его статусом."
        ),
    )
    await _try("Короткое описание", bot.set_my_short_description("Букеты и растения с доставкой. Заказ за минуту."))
    me = await bot.get_me()
    logger.info("Бот @%s запущен, администраторов: %d", me.username, len(settings.admin_ids))


def build_dispatcher(settings: Settings, db: Database) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp["settings"] = settings
    dp["db"] = db
    dp["promo_codes"] = parse_promo_codes(settings.promo_codes)
    dp.include_routers(admin.router, common.router, catalog.router, cart.router, checkout.router, orders.router, fallback.router)
    dp.errors.register(errors.on_error)
    return dp


async def run() -> None:
    settings = load_settings()
    db = Database(settings.db_path)
    await db.connect()
    await db.init()
    count = await db.seed_catalog(settings.catalog_path)
    logger.info("База %s готова, товаров в каталоге: %d", settings.db_path, count)

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher(settings, db)
    dp.startup.register(on_startup)
    try:
        await dp.start_polling(bot)
    finally:
        await db.close()
        logger.info("Соединение с базой закрыто")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")


if __name__ == "__main__":
    main()
