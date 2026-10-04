from collections import defaultdict, deque


class EventBus:
    def __init__(self):
        self._subscribers = defaultdict(list)
        self._queue = deque()
        self.dead_letter = []

    def subscribe(self, event_type, handler):
        self._subscribers[event_type].append(handler)

    def publish(self, event, payload=None):
        if isinstance(event, str):
            event = {"type": event, "data": payload}
        elif not isinstance(event, dict) or "type" not in event:
            raise ValueError("event must be a type string or a dict with a 'type' key")
        self._queue.append(event)

    def process(self):
        processed = 0
        while self._queue:
            event = self._queue.popleft()
            handlers = self._subscribers[event["type"]]
            for _ in range(3):
                try:
                    for handler in handlers:
                        handler(event)
                except Exception:
                    continue
                processed += 1
                break
            else:
                self.dead_letter.append(event)
        return processed