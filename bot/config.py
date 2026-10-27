from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Tuple

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: Tuple[int, ...]
    db_path: Path
    tz_offset_hours: int
    shop_name: str
    shop_phone: str
    shop_address: str
    shop_hours: str
    delivery_price: int
    free_delivery_from: int
    delivery_slots: Tuple[str, ...]
    order_lead_hours: int
    order_days_ahead: int
    max_qty: int
    promo_codes: str
    transfer_details: str
    catalog_path: Path
    assets_dir: Path

    @property
    def tz(self) -> timezone:
        return timezone(timedelta(hours=self.tz_offset_hours))

    def now(self) -> datetime:
        return datetime.now(self.tz).replace(tzinfo=None)

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _ids(raw: str) -> Tuple[int, ...]:
    result = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            result.append(int(part))
    return tuple(result)


def _list(raw: str) -> Tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _path(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def load_settings() -> Settings:
    token = _env("BOT_TOKEN")
    if not token:
        raise RuntimeError("В .env не задан BOT_TOKEN")
    return Settings(
        bot_token=token,
        admin_ids=_ids(_env("ADMIN_IDS")),
        db_path=_path(_env("DB_PATH", "data/flora.db")),
        tz_offset_hours=_int("TZ_OFFSET_HOURS", 3),
        shop_name=_env("SHOP_NAME", "Цветочная лавка Flora"),
        shop_phone=_env("SHOP_PHONE", "+7 (900) 000-00-00"),
        shop_address=_env("SHOP_ADDRESS", "Москва, ул. Садовая, 12"),
        shop_hours=_env("SHOP_HOURS", "ежедневно с 9:00 до 21:00"),
        delivery_price=_int("DELIVERY_PRICE", 350),
        free_delivery_from=_int("FREE_DELIVERY_FROM", 3000),
        delivery_slots=_list(_env("DELIVERY_SLOTS", "10:00-13:00,13:00-16:00,16:00-19:00,19:00-21:00")),
        order_lead_hours=_int("ORDER_LEAD_HOURS", 2),
        order_days_ahead=_int("ORDER_DAYS_AHEAD", 7),
        max_qty=_int("MAX_QTY", 20),
        promo_codes=_env("PROMO_CODES", ""),
        transfer_details=_env("TRANSFER_DETAILS", "переводом по номеру телефона магазина. В комментарии укажите номер заказа."),
        catalog_path=_path(_env("CATALOG_PATH", "data/catalog.json")),
        assets_dir=_path(_env("ASSETS_DIR", "assets/catalog")),
    )
