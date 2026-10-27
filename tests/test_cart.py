from bot.services.cart import (
    DELIVERY,
    PICKUP,
    CartLine,
    calc_totals,
    change_qty,
    find_promo,
    items_count,
    parse_promo_codes,
    promo_discount,
    subtotal,
)

LINES = [
    CartLine(product_id=1, title="Букет «Нежность»", price=2490, qty=2),
    CartLine(product_id=13, title="Открытка", price=190, qty=1),
]


def test_subtotal_and_count():
    assert subtotal(LINES) == 5170
    assert items_count(LINES) == 3
    assert subtotal([]) == 0


def test_parse_promo_codes():
    codes = parse_promo_codes("FLORA10:10%,welcome:300:2000, broken, BAD:abc, ZERO:0, BIG:150%")
    assert set(codes) == {"FLORA10", "WELCOME"}
    assert codes["FLORA10"].kind == "percent" and codes["FLORA10"].value == 10
    assert codes["WELCOME"].kind == "fixed" and codes["WELCOME"].value == 300
    assert codes["WELCOME"].min_total == 2000


def test_find_promo_is_case_insensitive():
    codes = parse_promo_codes("FLORA10:10%")
    assert find_promo(codes, "  flora10 ") is codes["FLORA10"]
    assert find_promo(codes, "nope") is None


def test_percent_discount_rounds_down():
    promo = parse_promo_codes("FLORA10:10%")["FLORA10"]
    assert promo_discount(5170, promo) == 517
    assert promo_discount(99, promo) == 9
    assert promo_discount(0, promo) == 0


def test_fixed_discount_respects_min_total_and_cap():
    promo = parse_promo_codes("WELCOME:300:2000")["WELCOME"]
    assert promo_discount(1999, promo) == 0
    assert promo_discount(2000, promo) == 300
    big = parse_promo_codes("GIFT:5000")["GIFT"]
    assert promo_discount(1290, big) == 1290


def test_totals_with_delivery_and_promo():
    promo = parse_promo_codes("FLORA10:10%")["FLORA10"]
    totals = calc_totals(LINES, promo, DELIVERY, delivery_price=350, free_delivery_from=3000)
    assert (totals.subtotal, totals.discount, totals.delivery, totals.total) == (5170, 517, 0, 4653)


def test_totals_paid_delivery_below_threshold():
    small = [CartLine(product_id=13, title="Открытка", price=190, qty=2)]
    totals = calc_totals(small, None, DELIVERY, delivery_price=350, free_delivery_from=3000)
    assert totals.delivery == 350 and totals.total == 730


def test_discount_can_drop_below_free_delivery_threshold():
    lines = [CartLine(product_id=1, title="Букет", price=3100, qty=1)]
    promo = parse_promo_codes("WELCOME:300")["WELCOME"]
    totals = calc_totals(lines, promo, DELIVERY, delivery_price=350, free_delivery_from=3000)
    assert totals.discount == 300 and totals.delivery == 350 and totals.total == 3150


def test_pickup_is_free():
    totals = calc_totals(LINES, None, PICKUP, delivery_price=350, free_delivery_from=0)
    assert totals.delivery == 0 and totals.total == 5170


def test_change_qty_limits():
    assert change_qty(1, 1) == 2
    assert change_qty(1, -1) == 0
    assert change_qty(0, -1) == 0
    assert change_qty(20, 1, max_qty=20) == 20
