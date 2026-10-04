from abc import ABC, abstractmethod


class StoreAdapter(ABC):
    @abstractmethod
    def verify_webhook(self, raw_body, signature):
        raise NotImplementedError

    @abstractmethod
    def parse_order(self, payload):
        raise NotImplementedError

    @abstractmethod
    def update_inventory(self, sku, quantity):
        raise NotImplementedError

    @abstractmethod
    def update_price(self, sku, price):
        raise NotImplementedError

    @abstractmethod
    def push_tracking(self, order, tracking):
        raise NotImplementedError


class SupplierAdapter(ABC):
    @abstractmethod
    def get_offers(self, sku):
        raise NotImplementedError

    @abstractmethod
    def place_order(self, sku, quantity):
        raise NotImplementedError

    @abstractmethod
    def get_tracking(self, po_id):
        raise NotImplementedError