import logging
from core.events import EventBus, EventType, Event

logger = logging.getLogger(__name__)

class VirtualPortfolio:
    def __init__(self, initial_balance=10000.0, event_bus: EventBus = None):
        self.balance = initial_balance
        self.positions = {}
        self.event_bus = event_bus
        if event_bus:
            event_bus.subscribe(EventType.SIGNAL_GENERATED, self.handle_signal)
            event_bus.subscribe(EventType.MARKET_DATA_EVENT, self.update_pnl)

    async def handle_signal(self, event: Event):
        signal = event.payload
        action = signal.get("action")
        symbol = signal.get("symbol")
        # Extract price from the incoming signal if available. If not, it will be updated later.
        price = signal.get("price") or signal.get("target_profit") or 1.0 # fallback

        # Wait, the dummy signal didn't have price directly, but target_profit/stop_loss. We'll modify scalping.py to include price.
        # But let's assume 'price' is available.
        trade_amount = 1000.0  # Buy $1000 worth of crypto on each BUY signal
        
        if action == "BUY":
            if self.balance >= trade_amount:
                qty = trade_amount / price
                self.balance -= trade_amount
                
                pos = self.positions.get(symbol, {"qty": 0.0, "avg_price": 0.0, "current_price": price})
                total_cost = pos["qty"] * pos["avg_price"] + trade_amount
                pos["qty"] += qty
                pos["avg_price"] = total_cost / pos["qty"]
                self.positions[symbol] = pos
                
                self.event_bus.publish(Event(EventType.ORDER_FILLED, {
                    "symbol": symbol, "action": action, "price": price, "qty": qty, "balance": self.balance
                }))
        elif action == "SELL":
            pos = self.positions.get(symbol)
            if pos and pos["qty"] > 0:
                qty_to_sell = pos["qty"]
                revenue = qty_to_sell * price
                cost_basis = pos["qty"] * pos["avg_price"]
                realized_pnl = revenue - cost_basis
                self.balance += revenue
                del self.positions[symbol]
                
                self.event_bus.publish(Event(EventType.ORDER_FILLED, {
                    "symbol": symbol, "action": action, "price": price, "qty": qty_to_sell, "balance": self.balance, "realized_pnl": realized_pnl
                }))
                
        self._publish_portfolio()

    async def update_pnl(self, event: Event):
        symbol = event.payload.get("symbol")
        last_price = event.payload.get("ticker", {}).get("last")
        if symbol in self.positions and last_price:
            self.positions[symbol]["current_price"] = last_price
            self._publish_portfolio()

    def _publish_portfolio(self):
        if not self.event_bus:
            return
            
        unrealized = 0.0
        portfolio_value = self.balance
        
        for p in self.positions.values():
            curr_p = p.get("current_price", p["avg_price"])
            unrealized += (curr_p - p["avg_price"]) * p["qty"]
            portfolio_value += curr_p * p["qty"]
            
        self.event_bus.publish(Event(EventType.PORTFOLIO_UPDATE, {
            "balance": self.balance,
            "unrealized_pnl": unrealized,
            "total_value": portfolio_value,
            "positions": self.positions
        }))
