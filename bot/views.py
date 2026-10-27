from __future__ import annotations

import logging
from html import escape
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InputMediaPhoto, Message

from bot import keyboards as kb
from bot.config import Settings
from bot.db import Database
from bot.services.cart import PICKUP, CartLine, Promo, calc_totals
from bot.services.format import cart_text, money
from bot.texts import CATALOG_CAPTION

logger = logging.getLogger(__name__)

COVER = "cover.png"
_FILE_IDS: Dict[str, str] = {}


def _image_key(settings: Settings, image: str) -> str:
    return str(settings.assets_dir / image)


def media_source(settings: Settings, image: str) -> Union[str, FSInputFile]:
    path = settings.assets_dir / image
    if not path.exists():
        path = settings.assets_dir / COVER
    key = str(path)
    if key in _FILE_IDS:
        return _FILE_IDS[key]
    return FSInputFile(path)


def remember_file_id(settings: Settings, image: str, message: Any) -> None:
    if isinstance(message, Message) and message.photo:
        path = settings.assets_dir / image
        if not path.exists():
            path = settings.assets_dir / COVER
        _FILE_IDS[str(path)] = message.photo[-1].file_id


def not_modified(error: TelegramBadRequest) -> bool:
    return "message is not modified" in str(error)


async def safe_edit_text(message: Message, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as error:
        if not not_modified(error):
            raise


async def safe_edit_markup(message: Message, reply_markup: Optional[InlineKeyboardMarkup]) -> None:
    try:
        await message.edit_reply_markup(reply_markup=reply_markup)
    except TelegramBadRequest as error:
        if not not_modified(error):
            raise


async def safe_delete(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        pass


async def send_catalog(message: Message, db: Database, settings: Settings, user_id: int) -> None:
    categories = await db.list_categories()
    count = await db.cart_count(user_id)
    sent = await message.answer_photo(
        media_source(settings, COVER), caption=CATALOG_CAPTION, reply_markup=kb.catalog_menu(categories, count)
    )
    remember_file_id(settings, COVER, sent)


async def edit_to_catalog(message: Message, db: Database, settings: Settings, user_id: int) -> None:
    categories = await db.list_categories()
    count = await db.cart_count(user_id)
    media = InputMediaPhoto(media=media_source(settings, COVER), caption=CATALOG_CAPTION)
    try:
        result = await message.edit_media(media, reply_markup=kb.catalog_menu(categories, count))
    except TelegramBadRequest as error:
        if not not_modified(error):
            raise
        return
    remember_file_id(settings, COVER, result)


def card_caption(product: Mapping[str, Any], category_title: str, index: int, total: int, in_cart: int) -> str:
    text = (
        f"<b>{escape(product['title'])}</b>\n"
        f"{escape(product['description'])}\n\n"
        f"Цена: <b>{money(product['price'])}</b>\n"
        f"{escape(category_title)} · {index + 1} из {total}"
    )
    if in_cart:
        text += f"\nВ корзине: {in_cart} шт."
    return text


async def card_payload(
    db: Database, settings: Settings, user_id: int, slug: str, index: int, qty: int
) -> Optional[Tuple[Mapping[str, Any], str, InlineKeyboardMarkup]]:
    products = await db.list_products(slug)
    category = await db.get_category(slug)
    if not products or category is None:
        return None
    index %= len(products)
    product = products[index]
    in_cart = await db.get_cart_qty(user_id, product["id"])
    count = await db.cart_count(user_id)
    caption = card_caption(product, category["title"], index, len(products), in_cart)
    markup = kb.product_card(slug, index, len(products), product["price"], qty, count)
    return product, caption, markup


async def edit_to_card(message: Message, db: Database, settings: Settings, user_id: int, slug: str, index: int, qty: int = 1) -> bool:
    payload = await card_payload(db, settings, user_id, slug, index, qty)
    if payload is None:
        return False
    product, caption, markup = payload
    media = InputMediaPhoto(media=media_source(settings, product["image"]), caption=caption)
    try:
        result = await message.edit_media(media, reply_markup=markup)
    except TelegramBadRequest as error:
        if not not_modified(error):
            raise
        return True
    remember_file_id(settings, product["image"], result)
    return True


async def send_card(message: Message, db: Database, settings: Settings, user_id: int, slug: str, index: int, qty: int = 1) -> bool:
    payload = await card_payload(db, settings, user_id, slug, index, qty)
    if payload is None:
        return False
    product, caption, markup = payload
    sent = await message.answer_photo(media_source(settings, product["image"]), caption=caption, reply_markup=markup)
    remember_file_id(settings, product["image"], sent)
    return True


async def resolve_promo(db: Database, promo_codes: Dict[str, Promo], user_id: int) -> Optional[Promo]:
    code = await db.get_user_promo(user_id)
    if not code:
        return None
    promo = promo_codes.get(code)
    if promo is None:
        await db.set_user_promo(user_id, None)
    return promo


async def cart_payload(
    db: Database, settings: Settings, promo_codes: Dict[str, Promo], user_id: int
) -> Tuple[List[CartLine], Optional[Promo], str, InlineKeyboardMarkup]:
    lines = await db.get_cart(user_id)
    promo = await resolve_promo(db, promo_codes, user_id)
    totals = calc_totals(lines, promo, PICKUP, settings.delivery_price, settings.free_delivery_from)
    text = cart_text(lines, totals, promo, settings.delivery_price, settings.free_delivery_from)
    markup = kb.cart_keyboard(lines, promo.code if promo else None)
    return lines, promo, text, markup


async def send_cart(message: Message, db: Database, settings: Settings, promo_codes: Dict[str, Promo], user_id: int) -> None:
    _, _, text, markup = await cart_payload(db, settings, promo_codes, user_id)
    await message.answer(text, reply_markup=markup)


async def edit_cart(message: Message, db: Database, settings: Settings, promo_codes: Dict[str, Promo], user_id: int) -> None:
    _, _, text, markup = await cart_payload(db, settings, promo_codes, user_id)
    await safe_edit_text(message, text, markup)
