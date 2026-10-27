import pytest

from bot.services.validation import format_phone, normalize_phone, validate_address, validate_name


@pytest.mark.parametrize(
    "raw",
    ["+7 999 123-45-67", "+7 (999) 123-45-67", "89991234567", "79991234567", "9991234567", " 8 999 123 45 67 "],
)
def test_valid_phones_normalize(raw):
    assert normalize_phone(raw) == "+79991234567"


@pytest.mark.parametrize(
    "raw",
    ["", "привет", "123", "+1 999 123 45 67", "+7 812 123 45 67", "8999123456", "899912345678", "8 (999) 123-45-6a"],
)
def test_invalid_phones_rejected(raw):
    assert normalize_phone(raw) is None


def test_format_phone():
    assert format_phone("+79991234567") == "+7 (999) 123-45-67"
    assert format_phone("12") == "12"


def test_validate_name():
    assert validate_name("  Никита   Комков ") == "Никита Комков"
    assert validate_name("Н") is None
    assert validate_name("Иван 2") is None


def test_validate_address():
    assert validate_address("ул. Садовая, 12, кв. 5") == "ул. Садовая, 12, кв. 5"
    assert validate_address("дом") is None
