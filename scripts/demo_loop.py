import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.stores.mock_store import MockStore
from adapters.suppliers.mock_supplier import MockSupplier
from core.db import Repository
from core.events import EventBus
from core.models import Order, OrderLine
from services.order_service import OrderService


def main():
    repo = Repository()
    store = MockStore("demo-store")
    cheap_supplier = MockSupplier(
        {
            "demo-sku": {
                "cost": 4.0,
                "shipping_cost": 1.0,
                "stock": 20,
                "ship_days": 2,
            }
        },
        fail_orders=True,
        supplier_id="cheapest-but-failing",
    )
    backup_supplier = MockSupplier(
        {
            "demo-sku": {
                "cost": 6.0,
                "shipping_cost": 1.0,
                "stock": 20,
                "ship_days": 2,
            }
        },
        supplier_id="backup-supplier",
    )
    suppliers = [cheap_supplier, backup_supplier]
    service = OrderService(repo, suppliers, [store])
    bus = EventBus()
    bus.subscribe("order.received", lambda event: service.handle_new_order(event["data"]))

    order = Order(
        external_id="demo-order-1",
        store_id=store.store_id,
        customer_email="customer@example.com",
        shipping_address={"country": "US"},
        lines=[OrderLine("demo-sku", 2, 19.99)],
    )
    bus.publish("order.received", order)
    bus.publish("order.received", order)
    bus.process()

    processed = repo.get_order(order.key)
    print(f"After duplicate webhooks: {processed.status.value}")
    print(f"Supplier selected: {processed.fulfillment[0]['supplier_id']}")

    po_id = processed.fulfillment[0]["po_id"]
    backup_supplier.ship(po_id, "DEMO-TRACK-123")
    service.poll_supplier_tracking()
    shipped = repo.get_order(order.key)
    print(f"After shipment: {shipped.status.value} ({shipped.tracking})")

    service.handle_delivered(order.key)
    delivered = repo.get_order(order.key)
    print(f"After delivery: {delivered.status.value}")
    repo.close()


if __name__ == "__main__":
    main()