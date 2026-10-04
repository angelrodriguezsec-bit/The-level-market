import atexit
import json
import os

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from adapters.stores.shopify import ShopifyAdapter
from adapters.suppliers.mock_supplier import MockSupplier
from core.db import Repository
from core.events import EventBus
from services.order_service import OrderService


def create_app(service, shopify, bus, repo):
    app = FastAPI()
    bus.subscribe(
        "order.received",
        lambda event: service.handle_new_order(event["data"]),
    )
    app.state.service = service
    app.state.shopify = shopify
    app.state.bus = bus
    app.state.repo = repo

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "dead_letter_count": len(bus.dead_letter),
        }

    @app.post("/webhooks/shopify", status_code=202)
    async def shopify_webhook(
        request: Request, background_tasks: BackgroundTasks
    ):
        raw_body = await request.body()
        signature = request.headers.get("X-Shopify-Hmac-Sha256", "")
        if not shopify.verify_webhook(raw_body, signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

        try:
            payload = json.loads(raw_body)
            order = shopify.parse_order(payload)
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail="Invalid Shopify order") from error

        bus.publish("order.received", order)
        background_tasks.add_task(bus.process)
        return {"status": "accepted"}

    @app.get("/orders")
    def get_orders(status: str | None = None):
        orders = repo.list_orders(status=status)
        return [order.to_dict() if hasattr(order, "to_dict") else order for order in orders]

    @app.get("/audit")
    def get_audit():
        return repo.audit()

    return app


def create_default_app():
    store_id = os.environ.get("SHOPIFY_STORE_ID", "shopify")
    tenant_id = os.environ.get("TENANT_ID", "default")
    shopify = ShopifyAdapter(
        os.environ.get("SHOPIFY_WEBHOOK_SECRET", "development-secret"),
        store_id=store_id,
        tenant_id=tenant_id,
    )
    catalog_json = os.environ.get("MOCK_SUPPLIER_CATALOG")
    catalog = (
        json.loads(catalog_json)
        if catalog_json
        else {
            "demo-sku": {
                "cost": 5.0,
                "shipping_cost": 1.0,
                "stock": 100,
                "ship_days": 2,
            }
        }
    )
    if not isinstance(catalog, dict):
        raise ValueError("MOCK_SUPPLIER_CATALOG must be a JSON object")

    supplier = MockSupplier(
        catalog,
        supplier_id=os.environ.get("MOCK_SUPPLIER_ID", "mock-supplier"),
    )
    repo = Repository(os.environ.get("DATABASE_PATH", ":memory:"))
    bus = EventBus()
    service = OrderService(repo, [supplier], [shopify])
    app = create_app(service, shopify, bus, repo)
    atexit.register(repo.close)
    return app


app = create_default_app()