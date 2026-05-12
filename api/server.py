import asyncio
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from core.events import EventBus, EventType
import os

logger = logging.getLogger(__name__)

app = FastAPI(title="AI Crypto Trading Bot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ui_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui")
os.makedirs(ui_path, exist_ok=True)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                disconnected.append(connection)
        for d in disconnected:
            self.disconnect(d)

manager = ConnectionManager()

@app.websocket("/ws/data")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

async def api_event_handler(event):
    if event.type == EventType.MARKET_DATA_EVENT:
        payload = event.payload
        await manager.broadcast(json.dumps({
            "type": "market_data",
            "data": {
                "symbol": payload.get("symbol"),
                "last": payload.get("ticker", {}).get("last"),
                "bid": payload.get("ticker", {}).get("bid"),
                "ask": payload.get("ticker", {}).get("ask"),
                "timestamp": payload.get("ticker", {}).get("timestamp")
            }
        }))
    else:
        await manager.broadcast(json.dumps({
            "type": "trade_event",
            "event": event.type.name if hasattr(event.type, 'name') else str(event.type),
            "data": event.payload
        }))

def setup_api_events(event_bus: EventBus):
    event_bus.subscribe(EventType.MARKET_DATA_EVENT, api_event_handler)
    event_bus.subscribe(EventType.SIGNAL_GENERATED, api_event_handler)
    event_bus.subscribe(EventType.ORDER_PLACED, api_event_handler)
    event_bus.subscribe(EventType.ORDER_FILLED, api_event_handler)
    event_bus.subscribe(EventType.PORTFOLIO_UPDATE, api_event_handler)
    logger.info("API events successfully hooked to EventBus")

# Mount static files last so it doesn't intercept specific API/WS routes
app.mount("/", StaticFiles(directory=ui_path, html=True), name="ui")
