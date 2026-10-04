def rank_offers(offers, qty, max_ship_days=None, day_penalty=0.5):
    eligible = [
        offer
        for offer in offers
        if offer.stock >= qty
        and (max_ship_days is None or offer.ship_days <= max_ship_days)
    ]
    return sorted(
        eligible,
        key=lambda offer: (
            offer.cost * qty
            + offer.shipping_cost
            + day_penalty * offer.ship_days,
            offer.supplier_id,
        ),
    )


def choose_offer(offers, qty, max_ship_days=None, day_penalty=0.5):
    ranked = rank_offers(offers, qty, max_ship_days, day_penalty)
    return ranked[0] if ranked else None