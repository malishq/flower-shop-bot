from __future__ import annotations

from typing import Dict, List, Set

NEW = "new"
ACCEPTED = "accepted"
ASSEMBLED = "assembled"
DELIVERING = "delivering"
DONE = "done"
CANCELLED = "cancelled"

ORDER = (NEW, ACCEPTED, ASSEMBLED, DELIVERING, DONE)
ACTIVE = (NEW, ACCEPTED, ASSEMBLED, DELIVERING)
FINAL = (DONE, CANCELLED)

TRANSITIONS: Dict[str, Set[str]] = {
    NEW: {ACCEPTED, CANCELLED},
    ACCEPTED: {ASSEMBLED, CANCELLED},
    ASSEMBLED: {DELIVERING, DONE, CANCELLED},
    DELIVERING: {DONE, CANCELLED},
    DONE: set(),
    CANCELLED: set(),
}

TITLES = {
    NEW: "Новый",
    ACCEPTED: "Принят",
    ASSEMBLED: "Собран",
    DELIVERING: "В пути",
    DONE: "Доставлен",
    CANCELLED: "Отменён",
}

ICONS = {
    NEW: "🆕",
    ACCEPTED: "✅",
    ASSEMBLED: "💐",
    DELIVERING: "🚗",
    DONE: "🏁",
    CANCELLED: "❌",
}

ACTION_TITLES = {
    ACCEPTED: "Принять",
    ASSEMBLED: "Собран",
    DELIVERING: "Передан курьеру",
    DONE: "Доставлен",
    CANCELLED: "Отменить",
}


def title(status: str, delivery_type: str = "delivery") -> str:
    if status == DONE and delivery_type == "pickup":
        return "Выдан"
    return TITLES.get(status, status)


def action_title(status: str, delivery_type: str = "delivery") -> str:
    if status == DONE and delivery_type == "pickup":
        return "Выдан"
    return ACTION_TITLES.get(status, status)


def can_transition(current: str, new: str) -> bool:
    return new in TRANSITIONS.get(current, set())


def next_statuses(current: str, delivery_type: str = "delivery") -> List[str]:
    allowed = TRANSITIONS.get(current, set())
    result = [s for s in ORDER if s in allowed]
    if delivery_type == "pickup":
        result = [s for s in result if s != DELIVERING]
    if CANCELLED in allowed:
        result.append(CANCELLED)
    return result


def is_active(status: str) -> bool:
    return status in ACTIVE


def customer_message(status: str, order_id: int, delivery_type: str, shop_address: str, shop_phone: str) -> str:
    number = f"№ {order_id}"
    if status == ACCEPTED:
        return f"Заказ {number} принят. Флорист уже подбирает цветы."
    if status == ASSEMBLED:
        if delivery_type == "pickup":
            return f"Заказ {number} собран и ждёт вас по адресу {shop_address}."
        return f"Заказ {number} собран. Курьер скоро выедет к вам."
    if status == DELIVERING:
        return f"Заказ {number} в пути, курьер уже едет."
    if status == DONE:
        if delivery_type == "pickup":
            return f"Заказ {number} выдан. Спасибо, что выбрали нас!"
        return f"Заказ {number} доставлен. Спасибо, что выбрали нас!"
    if status == CANCELLED:
        return f"Заказ {number} отменён. Если это ошибка, позвоните нам: {shop_phone}."
    return f"Заказ {number}: статус «{title(status, delivery_type)}»."
