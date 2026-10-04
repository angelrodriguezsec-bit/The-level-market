import json
import sqlite3
import threading
from datetime import datetime, timezone

from core.models import Order


class Repository:
    def __init__(self, database=":memory:"):
        self.connection = sqlite3.connect(database, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS orders (order_key TEXT PRIMARY KEY, status TEXT NOT NULL, data TEXT NOT NULL)"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL)"
        )
        self.connection.commit()

    def get_order(self, key):
        with self._lock:
            row = self.connection.execute(
                "SELECT data FROM orders WHERE order_key = ?", (key,)
            ).fetchone()
        return Order.from_dict(json.loads(row["data"])) if row else None

    def save_order(self, order):
        data = json.dumps(order.to_dict())
        with self._lock:
            self.connection.execute(
                "INSERT INTO orders (order_key, status, data) VALUES (?, ?, ?) "
                "ON CONFLICT(order_key) DO UPDATE SET status = excluded.status, data = excluded.data",
                (order.key, order.status.value, data),
            )
            self.connection.commit()

    def list_orders(self, status=None):
        with self._lock:
            if status is None:
                rows = self.connection.execute(
                    "SELECT data FROM orders ORDER BY rowid"
                ).fetchall()
            else:
                status_value = getattr(status, "value", status)
                rows = self.connection.execute(
                    "SELECT data FROM orders WHERE status = ? ORDER BY rowid",
                    (status_value,),
                ).fetchall()
        return [Order.from_dict(json.loads(row["data"])) for row in rows]

    def log(self, actor, action, detail):
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self.connection.execute(
                "INSERT INTO audit_log (timestamp, actor, action, detail) VALUES (?, ?, ?, ?)",
                (timestamp, actor, action, json.dumps(detail)),
            )
            self.connection.commit()

    def audit(self):
        with self._lock:
            rows = self.connection.execute(
                "SELECT timestamp, actor, action, detail FROM audit_log ORDER BY id"
            ).fetchall()
        return [
            {
                "timestamp": row["timestamp"],
                "actor": row["actor"],
                "action": row["action"],
                "detail": json.loads(row["detail"]),
            }
            for row in rows
        ]

    def close(self):
        with self._lock:
            self.connection.close()