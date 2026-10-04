import asyncio
import base64
import hashlib
import hmac
import json
import unittest

from fastapi import BackgroundTasks, HTTPException

from adapters.stores.mock_store import MockStore
from adapters.stores.shopify import ShopifyAdapter
from adapters.suppliers.mock_supplier import MockSupplier
from api.main import create_app
from core.db import Repository
from core.events import EventBus
from services.order_service import OrderService


class StubRequest:
    def __init__(self, body, signature=""):
        self._body = body
        self.headers = {"X-Shopify-Hmac-Sha256": signature}

    async def body(self):
        return self._body


def route(app, path, method="GET"):
    return next(
        item.endpoint
        for item in app.routes
        if getattr(item, "path", None) == path and method in item.methods
    )


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repository()
        self.shopify = ShopifyAdapter("test-secret", store_id="shop-1")
        self.store = MockStore("shop-1")
        self.supplier = MockSupplier(
            {
                "sku-1": {
                    "cost": 2,
                    "shipping_cost": 1,
                    "stock": 10,
                    "ship_days": 2,
                }
            },
            supplier_id="supplier-1",
        )
        self.service = OrderService(self.repo, [self.supplier], [self.store])
        self.bus = EventBus()
        self.app = create_app(self.service, self.shopify, self.bus, self.repo)

    def tearDown(self):
        self.repo.close()

    def signed_request(self, payload):
        body = json.dumps(payload).encode("utf-8")
        signature = base64.b64encode(
            hmac.new(b"test-secret", body, hashlib.sha256).digest()
        ).decode("ascii")
        return StubRequest(body, signature)

    def test_health_includes_dead_letter_count_and_orders_audit(self):
        self.bus.dead_letter.append({"type": "failed"})
        health = route(self.app, "/health")()
        self.assertEqual(health["dead_letter_count"], 1)
        self.assertEqual(route(self.app, "/orders")(status=None), [])
        self.assertEqual(route(self.app, "/audit")(), [])

    def test_webhook_verifies_publishes_background_and_is_idempotent(self):
        payload = {
            "id": 42,
            "email": "buyer@example.com",
            "shipping_address": {"country_code": "US"},
            "line_items": [{"sku": "sku-1", "quantity": 2, "price": "12.00"}],
        }
        endpoint = route(self.app, "/webhooks/shopify", method="POST")

        for _ in range(2):
            tasks = BackgroundTasks()
            response = asyncio.run(endpoint(self.signed_request(payload), tasks))
            self.assertEqual(response, {"status": "accepted"})
            asyncio.run(tasks())

        saved = self.repo.list_orders()
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].status.value, "ordered_from_supplier")
        self.assertEqual(self.supplier.catalog["sku-1"]["stock"], 8)
        self.assertEqual(len(route(self.app, "/orders")()), 1)
        self.assertEqual(len(route(self.app, "/audit")()), 4)

    def test_invalid_signature_returns_401(self):
        endpoint = route(self.app, "/webhooks/shopify", method="POST")
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                endpoint(
                    StubRequest(b"{}", "invalid"),
                    BackgroundTasks(),
                )
            )
        self.assertEqual(raised.exception.status_code, 401)

    def test_invalid_payload_returns_400(self):
        endpoint = route(self.app, "/webhooks/shopify", method="POST")
        body = b"not-json"
        signature = base64.b64encode(
            hmac.new(b"test-secret", body, hashlib.sha256).digest()
        ).decode("ascii")
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                endpoint(StubRequest(body, signature), BackgroundTasks())
            )
        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()