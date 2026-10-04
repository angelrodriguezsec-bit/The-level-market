from adapters.base import StoreAdapter


class MockStore(StoreAdapter):
    def __init__(self, store_id="mock-store"):
        self.store_id = store_id
        self.inventory = {}
        self.prices = {}
        self.tracking_updates = []

    def verify_webhook(self, raw_body, signature):
        return True

    def parse_order(self, payload):
        raise NotImplementedError("MockStore does not parse external order payloads")

    def update_inventory(self, sku, quantity):
        self.inventory[sku] = quantity

    def update_price(self, sku, price):
        self.prices[sku] = price

    def push_tracking(self, order, tracking):
        self.tracking_updates.append((order.key, tracking))