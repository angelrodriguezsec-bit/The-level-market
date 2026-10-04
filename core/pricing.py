from decimal import Decimal, ROUND_CEILING


CENT = Decimal("0.01")


def _decimal(value):
    return Decimal(str(value))


def min_price(cost, shipping, fee_pct=0.029, fee_fixed=0.30, min_margin=0.20):
    denominator = Decimal("1") - _decimal(fee_pct) - _decimal(min_margin)
    if denominator <= 0:
        raise ValueError("fee_pct + min_margin must be less than 1")
    total = _decimal(cost) + _decimal(shipping) + _decimal(fee_fixed)
    return float((total / denominator).quantize(CENT, rounding=ROUND_CEILING))


def sell_price(cost, shipping, fee_pct=0.029, fee_fixed=0.30, margin_pct=0.30):
    denominator = Decimal("1") - _decimal(fee_pct) - _decimal(margin_pct)
    if denominator <= 0:
        raise ValueError("fee_pct + margin_pct must be less than 1")
    total = _decimal(cost) + _decimal(shipping) + _decimal(fee_fixed)
    target = total / denominator
    ending_offset = Decimal("0.99")
    whole_dollars = (target - ending_offset).to_integral_value(rounding=ROUND_CEILING)
    return float(max(ending_offset, whole_dollars + ending_offset))


def margin(price, cost, shipping, fee_pct=0.029, fee_fixed=0.30):
    price = _decimal(price)
    if price <= 0:
        raise ValueError("price must be greater than zero")
    fees = price * _decimal(fee_pct) + _decimal(fee_fixed)
    profit = price - fees - _decimal(cost) - _decimal(shipping)
    return float(profit / price)


def bounded_price(current, proposed, max_change_pct, floor):
    current = _decimal(current)
    proposed = _decimal(proposed)
    floor = _decimal(floor)
    change = _decimal(max_change_pct)
    if current < 0 or change < 0:
        raise ValueError("current and max_change_pct must be non-negative")
    lower = max(floor, current * (Decimal("1") - change))
    upper = max(floor, current * (Decimal("1") + change))
    return float(min(max(proposed, lower), upper))