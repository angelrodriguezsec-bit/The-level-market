from dataclasses import asdict, dataclass, field

from core.state_machine import OrderStatus


@dataclass
class OrderLine:
    sku: str
    quantity: int
    unit_price: float


@dataclass
class SupplierOffer:
    supplier_id: str
    sku: str
    cost: float
    shipping_cost: float
    stock: int
    ship_days: int


@dataclass
class Order:
    external_id: str
    store_id: str
    customer_email: str
    shipping_address: dict
    lines: list[OrderLine]
    tenant_id: str = "default"
    status: OrderStatus = OrderStatus.RECEIVED
    fulfillment: list[dict] = field(default_factory=list)
    tracking: str | None = None
    notes: list = field(default_factory=list)

    @property
    def key(self):
        return f"{self.tenant_id}:{self.store_id}:{self.external_id}"

    def to_dict(self):
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data):
        values = dict(data)
        values["lines"] = [
            line if isinstance(line, OrderLine) else OrderLine(**line)
            for line in values["lines"]
        ]
        values["status"] = OrderStatus(values.get("status", OrderStatus.RECEIVED))
        return cls(**values)