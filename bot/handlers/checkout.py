from __future__ import annotations

import logging
from datetime import date, time
from typing import Any, Dict, Optional

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot import keyboards as kb
from bot import views
from bot.config import Settings
from bot.db import Database
from bot.services import statuses
from bot.services.cart import DELIVERY, PICKUP, Promo, calc_totals, promo_discount, subtotal
from bot.services.delivery import available_slots, day_full, delivery_days, parse_slots, slot_label
from bot.services.format import (
    order_number,
    order_summary,
    order_text_for_admin,
    order_view,
    payment_instructions,
)
from bot.services.validation import format_phone, normalize_phone, validate_address, validate_comment, validate_name

logger = logging.getLogger(__name__)
router = Router(name="checkout")


class Checkout(StatesGroup):
    name = State()
    phone = State()
    delivery = State()
    address = State()
    date = State()
    slot = State()
    comment = State()
    payment = State()
    confirm = State()


CHOICE_STATES = (Checkout.delivery, Checkout.date, Checkout.slot, Checkout.payment, Checkout.confirm)


def _timestamp(settings: Settings) -> str:
    return settings.now().strftime("%Y-%m-%d %H:%M:%S")


async def _ask_name(message: Message, state: FSMContext, db: Database, user_id: int, first_name: Optional[str]) -> None:
    await state.set_state(Checkout.name)
    suggestion = None
    previous = await db.list_user_orders(user_id, limit=1)
    if previous:
        suggestion = previous[0]["name"]
    elif first_name:
        suggestion = validate_name(first_name)
    await state.update_data(name_suggestion=suggestion)
    await message.answer("Как к вам обращаться?", reply_markup=kb.checkout_name(suggestion))


async def _ask_phone(message: Message, state: FSMContext) -> None:
    await state.set_state(Checkout.phone)
    await message.answer(
        "Номер телефона для связи. Напишите его или нажмите кнопку ниже.",
        reply_markup=kb.phone_keyboard(),
    )


async def _ask_delivery(message: Message, state: FSMContext, db: Database, settings: Settings, promo_codes: Dict[str, Promo], user_id: int) -> None:
    await state.set_state(Checkout.delivery)
    lines = await db.get_cart(user_id)
    promo = await views.resolve_promo(db, promo_codes, user_id)
    amount = subtotal(lines)
    amount -= promo_discount(amount, promo)
    qualifies = settings.free_delivery_from > 0 and amount >= settings.free_delivery_from
    await message.answer("Как получить заказ?", reply_markup=kb.checkout_delivery(settings.delivery_price, qualifies))


async def _ask_address(message: Message, state: FSMContext) -> None:
    await state.set_state(Checkout.address)
    await message.answer("Адрес доставки: улица, дом, квартира, этаж или код домофона.", reply_markup=kb.checkout_cancel())


async def _ask_date(message: Message, state: FSMContext, settings: Settings, edit: bool = False) -> None:
    await state.set_state(Checkout.date)
    now = settings.now()
    slots = parse_slots(settings.delivery_slots)
    days = delivery_days(now, settings.order_days_ahead, slots, settings.order_lead_hours)
    markup = kb.checkout_dates(days, now.date())
    text = "Выберите дату:"
    if edit:
        await views.safe_edit_text(message, text, markup)
    else:
        await message.answer(text, reply_markup=markup)


async def _ask_slot(message: Message, state: FSMContext, settings: Settings, day: date) -> bool:
    now = settings.now()
    slots = available_slots(day, now, parse_slots(settings.delivery_slots), settings.order_lead_hours)
    if not slots:
        return False
    await state.set_state(Checkout.slot)
    await views.safe_edit_text(message, f"Дата: {day_full(day)}. Выберите время:", kb.checkout_slots(slots))
    return True


async def _ask_comment(message: Message, state: FSMContext) -> None:
    await state.set_state(Checkout.comment)
    await message.answer(
        "Комментарий к заказу: текст открытки, пожелания к букету, как найти подъезд.",
        reply_markup=kb.checkout_comment(),
    )


async def _ask_payment(message: Message, state: FSMContext) -> None:
    await state.set_state(Checkout.payment)
    await message.answer("Как будете оплачивать?", reply_markup=kb.checkout_payment())


