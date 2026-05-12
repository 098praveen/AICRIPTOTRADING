"""
Data Aggregation and Feature Engineering Pipeline
"""
import asyncio
import logging
import ccxt.pro as ccxtpro
from core.events import EventBus, EventType, Event
from config.settings import settings

logger = logging.getLogger(__name__)

class DataPipeline:
    """
    Orchestrates real-time data collection via WebSockets.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        exchange_config = {'enableRateLimit': True}
        if settings.binance_api_key and settings.binance_api_secret:
            exchange_config['apiKey'] = settings.binance_api_key
            exchange_config['secret'] = settings.binance_api_secret
        self.exchange = ccxtpro.binance(exchange_config)
        self._running = False

    async def start(self, symbols: list):
        self._running = True
        logger.info(f"Starting Data Pipeline for symbols: {symbols}")
        
        # Start a listener task for each symbol
        tasks = [asyncio.create_task(self._listen_ticker(symbol)) for symbol in symbols]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Data Pipeline tasks cancelled.")

    async def _listen_ticker(self, symbol: str):
        while self._running:
            try:
                # ccxt.pro websocket stream
                ticker = await self.exchange.watch_ticker(symbol)
                
                # Publish the new market data to the event bus
                self.event_bus.publish(Event(
                    type=EventType.MARKET_DATA_EVENT,
                    payload={"symbol": symbol, "ticker": ticker}
                ))
            except ccxtpro.NetworkError as e:
                logger.error(f"Network error on {symbol}: {e}. Retrying in 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected error in pipeline for {symbol}: {e}")
                self.event_bus.publish(Event(
                    type=EventType.ERROR,
                    payload={"source": "DataPipeline", "error": str(e)}
                ))
                await asyncio.sleep(5)

    async def stop(self):
        self._running = False
        logger.info("Stopping Data Pipeline...")
        await self.exchange.close()
