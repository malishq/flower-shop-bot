from datetime import date, datetime, time

from bot.services.delivery import (
    available_slots,
    day_full,
    day_label,
    delivery_days,
    parse_slot,
    parse_slots,
    slot_label,
)

RAW = ["10:00-13:00", "13:00-16:00", "16:00-19:00", "19:00-21:00"]
SLOTS = parse_slots(RAW)


def test_parse_slots():
    assert len(SLOTS) == 4
    assert SLOTS[0] == (time(10, 0), time(13, 0))
    assert parse_slot("25:00-26:00") is None
    assert parse_slot("13:00-10:00") is None
    assert parse_slot("abc") is None
    assert parse_slots(["10:00-13:00", "мусор"]) == [(time(10, 0), time(13, 0))]


def test_slot_label():
    assert slot_label(SLOTS[0]) == "10:00–13:00"


def test_today_slots_respect_lead_time():
    now = datetime(2026, 10, 28, 12, 30)
    labels = [slot_label(s) for s in available_slots(date(2026, 10, 28), now, SLOTS, lead_hours=2)]
    assert labels == ["16:00–19:00", "19:00–21:00"]


def test_future_day_has_all_slots_and_past_day_none():
    now = datetime(2026, 10, 28, 20, 0)
    assert available_slots(date(2026, 10, 29), now, SLOTS, 2) == SLOTS
    assert available_slots(date(2026, 10, 27), now, SLOTS, 2) == []
    assert available_slots(date(2026, 10, 28), now, SLOTS, 2) == []


def test_delivery_days_skip_today_when_too_late():
    now = datetime(2026, 10, 28, 20, 0)
    days = delivery_days(now, 7, SLOTS, 2)
    assert len(days) == 7
    assert days[0] == date(2026, 10, 29)
    assert days[-1] == date(2026, 11, 4)


def test_delivery_days_include_today_in_the_morning():
    now = datetime(2026, 10, 28, 9, 0)
    days = delivery_days(now, 7, SLOTS, 2)
    assert days[0] == date(2026, 10, 28) and len(days) == 7


def test_day_labels():
    today = date(2026, 10, 28)
    assert day_label(today, today) == "Сегодня, 28 окт"
    assert day_label(date(2026, 10, 29), today) == "Завтра, 29 окт"
    assert day_label(date(2026, 10, 30), today) == "Пт, 30 окт"
    assert day_full(date(2026, 11, 1)) == "1 ноября (вс)"