def _draft(data: Dict[str, Any], settings: Settings, lines, promo: Optional[Promo]) -> Dict[str, Any]:
    totals = calc_totals(lines, promo, data["delivery_type"], settings.delivery_price, settings.free_delivery_from)
    return {
        "name": data["name"],
        "phone": data["phone"],
        "delivery_type": data["delivery_type"],
        "address": data.get("address", ""),
        "delivery_date": data["date"],
        "delivery_date_text": day_full(date.fromisoformat(data["date"])),
        "delivery_slot": data["slot"],
        "comment": data.get("comment", ""),
        "payment": data["payment"],
        "promo_code": promo.code if promo and totals.discount else None,
        "subtotal": totals.subtotal,
        "discount": totals.discount,
        "delivery_price": totals.delivery,
        "total": totals.total,
    }


async def _show_confirm(message: Message, state: FSMContext, db: Database, settings: Settings, promo_codes: Dict[str, Promo], user_id: int) -> None:
    data = await state.get_data()
    lines = await db.get_cart(user_id)
    if not lines:
        await state.clear()
        await message.answer("Корзина опустела, оформлять нечего.", reply_markup=kb.main_menu())
        return
    promo = await views.resolve_promo(db, promo_codes, user_id)
    draft = _draft(data, settings, lines, promo)
    await state.set_state(Checkout.confirm)
    text = "<b>Проверьте заказ</b>\n\n" + order_summary(draft, lines, draft["promo_code"], settings.shop_address)
    await message.answer(text, reply_markup=kb.checkout_confirm())


async def _finish(callback: CallbackQuery, state: FSMContext, db: Database, settings: Settings, promo_codes: Dict[str, Promo], bot: Bot) -> None:
    data = await state.get_data()
    user_id = callback.from_user.id
    lines = await db.get_cart(user_id)
    if not lines:
        await state.clear()
        await callback.answer("Корзина опустела", show_alert=True)
        return
    promo = await views.resolve_promo(db, promo_codes, user_id)
    draft = _draft(data, settings, lines, promo)
    draft.pop("delivery_date_text")
    now = _timestamp(settings)
    draft.update({"user_id": user_id, "status": statuses.NEW, "created_at": now, "updated_at": now})
    order_id = await db.create_order(draft, lines)
    await state.clear()
    order = order_view(await db.get_order(order_id))
    await callback.answer()
    if isinstance(callback.message, Message):
        await views.safe_edit_markup(callback.message, None)
        text = (
            f"<b>Заказ {order_number(order_id)} оформлен</b> 🌷\n\n"
            f"{payment_instructions(order, settings.transfer_details)}\n\n"
            "Мы напишем, когда флорист примет заказ. Статус можно смотреть в «Мои заказы»."
        )
        await callback.message.answer(text, reply_markup=kb.after_order(order_id))
    await notify_admins(bot, db, settings, order_id)


async def notify_admins(bot: Bot, db: Database, settings: Settings, order_id: int) -> None:
    order = await db.get_order(order_id)
    if order is None:
        return
    order = order_view(order)
    lines = await db.get_order_lines(order_id)
    user = await db.get_user(order["user_id"])
    text = "🔔 Новый заказ\n\n" + order_text_for_admin(order, lines, settings.shop_address, user)
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=kb.admin_order(order))
        except Exception as error:
            logger.warning("Не удалось отправить заказ %s администратору %s: %s", order_id, admin_id, error)


