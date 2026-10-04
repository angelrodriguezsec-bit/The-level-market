from core.state_machine import OrderStatus, transition
from services.sourcing import rank_offers


class OrderService:
    def __init__(self, repo, suppliers, stores):
        self.repo = repo
        self.suppliers = self._as_mapping(suppliers, "supplier_id")
        self.stores = self._as_mapping(stores, "store_id")

    @staticmethod
    def _as_mapping(adapters, identifier):
        if isinstance(adapters, dict):
            return adapters
        return {getattr(adapter, identifier): adapter for adapter in adapters}

    def _change_status(self, order, target, detail=None):
        previous = order.status
        order.status = transition(previous, target)
        self.repo.save_order(order)
        self.repo.log(
            "order_service",
            "status_changed",
            {
                "order_key": order.key,
                "from": previous.value,
                "to": order.status.value,
                **(detail or {}),
            },
        )

    def _exception(self, order, reason):
        order.notes.append(reason)
        self._change_status(order, OrderStatus.EXCEPTION, {"reason": reason})
        return order

    @staticmethod
    def _valid(order):
        address = order.shipping_address or {}
        has_country = bool(address.get("country") or address.get("country_code"))
        return bool(order.lines) and has_country and all(
            bool(line.sku) and line.quantity > 0 for line in order.lines
        )

    def handle_new_order(self, order):
        existing = self.repo.get_order(order.key)
        if existing is not None:
            return existing

        if order.status != OrderStatus.RECEIVED:
            order.status = transition(order.status, OrderStatus.RECEIVED)
        self.repo.save_order(order)
        self.repo.log(
            "order_service",
            "status_changed",
            {"order_key": order.key, "from": None, "to": OrderStatus.RECEIVED.value},
        )

        if not self._valid(order):
            return self._exception(order, "invalid order")
        self._change_status(order, OrderStatus.VALIDATED)

        line_offers = []
        for line in order.lines:
            offers = []
            for supplier in self.suppliers.values():
                offers.extend(supplier.get_offers(line.sku))
            ranked = rank_offers(offers, line.quantity)
            if not ranked:
                return self._exception(order, "no supplier stock")
            line_offers.append(ranked)
        self._change_status(order, OrderStatus.SOURCED)

        fulfillment = []
        for line, ranked in zip(order.lines, line_offers):
            placed = False
            for offer in ranked:
                supplier = self.suppliers.get(offer.supplier_id)
                if supplier is None:
                    continue
                try:
                    po_id = supplier.place_order(line.sku, line.quantity)
                except Exception:
                    continue
                fulfillment.append(
                    {
                        "sku": line.sku,
                        "supplier_id": offer.supplier_id,
                        "po_id": po_id,
                    }
                )
                placed = True
                break
            if not placed:
                order.fulfillment = fulfillment
                return self._exception(order, "all supplier orders failed")

        order.fulfillment = fulfillment
        self._change_status(order, OrderStatus.ORDERED_FROM_SUPPLIER)
        return order

    def handle_shipment(self, order_key, tracking):
        order = self.repo.get_order(order_key)
        if order is None:
            raise KeyError(order_key)
        store = self.stores[order.store_id]
        store.push_tracking(order, tracking)
        order.tracking = tracking
        if order.status != OrderStatus.SHIPPED:
            self._change_status(order, OrderStatus.SHIPPED, {"tracking": tracking})
        else:
            self.repo.save_order(order)
        return order

    def handle_delivered(self, order_key):
        order = self.repo.get_order(order_key)
        if order is None:
            raise KeyError(order_key)
        self._change_status(order, OrderStatus.DELIVERED)
        return order

    def poll_supplier_tracking(self):
        shipped = []
        for order in self.repo.list_orders(OrderStatus.ORDERED_FROM_SUPPLIER):
            for fulfillment in order.fulfillment:
                supplier = self.suppliers.get(fulfillment["supplier_id"])
                if supplier is None:
                    continue
                tracking = supplier.get_tracking(fulfillment["po_id"])
                if tracking:
                    shipped.append(self.handle_shipment(order.key, tracking))
                    break
        return shipped