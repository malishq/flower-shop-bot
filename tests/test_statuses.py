import pytest

from bot.services import statuses as st


@pytest.mark.parametrize(
    "current,new,expected",
    [
        (st.NEW, st.ACCEPTED, True),
        (st.NEW, st.CANCELLED, True),
        (st.NEW, st.ASSEMBLED, False),
        (st.ACCEPTED, st.ASSEMBLED, True),
        (st.ACCEPTED, st.DELIVERING, False),
        (st.ASSEMBLED, st.DELIVERING, True),
        (st.ASSEMBLED, st.DONE, True),
        (st.DELIVERING, st.DONE, True),
        (st.DELIVERING, st.NEW, False),
        (st.DONE, st.CANCELLED, False),
        (st.CANCELLED, st.ACCEPTED, False),
    ],
)
def test_transitions(current, new, expected):
    assert st.can_transition(current, new) is expected


def test_next_statuses_order():
    assert st.next_statuses(st.NEW) == [st.ACCEPTED, st.CANCELLED]
    assert st.next_statuses(st.ASSEMBLED) == [st.DELIVERING, st.DONE, st.CANCELLED]
    assert st.next_statuses(st.DONE) == []


def test_pickup_skips_delivering():
    assert st.next_statuses(st.ASSEMBLED, "pickup") == [st.DONE, st.CANCELLED]
    assert st.title(st.DONE, "pickup") == "Выдан"
    assert st.title(st.DONE, "delivery") == "Доставлен"


def test_active_and_messages():
    assert st.is_active(st.DELIVERING) and not st.is_active(st.DONE)
    text = st.customer_message(st.CANCELLED, 1001, "delivery", "адрес", "+7 900")
    assert "№ 1001" in text and "+7 900" in text
    assert "адрес" in st.customer_message(st.ASSEMBLED, 1, "pickup", "адрес", "тел")
