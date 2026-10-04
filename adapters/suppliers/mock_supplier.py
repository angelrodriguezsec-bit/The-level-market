from adapters.base import SupplierAdapter
from core.models import SupplierOffer


class MockSupplier(SupplierAdapter):
    def __init__(self, catalog, fail_orders=False, supplier_id="mock-supplier"):
        self.catalog = {
            sku: dict(item) if isinstance(item, dict) else item
            for sku, item in catalog.items()
        }
        self.fail_orders = fail_orders
        self.supplier_id = supplier_id
        self._next_po_id = 1
        self._tracking = {}
        self._purchase_orders = {}

    def get_offers(self, sku):
        item = self.catalog.get(sku)
        if item is None:
            return []
        if isinstance(item, SupplierOffer):
            return [
                SupplierOffer(
                    supplier_id=self.supplier_id,
                    sku=item.sku,
                    cost=item.cost,
                    shipping_cost=item.shipping_cost,
                    stock=item.stock,
                    ship_days=item.ship_days,
                )
            ]
        return [
            SupplierOffer(
                supplier_id=self.supplier_id,
                sku=sku,
                cost=item["cost"],
                shipping_cost=item.get("shipping_cost", 0),
                stock=item["stock"],
                ship_days=item.get("ship_days", 0),
            )
        ]

    def place_order(self, sku, quantity):
        if self.fail_orders:
            raise RuntimeError(f"{self.supplier_id} failed to place order")
        item = self.catalog.get(sku)
        if item is None:
            raise ValueError(f"Unknown SKU: {sku}")
        stock = item.stock if isinstance(item, SupplierOffer) else item["stock"]
        if stock < quantity:
            raise ValueError(f"Insufficient stock for SKU: {sku}")
        if isinstance(item, SupplierOffer):
            item.stock -= quantity
        else:
            item["stock"] -= quantity
        po_id = f"{self.supplier_id}-{self._next_po_id}"
        self._next_po_id += 1
        self._purchase_orders[po_id] = sku
        return po_id

    def get_tracking(self, po_id):
        return self._tracking.get(po_id)

    def ship(self, po_id, tracking):
        if po_id not in self._purchase_orders:
            raise KeyError(f"Unknown purchase order: {po_id}")
        self._tracking[po_id] = tracking