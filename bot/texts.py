from __future__ import annotations

from html import escape

from bot.config import Settings
from bot.services.format import money


def greeting(settings: Settings, first_name: str) -> str:
    name = escape(first_name) if first_name else "друг"
    return (
        f"Здравствуйте, {name}! Это <b>{escape(settings.shop_name)}</b> 🌷\n\n"
        "Здесь можно выбрать букет или композицию, добавить открытку или шары "
        "и оформить доставку на удобное время.\n\n"
        "Выберите раздел в меню ниже."
    )


def about(settings: Settings) -> str:
    free = f", бесплатно от {money(settings.free_delivery_from)}" if settings.free_delivery_from > 0 else ""
    return (
        f"<b>{escape(settings.shop_name)}</b>\n\n"
        f"Адрес: {escape(settings.shop_address)}\n"
        f"Часы работы: {escape(settings.shop_hours)}\n"
        f"Телефон: {escape(settings.shop_phone)}\n\n"
        f"Доставка курьером: {money(settings.delivery_price)}{free}. "
        f"Самовывоз бесплатный.\n"
        f"Интервалы доставки: {', '.join(s.replace('-', '–') for s in settings.delivery_slots)}. "
        f"Ближайший интервал — через {settings.order_lead_hours} ч после заказа.\n\n"
        "Оплата при получении или переводом."
    )


def help_text(settings: Settings, is_admin: bool) -> str:
    text = (
        "<b>Как сделать заказ</b>\n"
        "1. Откройте «Каталог», выберите категорию и товар, нажмите «В корзину».\n"
        "2. В «Корзине» проверьте состав, введите промокод, если есть.\n"
        "3. Нажмите «Оформить заказ» и ответьте на несколько вопросов: имя, телефон, "
        "доставка или самовывоз, дата и время, оплата.\n"
        "4. Мы напишем вам, когда заказ примут, соберут и передадут курьеру.\n\n"
        "<b>Команды</b>\n"
        "/catalog — каталог\n"
        "/cart — корзина\n"
        "/orders — мои заказы\n"
        "/help — эта подсказка\n\n"
        f"Вопросы: {escape(settings.shop_phone)}"
    )
    if is_admin:
        text += (
            "\n\n<b>Для администратора</b>\n"
            "/orders — активные заказы с фильтром по статусу\n"
            "/stats — заказы и выручка за день, неделю, месяц\n"
            "/stock — включить или выключить товар в каталоге\n"
            "Новые заказы приходят сюда с кнопками смены статуса."
        )
    return text


CATALOG_CAPTION = "<b>Каталог</b>\nВыберите категорию. В карточках — состав, цена и кнопка «В корзину»."
