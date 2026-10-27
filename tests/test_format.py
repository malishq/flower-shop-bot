from bot.services.cart import CartLine, Totals, parse_promo_codes
from bot.services.format import cart_text, money, order_summary, plural

LINES = [CartLine(product_id=1, title="Букет <Нежность>", price=2490, qty=2)]


def test_money():
    assert money(2490) == "2 490 ₽"
    assert money(1234567) == "1 234 567 ₽"
    assert money(0) == "0 ₽"


def test_plural():
    assert plural(1, "товар", "товара", "товаров") == "товар"
    assert plural(3, "товар", "товара", "товаров") == "товара"
    assert plural(12, "товар", "товара", "товаров") == "товаров"


def test_cart_text_escapes_html_and_shows_totals():
    promo = parse_promo_codes("FLORA10:10%")["FLORA10"]
    text = cart_text(LINES, Totals(4980, 498, 0), promo, 350, 3000)
    assert "&lt;Нежность&gt;" in text
    assert "−498 ₽" in text and "Итого: 4 482 ₽" in text
    assert "Пока пусто" in cart_text([], Totals(0, 0, 0), None, 350, 3000)


def test_order_summary():
    order = {
        "subtotal": 4980, "discount": 0, "delivery_price": 350, "total": 5330,
        "name": "Никита", "phone": "+79991234567", "delivery_type": "delivery",
        "address": "ул. Садовая, 12", "delivery_date_text": "29 октября (чт)",
        "delivery_slot": "13:00–16:00", "payment": "cash", "comment": "позвонить за час",
    }
    text = order_summary(order, LINES, None, "Москва")
    assert "Доставка: 350 ₽" in text and "Итого: 5 330 ₽" in text
    assert "+7 (999) 123-45-67" in text and "позвонить за час" in text
