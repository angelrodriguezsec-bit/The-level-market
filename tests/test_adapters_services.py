import base64
import hashlib
import hmac
import unittest

from adapters.stores.mock_store import MockStore
from adapters.stores.shopify import ShopifyAdapter
from adapters.suppliers.mock_supplier import MockSupplier
from core.db import Repository
from core.models import Order, OrderLine, SupplierOffer
from core.state_machine import OrderStatus
from services.inventory_sync import sync_inventory
from services.order_service import OrderService
from services.sourcing import choose_offer, rank_offers


def supplier(supplier_id, cost, stock=20, fail_orders=False, ship_days=2):
    return MockSupplier(
        {
            "sku-1": {
                "cost": cost,
                "shipping_cost": 1,
                "stock": stock,
                "ship_days": ship_days,
            }
        },
        fail_orders=fail_orders,
        supplier_id=supplier_id,
    )


def order(external_id="order-1", lines=None, address=None):
    return Order(
        external_id,
        "store-1",
        "buyer@example.com",
        address if address is not None else {"country": "US"},
        lines if lines is not None else [OrderLine("sku-1", 2, 15)],
    )


class ShopifyAdapterTests(unittest.TestCase):
    def test_webhook_verification_and_order_parsing(self):
        adapter = ShopifyAdapter("secret", store_id="shop-1")
        body = b'{"id":123}'
        signature = base64.b64encode(
            hmac.new(b"secret", body, hashlib.sha256).digest()
        ).decode("ascii")
        self.assertTrue(adapter.verify_webhook(body, signature))
        self.assertFalse(adapter.verify_webhook(body, "invalid"))

        parsed = adapter.parse_order(
            {
                "id": 123,
                "email": "buyer@example.com",
                "shipping_address": {"country_code": "US"},
                "line_items": [{"sku": "sku-1", "quantity": 2, "price": "15.00"}],
            }
        )
        self.assertEqual(parsed.store_id, "shop-1")
        self.assertEqual(parsed.external_id, "123")
        self.assertEqual(parsed.lines[0], OrderLine("sku-1", 2, 15.0))


class SourcingTests(unittest.TestCase):
    def test_rank_filters_stock_and_days_then_sorts_cost(self):
        offers = [
            SupplierOffer("b", "sku-1", 3, 1, 5, 2),
            SupplierOffer("a", "sku-1", 3, 1, 5, 2),
            SupplierOffer("low-stock", "sku-1", 1, 0, 1, 1),
            SupplierOffer("slow", "sku-1", 1, 0, 5, 8),
        ]
        ranked = rank_offers(offers, 2, max_ship_days=5)
        self.assertEqual([offer.supplier_id for offer in ranked], ["a", "b"])
        self.assertEqual(choose_offer(offers, 2, max_ship_days=5), ranked[0])
        self.assertIsNone(choose_offer(offers, 10))


class OrderServiceTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repository()
        self.store = MockStore("store-1")

    def tearDown(self):
        self.repo.close()

    def service(self, *suppliers):
        return OrderService(self.repo, suppliers, [self.store])

    def test_process_is_idempotent_audited_and_reroutes(self):
        failing = supplier("cheap", 1, fail_orders=True)
        fallback = supplier("backup", 2)
        service = self.service(failing, fallback)
        processed = service.handle_new_order(order())
        self.assertEqual(processed.status, OrderStatus.ORDERED_FROM_SUPPLIER)
        self.assertEqual(processed.fulfillment[0]["supplier_id"], "backup")
        self.assertEqual(service.handle_new_order(order()), self.repo.get_order(processed.key))
        self.assertEqual(
            [entry["detail"]["to"] for entry in self.repo.audit()],
            ["received", "validated", "sourced", "ordered_from_supplier"],
        )
        self.assertEqual(failing.catalog["sku-1"]["stock"], 20)
        self.assertEqual(fallback.catalog["sku-1"]["stock"], 18)

    def test_invalid_or_unsourced_orders_enter_exception(self):
        service = self.service(supplier("supplier", 1))
        invalid = service.handle_new_order(order("bad", lines=[]))
        self.assertEqual(invalid.status, OrderStatus.EXCEPTION)
        self.assertEqual(invalid.notes, ["invalid order"])

        no_stock_service = self.service(supplier("empty", 1, stock=0))
        unavailable = no_stock_service.handle_new_order(order("empty-order"))
        self.assertEqual(unavailable.status, OrderStatus.EXCEPTION)
        self.assertEqual(unavailable.notes, ["no supplier stock"])

    def test_supplier_tracking_shipment_and_delivery(self):
        supplier_adapter = supplier("supplier", 1)
        service = self.service(supplier_adapter)
        processed = service.handle_new_order(order())
        po_id = processed.fulfillment[0]["po_id"]
        supplier_adapter.ship(po_id, "TRACK-123")

        shipped = service.poll_supplier_tracking()[0]
        self.assertEqual(shipped.status, OrderStatus.SHIPPED)
        self.assertEqual(self.store.tracking_updates, [(processed.key, "TRACK-123")])
        delivered = service.handle_delivered(processed.key)
        self.assertEqual(delivered.status, OrderStatus.DELIVERED)

    def test_all_supplier_placements_failing_enters_exception(self):
        service = self.service(supplier("one", 1, fail_orders=True))
        processed = service.handle_new_order(order())
        self.assertEqual(processed.status, OrderStatus.EXCEPTION)
        self.assertEqual(processed.notes, ["all supplier orders failed"])

    def test_duplicate_sku_lines_use_quantity_specific_offers(self):
        small = MockSupplier(
            {"sku-1": {"cost": 1, "shipping_cost": 0, "stock": 4, "ship_days": 1}},
            supplier_id="small",
        )
        large = MockSupplier(
            {"sku-1": {"cost": 2, "shipping_cost": 0, "stock": 8, "ship_days": 1}},
            supplier_id="large",
        )
        processed = self.service(small, large).handle_new_order(
            order(
                "split-quantity",
                lines=[OrderLine("sku-1", 2, 10), OrderLine("sku-1", 8, 10)],
            )
        )
        self.assertEqual(processed.status, OrderStatus.ORDERED_FROM_SUPPLIER)
        self.assertEqual(
            [entry["supplier_id"] for entry in processed.fulfillment],
            ["small", "large"],
        )


class InventorySyncTests(unittest.TestCase):
    def test_sync_sums_supplier_stock_and_applies_buffer(self):
        suppliers = [supplier("one", 1, stock=3), supplier("two", 2, stock=2)]
        store = MockStore()
        self.assertEqual(sync_inventory(suppliers, [store], ["sku-1"], buffer=2), {"sku-1": 3})
        self.assertEqual(store.inventory["sku-1"], 3)
        self.assertEqual(sync_inventory(suppliers, [store], ["missing"], buffer=2), {"missing": 0})


if __name__ == "__main__":
    unittest.main()