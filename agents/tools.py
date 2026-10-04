from decimal import Decimal

from core.pricing import bounded_price, min_price


class GuardrailViolation(ValueError):
    """Raised when an agent requests an unsafe price change or refund."""


class GuardedTools:
    def __init__(
        self,
        repo,
        stores,
        max_change_pct=0.10,
        min_margin=0.20,
        refund_auto_cap=25.0,
    ):
        self.repo = repo
        self.max_change_pct = max_change_pct
        self.min_margin = min_margin
        self.refund_auto_cap = refund_auto_cap
        if isinstance(stores, dict):
            self.stores = stores
        elif hasattr(stores, "store_id"):
            self.stores = {stores.store_id: stores}
        else:
            self.stores = {store.store_id: store for store in stores}

    def update_price(
        self, store_id, sku, current_price, proposed_price, cost, shipping_cost
    ):
        floor = min_price(cost, shipping_cost, min_margin=self.min_margin)
        if Decimal(str(current_price)) < Decimal(str(floor)):
            raise GuardrailViolation(
                f"Current price {current_price} is below the minimum price {floor}"
            )

        price = bounded_price(
            current_price, proposed_price, self.max_change_pct, floor
        )
        self.stores[store_id].update_price(sku, price)
        self.repo.log(
            "guarded_tools",
            "price_updated",
            {
                "store_id": store_id,
                "sku": sku,
                "current_price": current_price,
                "proposed_price": proposed_price,
                "final_price": price,
                "minimum_price": floor,
            },
        )
        return price

    def request_refund(self, amount, order_key=None):
        if Decimal(str(amount)) < 0:
            raise GuardrailViolation("Refund amount must be non-negative")
        if amount <= self.refund_auto_cap:
            # TODO: connect an approved request to the payment provider.
            return "auto_approved"
        return "needs_human_approval"