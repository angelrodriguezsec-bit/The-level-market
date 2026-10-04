import base64
import hashlib
import hmac

from adapters.base import StoreAdapter
from core.models import Order, OrderLine


class ShopifyAdapter(StoreAdapter):
    def __init__(self, secret, store_id="shopify", tenant_id="default"):
        self.secret = secret.encode("utf-8") if isinstance(secret, str) else secret
        self.store_id = store_id
        self.tenant_id = tenant_id

    def verify_webhook(self, raw_body, signature):
        body = raw_body.encode("utf-8") if isinstance(raw_body, str) else raw_body
        expected = base64.b64encode(
            hmac.new(self.secret, body, hashlib.sha256).digest()
        ).decode("ascii")
        return isinstance(signature, str) and hmac.compare_digest(expected, signature)

    def parse_order(self, payload):
        lines = [
            OrderLine(
                sku=item.get("sku") or "",
                quantity=int(item["quantity"]),
                unit_price=float(item["price"]),
            )
            for item in payload.get("line_items", [])
        ]
        return Order(
            external_id=str(payload["id"]),
            store_id=self.store_id,
            customer_email=payload.get("email") or "",
            shipping_address=payload.get("shipping_address") or {},
            lines=lines,
            tenant_id=self.tenant_id,
        )

    def update_inventory(self, sku, quantity):
        raise NotImplementedError("TODO: update Shopify inventory")

    def update_price(self, sku, price):
        raise NotImplementedError("TODO: update Shopify price")

    def push_tracking(self, order, tracking):
        raise NotImplementedError("TODO: push Shopify fulfillment tracking")