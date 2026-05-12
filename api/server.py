import asyncio
import json
import logging
from collections import defaultdict, deque
from statistics import pstdev
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
portfolio = None

class MarketSentimentTracker:
    def __init__(self, history_size=120):
        self.prices = defaultdict(lambda: deque(maxlen=history_size))
        self.quotes = {}

    def update(self, symbol, ticker):
        if not symbol:
            return None

        try:
            price = float(ticker.get("last") or 0)
        except (TypeError, ValueError):
            price = 0.0

        if price > 0:
            self.prices[symbol].append(price)

        self.quotes[symbol] = {
            "last": price,
            "bid": ticker.get("bid"),
            "ask": ticker.get("ask"),
            "timestamp": ticker.get("timestamp")
        }
        return self.symbol_sentiment(symbol)

    def snapshot(self):
        return {
            symbol: self.symbol_sentiment(symbol)
            for symbol in sorted(self.quotes)
        }

    def symbol_sentiment(self, symbol):
        prices = list(self.prices[symbol])
        quote = self.quotes.get(symbol, {})
        price = quote.get("last") or (prices[-1] if prices else 0.0)
        returns = [
            (current - previous) / previous
            for previous, current in zip(prices, prices[1:])
            if previous
        ]

        trend = 0.0
        if len(prices) >= 6 and prices[0]:
            trend = (prices[-1] - prices[0]) / prices[0]

        recent_momentum = returns[-1] if returns else 0.0
        volatility = pstdev(returns[-30:]) if len(returns) >= 2 else 0.0
        spread_bps = self._spread_bps(quote)

        score = (trend * 7000) + (recent_momentum * 2500) - (volatility * 900)
        if score >= 7:
            label = "Bullish"
            tone = "positive"
        elif score <= -7:
            label = "Bearish"
            tone = "negative"
        elif volatility >= 0.0035:
            label = "Choppy"
            tone = "caution"
        else:
            label = "Neutral"
            tone = "neutral"

        if len(prices) < 8:
            label = "Warming Up"
            tone = "neutral"

        return {
            "symbol": symbol,
            "label": label,
            "tone": tone,
            "score": round(score, 2),
            "price": price,
            "trend_pct": round(trend * 100, 3),
            "momentum_pct": round(recent_momentum * 100, 3),
            "volatility_pct": round(volatility * 100, 3),
            "spread_bps": round(spread_bps, 2),
            "history": len(prices),
            "timestamp": quote.get("timestamp")
        }

    def _spread_bps(self, quote):
        try:
            bid = float(quote.get("bid") or 0)
            ask = float(quote.get("ask") or 0)
            midpoint = (bid + ask) / 2
        except (TypeError, ValueError):
            return 0.0

        if bid <= 0 or ask <= 0 or midpoint <= 0:
            return 0.0
        return ((ask - bid) / midpoint) * 10000

market_sentiment = MarketSentimentTracker()

class PortfolioResetRequest(BaseModel):
    balance: float

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

@app.get("/api/portfolio")
async def get_portfolio():
    if portfolio is None:
        raise HTTPException(status_code=503, detail="Portfolio is not ready")
    return _portfolio_payload(portfolio.snapshot())

@app.post("/api/portfolio/reset")
async def reset_portfolio(request: PortfolioResetRequest):
    if portfolio is None:
        raise HTTPException(status_code=503, detail="Portfolio is not ready")

    if request.balance <= 0:
        raise HTTPException(status_code=400, detail="Balance must be greater than 0")

    return _portfolio_payload(portfolio.reset(request.balance))

async def api_event_handler(event):
    if event.type == EventType.MARKET_DATA_EVENT:
        payload = event.payload
        sentiment = market_sentiment.update(payload.get("symbol"), payload.get("ticker", {}))
        await manager.broadcast(json.dumps({
            "type": "market_data",
            "data": {
                "symbol": payload.get("symbol"),
                "last": payload.get("ticker", {}).get("last"),
                "bid": payload.get("ticker", {}).get("bid"),
                "ask": payload.get("ticker", {}).get("ask"),
                "timestamp": payload.get("ticker", {}).get("timestamp"),
                "sentiment": sentiment
            }
        }))
    else:
        data = event.payload
        if event.type == EventType.PORTFOLIO_UPDATE and isinstance(data, dict):
            data = _portfolio_payload(data)
        await manager.broadcast(json.dumps({
            "type": "trade_event",
            "event": event.type.name if hasattr(event.type, 'name') else str(event.type),
            "data": data
        }))

def _portfolio_payload(snapshot):
    payload = dict(snapshot)
    payload["market_sentiment"] = market_sentiment.snapshot()
    return payload

def setup_api_events(event_bus: EventBus, portfolio_manager=None):
    global portfolio
    portfolio = portfolio_manager
    event_bus.subscribe(EventType.MARKET_DATA_EVENT, api_event_handler)
    event_bus.subscribe(EventType.SIGNAL_GENERATED, api_event_handler)
    event_bus.subscribe(EventType.ORDER_PLACED, api_event_handler)
    event_bus.subscribe(EventType.ORDER_FILLED, api_event_handler)
    event_bus.subscribe(EventType.PORTFOLIO_UPDATE, api_event_handler)
    logger.info("API events successfully hooked to EventBus")

# Mount static files last so it doesn't intercept specific API/WS routes
app.mount("/", StaticFiles(directory=ui_path, html=True), name="ui")
