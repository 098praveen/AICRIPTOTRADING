import asyncio
from typing import Callable, Dict, List, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class EventType(Enum):
    MARKET_DATA_EVENT = "MARKET_DATA_EVENT"
    SIGNAL_GENERATED = "SIGNAL_GENERATED"
    ORDER_PLACED = "ORDER_PLACED"
    ORDER_FILLED = "ORDER_FILLED"
    ERROR = "ERROR"
    PORTFOLIO_UPDATE = "PORTFOLIO_UPDATE"

class Event:
    def __init__(self, type: EventType, payload: Any):
        self.type = type
        self.payload = payload

class EventBus:
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {
            event_type: [] for event_type in EventType
        }
        self._queue = asyncio.Queue()
        self._running = False

    def subscribe(self, event_type: EventType, callback: Callable):
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)

    def publish(self, event: Event):
        self._queue.put_nowait(event)

    async def start(self):
        self._running = True
        logger.info("Event Bus started.")
        while self._running:
            event = await self._queue.get()
            await self._process_event(event)
            self._queue.task_done()

    async def _process_event(self, event: Event):
        for callback in self._subscribers.get(event.type, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Error processing event {event.type} in callback {callback}: {e}")

    def stop(self):
        self._running = False
        logger.info("Event Bus stopped.")
