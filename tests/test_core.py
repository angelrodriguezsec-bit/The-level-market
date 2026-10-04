import unittest
from decimal import Decimal

from core.db import Repository
from core.events import EventBus
from core.models import Order, OrderLine
from core.pricing import bounded_price, margin, min_price, sell_price
from core.state_machine import InvalidTransition, OrderStatus, transition


class StateMachineTests(unittest.TestCase):
    def test_transition_matrix(self):
        allowed = {
            OrderStatus.RECEIVED: {
                OrderStatus.VALIDATED,
                OrderStatus.EXCEPTION,
                OrderStatus.CANCELLED,
            },
            OrderStatus.VALIDATED: {
                OrderStatus.SOURCED,
                OrderStatus.EXCEPTION,
                OrderStatus.CANCELLED,
            },
            OrderStatus.SOURCED: {
                OrderStatus.ORDERED_FROM_SUPPLIER,
                OrderStatus.EXCEPTION,
                OrderStatus.CANCELLED,
            },
            OrderStatus.ORDERED_FROM_SUPPLIER: {
                OrderStatus.SHIPPED,
                OrderStatus.EXCEPTION,
                OrderStatus.CANCELLED,
            },
            OrderStatus.SHIPPED: {OrderStatus.DELIVERED, OrderStatus.EXCEPTION},
            OrderStatus.DELIVERED: {OrderStatus.REFUNDED},
            OrderStatus.EXCEPTION: {
                OrderStatus.VALIDATED,
                OrderStatus.SOURCED,
                OrderStatus.CANCELLED,
            },
            OrderStatus.CANCELLED: {OrderStatus.REFUNDED},
            OrderStatus.REFUNDED: set(),
        }
        self.assertEqual(set(allowed), set(OrderStatus))
        for current, targets in allowed.items():
            for target in OrderStatus:
                if target in targets:
                    self.assertEqual(transition(current, target), target)
                else:
                    with self.assertRaises(InvalidTransition):
                        transition(current, target)

        with self.assertRaises(InvalidTransition):
            transition("unknown", OrderStatus.RECEIVED)


class ModelTests(unittest.TestCase):
    def test_order_round_trip_and_independent_defaults(self):
        order = Order("ext-1", "store-1", "a@example.com", {}, [OrderLine("sku", 2, 9.5)])
        restored = Order.from_dict(order.to_dict())
        self.assertEqual(restored.key, "default:store-1:ext-1")
        self.assertEqual(restored.lines[0], OrderLine("sku", 2, 9.5))
        self.assertEqual(restored.status, OrderStatus.RECEIVED)
        self.assertIsNot(order.fulfillment, restored.fulfillment)


class PricingTests(unittest.TestCase):
    def test_pricing_rounding_and_bounds(self):
        floor = min_price(10, 2)
        self.assertEqual(floor, 15.96)
        self.assertGreaterEqual(margin(floor, 10, 2), 0.20)
        self.assertLess(margin(floor - 0.01, 10, 2), 0.20)
        self.assertEqual(Decimal(str(sell_price(10, 2))) % 1, Decimal("0.99"))
        self.assertAlmostEqual(margin(20, 10, 2), 0.356, places=3)
        self.assertEqual(bounded_price(100, 200, 0.1, 50), 110)
        self.assertEqual(bounded_price(100, 1, 0.1, 95), 95)
        self.assertEqual(bounded_price(100, 100, 0.1, 150), 150)


class EventBusTests(unittest.TestCase):
    def test_publish_process_and_dead_letter(self):
        bus = EventBus()
        received = []
        attempts = []

        bus.subscribe("ok", lambda event: received.append(event["data"]))

        def fail(event):
            attempts.append(event)
            raise RuntimeError("temporary failure")

        bus.subscribe("fail", fail)
        bus.publish("ok", 3)
        bus.publish({"type": "fail", "data": 4})
        self.assertEqual(bus.process(), 1)
        self.assertEqual(received, [3])
        self.assertEqual(len(attempts), 3)
        self.assertEqual(bus.dead_letter, [{"type": "fail", "data": 4}])


class RepositoryTests(unittest.TestCase):
    def test_order_upsert_filter_and_audit(self):
        repository = Repository()
        order = Order("ext-1", "store-1", "a@example.com", {}, [OrderLine("sku", 1, 5)])
        repository.save_order(order)
        self.assertEqual(repository.get_order(order.key).to_dict(), order.to_dict())
        order.status = OrderStatus.VALIDATED
        repository.save_order(order)
        self.assertEqual(len(repository.list_orders(OrderStatus.VALIDATED)), 1)
        self.assertEqual(len(repository.list_orders(OrderStatus.RECEIVED)), 0)
        repository.log("system", "validated", {"order": order.key})
        self.assertEqual(repository.audit()[0]["detail"], {"order": order.key})
        repository.close()


if __name__ == "__main__":
    unittest.main()