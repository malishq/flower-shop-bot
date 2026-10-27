from __future__ import annotations

import re
from typing import Optional

_DIGITS = re.compile(r"\d")
_ALLOWED = re.compile(r"^[\d\s()+\-]+$")


def normalize_phone(raw: str) -> Optional[str]:
    text = raw.strip()
    if not text or not _ALLOWED.match(text):
        return None
    digits = "".join(_DIGITS.findall(text))
    if text.startswith("+") and not digits.startswith("7"):
        return None
    if len(digits) == 11 and digits[0] in "78":
        digits = "7" + digits[1:]
    elif len(digits) == 10 and digits[0] == "9":
        digits = "7" + digits
    else:
        return None
    if digits[1] != "9":
        return None
    return "+" + digits


def format_phone(phone: str) -> str:
    digits = "".join(_DIGITS.findall(phone))
    if len(digits) != 11:
        return phone
    return f"+{digits[0]} ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"


def clean_text(raw: str, min_len: int, max_len: int) -> Optional[str]:
    text = " ".join(raw.split())
    if len(text) < min_len or len(text) > max_len:
        return None
    return text


def validate_name(raw: str) -> Optional[str]:
    text = clean_text(raw, 2, 60)
    if text is None or _DIGITS.search(text):
        return None
    return text


def validate_address(raw: str) -> Optional[str]:
    return clean_text(raw, 5, 200)


def validate_comment(raw: str) -> Optional[str]:
    return clean_text(raw, 1, 300)
