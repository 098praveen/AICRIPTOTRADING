import asyncio
import logging
import sys
import os
import socket

# Add parent directory to path to allow absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.events import EventBus, EventType, Event
from config.settings import settings
from data.pipeline import DataPipeline
from api.server import app, setup_api_events
from strategies.router import StrategyRouter
from trade_engine.portfolio import VirtualPortfolio
from trade_engine.risk_manager import RiskManager
import uvicorn

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Globals for easy access in handlers
event_bus = EventBus()
router = StrategyRouter()
portfolio = VirtualPortfolio(initial_balance=10000.0, event_bus=event_bus, risk_per_trade=0.01)
risk_manager = RiskManager(portfolio)

def _available_port(preferred_port):
    for port in range(preferred_port, preferred_port + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"No free local port found from {preferred_port} to {preferred_port + 19}.")

async def market_data_handler(event: Event):
    """Handles incoming market data."""
    symbol = event.payload.get("symbol")
    ticker = event.payload.get("ticker", {})
    last_price = ticker.get('last')
    logger.info(f"Received Market Data for {symbol}: Last Price = {last_price}")
    
    if last_price is not None:
        market_data = {
            "symbol": symbol,
            "last": last_price,
            "bid": ticker.get("bid"),
            "ask": ticker.get("ask"),
            "timestamp": ticker.get("timestamp")
        }
        signals = router.route_trades(market_data, portfolio.snapshot())
        signals = risk_manager.apply_risk_filters(signals)
        for signal in signals:
            logger.info(f"Generated Signal: {signal}")
            event_bus.publish(Event(EventType.SIGNAL_GENERATED, signal))

async def main():
    logger.info("🚀 AI Crypto Trading System starting...")
    
    # Initialize Core Components
    data_pipeline = DataPipeline(event_bus)
    
    # Register handlers
    event_bus.subscribe(EventType.MARKET_DATA_EVENT, market_data_handler)
    
    # Start background tasks
    event_bus_task = asyncio.create_task(event_bus.start())
    symbols_to_trade = ["BTC/USDT", "ETH/USDT"]
    market_data_task = asyncio.create_task(data_pipeline.start(symbols_to_trade))
    
    # Set up API events
    setup_api_events(event_bus, portfolio)
    
    # Start UI / API server
    port = _available_port(int(os.getenv("PORT", "8000")))
    if port != 8000:
        logger.info("Port 8000 is busy; using http://127.0.0.1:%s instead.", port)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())
    
    try:
        # Keep the main loop running
        await asyncio.gather(event_bus_task, market_data_task, server_task)
    except asyncio.CancelledError:
        logger.info("Shutting down...")
    finally:
        await data_pipeline.stop()
        event_bus.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
