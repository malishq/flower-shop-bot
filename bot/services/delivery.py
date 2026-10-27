from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import List, Optional, Sequence, Tuple

WEEKDAYS = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")
MONTHS_SHORT = ("янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек")
MONTHS_FULL = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)

_SLOT = re.compile(r"^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})$")


def parse_slot(raw: str) -> Optional[Tuple[time, time]]:
    match = _SLOT.match(raw.strip())
    if not match:
        return None
    h1, m1, h2, m2 = (int(g) for g in match.groups())
    if not (0 <= h1 < 24 and 0 <= h2 <= 24 and 0 <= m1 < 60 and 0 <= m2 < 60):
        return None
    start = time(h1, m1)
    end = time(h2 % 24, m2) if h2 < 24 else time(23, 59)
    if end <= start:
        return None
    return start, end


def parse_slots(raw: Sequence[str]) -> List[Tuple[time, time]]:
    result = []
    for item in raw:
        parsed = parse_slot(item)
        if parsed:
            result.append(parsed)
    return result


def slot_label(slot: Tuple[time, time]) -> str:
    start, end = slot
    return f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}"


def available_slots(day: date, now: datetime, slots: Sequence[Tuple[time, time]], lead_hours: int) -> List[Tuple[time, time]]:
    if day < now.date():
        return []
    if day > now.date():
        return list(slots)
    earliest = now + timedelta(hours=lead_hours)
    return [slot for slot in slots if datetime.combine(day, slot[0]) >= earliest]


def delivery_days(now: datetime, days_ahead: int, slots: Sequence[Tuple[time, time]], lead_hours: int) -> List[date]:
    result = []
    day = now.date()
    while len(result) < days_ahead:
        if available_slots(day, now, slots, lead_hours):
            result.append(day)
        day += timedelta(days=1)
        if (day - now.date()).days > days_ahead + 1:
            break
    return result


def day_label(day: date, today: date) -> str:
    short = f"{day.day} {MONTHS_SHORT[day.month - 1]}"
    if day == today:
        return f"Сегодня, {short}"
    if day == today + timedelta(days=1):
        return f"Завтра, {short}"
    return f"{WEEKDAYS[day.weekday()].capitalize()}, {short}"


def day_full(day: date) -> str:
    return f"{day.day} {MONTHS_FULL[day.month - 1]} ({WEEKDAYS[day.weekday()]})"