@router.callback_query(kb.CheckoutCb.filter(F.step == "start"))
async def checkout_start(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lines = await db.get_cart(callback.from_user.id)
    if not lines:
        await callback.answer("Корзина пуста", show_alert=True)
        return
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    await state.clear()
    await callback.answer()
    await _ask_name(callback.message, state, db, callback.from_user.id, callback.from_user.first_name)


@router.callback_query(kb.CheckoutCb.filter(F.step == "cancel"))
async def checkout_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        await views.safe_edit_markup(callback.message, None)
        await callback.message.answer("Оформление отменено. Корзина сохранена.", reply_markup=kb.main_menu())
    await callback.answer()


@router.callback_query(kb.CheckoutCb.filter(F.step == "restart"))
async def checkout_restart(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    await state.set_data({})
    if isinstance(callback.message, Message):
        await views.safe_edit_markup(callback.message, None)
        await _ask_name(callback.message, state, db, callback.from_user.id, callback.from_user.first_name)
    await callback.answer()


@router.callback_query(Checkout.name, kb.CheckoutCb.filter(F.step == "name_use"))
async def name_use(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    name = data.get("name_suggestion")
    if not name or not isinstance(callback.message, Message):
        await callback.answer("Напишите имя сообщением")
        return
    await state.update_data(name=name)
    await views.safe_edit_text(callback.message, f"Имя: {name}")
    await callback.answer()
    await _ask_phone(callback.message, state)


@router.message(Checkout.name, F.text)
async def name_enter(message: Message, state: FSMContext) -> None:
    name = validate_name(message.text or "")
    if name is None:
        await message.answer("Напишите имя буквами, от 2 до 60 символов.", reply_markup=kb.checkout_cancel())
        return
    await state.update_data(name=name)
    await _ask_phone(message, state)


@router.message(Checkout.phone, F.text == kb.BTN_CANCEL)
async def phone_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Оформление отменено. Корзина сохранена.", reply_markup=kb.main_menu())


@router.message(Checkout.phone, F.contact)
async def phone_contact(message: Message, state: FSMContext, db: Database, settings: Settings, promo_codes: Dict[str, Promo]) -> None:
    raw = message.contact.phone_number or ""
    phone = normalize_phone(raw if raw.startswith("+") else "+" + raw)
    if phone is None:
        await message.answer("Этот номер не похож на российский. Напишите номер вручную: +7 999 123-45-67.", reply_markup=kb.phone_keyboard())
        return
    await state.update_data(phone=phone)
    await message.answer(f"Телефон: {format_phone(phone)}", reply_markup=kb.main_menu())
    await _ask_delivery(message, state, db, settings, promo_codes, message.from_user.id)


@router.message(Checkout.phone, F.text)
async def phone_enter(message: Message, state: FSMContext, db: Database, settings: Settings, promo_codes: Dict[str, Promo]) -> None:
    phone = normalize_phone(message.text or "")
    if phone is None:
        await message.answer("Не похоже на номер. Пример: +7 999 123-45-67 или 8 999 123 45 67.", reply_markup=kb.phone_keyboard())
        return
    await state.update_data(phone=phone)
    await message.answer(f"Телефон: {format_phone(phone)}", reply_markup=kb.main_menu())
    await _ask_delivery(message, state, db, settings, promo_codes, message.from_user.id)


@router.callback_query(Checkout.delivery, kb.CheckoutCb.filter(F.step == "delivery"))
async def delivery_choose(callback: CallbackQuery, callback_data: kb.CheckoutCb, state: FSMContext, settings: Settings) -> None:
    if callback_data.value not in (DELIVERY, PICKUP) or not isinstance(callback.message, Message):
        await callback.answer()
        return
    await state.update_data(delivery_type=callback_data.value, address="")
    await callback.answer()
    if callback_data.value == DELIVERY:
        await views.safe_edit_text(callback.message, "Получение: доставка курьером")
        await _ask_address(callback.message, state)
    else:
        await views.safe_edit_text(callback.message, f"Получение: самовывоз, {settings.shop_address}")
        await _ask_date(callback.message, state, settings)


@router.message(Checkout.address, F.text)
async def address_enter(message: Message, state: FSMContext, settings: Settings) -> None:
    address = validate_address(message.text or "")
    if address is None:
        await message.answer("Напишите адрес подробнее: улица, дом, квартира.", reply_markup=kb.checkout_cancel())
        return
    await state.update_data(address=address)
    await _ask_date(message, state, settings)


@router.callback_query(Checkout.date, kb.CheckoutCb.filter(F.step == "date"))
async def date_choose(callback: CallbackQuery, callback_data: kb.CheckoutCb, state: FSMContext, settings: Settings) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    try:
        day = date.fromisoformat(callback_data.value)
    except ValueError:
        await callback.answer()
        return
    await state.update_data(date=day.isoformat())
    if not await _ask_slot(callback.message, state, settings, day):
        await callback.answer("На эту дату интервалов уже нет", show_alert=True)
        await _ask_date(callback.message, state, settings, edit=True)
        return
    await callback.answer()


@router.callback_query(Checkout.slot, kb.CheckoutCb.filter(F.step == "back_date"))
async def slot_back(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if isinstance(callback.message, Message):
        await _ask_date(callback.message, state, settings, edit=True)
    await callback.answer()


@router.callback_query(Checkout.slot, kb.CheckoutCb.filter(F.step == "slot"))
async def slot_choose(callback: CallbackQuery, callback_data: kb.CheckoutCb, state: FSMContext, settings: Settings) -> None:
    data = await state.get_data()
    if not isinstance(callback.message, Message) or "date" not in data:
        await callback.answer()
        return
    try:
        start_raw, end_raw = callback_data.value.split("-")
        chosen = (time(int(start_raw[:2]), int(start_raw[2:])), time(int(end_raw[:2]), int(end_raw[2:])))
    except ValueError:
        await callback.answer()
        return
    day = date.fromisoformat(data["date"])
    slots = available_slots(day, settings.now(), parse_slots(settings.delivery_slots), settings.order_lead_hours)
    if chosen not in slots:
        await callback.answer("Этот интервал уже недоступен", show_alert=True)
        if not await _ask_slot(callback.message, state, settings, day):
            await _ask_date(callback.message, state, settings, edit=True)
        return
    label = slot_label(chosen)
    await state.update_data(slot=label)
    await views.safe_edit_text(callback.message, f"Когда: {day_full(day)}, {label}")
    await callback.answer()
    await _ask_comment(callback.message, state)


@router.callback_query(Checkout.comment, kb.CheckoutCb.filter(F.step == "comment_skip"))
async def comment_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(comment="")
    if isinstance(callback.message, Message):
        await views.safe_edit_text(callback.message, "Без комментария")
        await _ask_payment(callback.message, state)
    await callback.answer()


@router.message(Checkout.comment, F.text)
async def comment_enter(message: Message, state: FSMContext) -> None:
    comment = validate_comment(message.text or "")
    if comment is None:
        await message.answer("Комментарий до 300 символов, пожалуйста.", reply_markup=kb.checkout_comment())
        return
    await state.update_data(comment=comment)
    await _ask_payment(message, state)


@router.callback_query(Checkout.payment, kb.CheckoutCb.filter(F.step == "payment"))
async def payment_choose(callback: CallbackQuery, callback_data: kb.CheckoutCb, state: FSMContext, db: Database, settings: Settings, promo_codes: Dict[str, Promo]) -> None:
    if callback_data.value not in ("cash", "transfer") or not isinstance(callback.message, Message):
        await callback.answer()
        return
    await state.update_data(payment=callback_data.value)
    title = "при получении" if callback_data.value == "cash" else "переводом"
    await views.safe_edit_text(callback.message, f"Оплата: {title}")
    await callback.answer()
    await _show_confirm(callback.message, state, db, settings, promo_codes, callback.from_user.id)


@router.callback_query(Checkout.confirm, kb.CheckoutCb.filter(F.step == "confirm"))
async def confirm_order(callback: CallbackQuery, state: FSMContext, db: Database, settings: Settings, promo_codes: Dict[str, Promo], bot: Bot) -> None:
    await _finish(callback, state, db, settings, promo_codes, bot)


@router.callback_query(kb.CheckoutCb.filter())
async def checkout_stale(callback: CallbackQuery) -> None:
    await callback.answer("Этот шаг уже неактуален. Начните оформление из корзины.", show_alert=True)


@router.message(Checkout.delivery)
@router.message(Checkout.date)
@router.message(Checkout.slot)
@router.message(Checkout.payment)
@router.message(Checkout.confirm)
async def choice_hint(message: Message) -> None:
    await message.answer("Выберите вариант кнопкой в сообщении выше или отмените оформление.", reply_markup=kb.checkout_cancel())


@router.message(Checkout.name)
@router.message(Checkout.phone)
@router.message(Checkout.address)
@router.message(Checkout.comment)
async def text_hint(message: Message) -> None:
    await message.answer("Напишите ответ текстом, пожалуйста.", reply_markup=kb.checkout_cancel())
