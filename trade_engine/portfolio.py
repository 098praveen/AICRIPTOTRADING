import logging
import json
import os
from core.events import EventBus, EventType, Event

logger = logging.getLogger(__name__)

class VirtualPortfolio:
    def __init__(
        self,
        initial_balance=10000.0,
        event_bus: EventBus = None,
        state_path=None,
        risk_per_trade=0.10,
        max_cash_per_trade=0.25,
    ):
        self.initial_balance = float(initial_balance)
        self.balance = self.initial_balance
        self.positions = {}
        self.event_bus = event_bus
        self.risk_per_trade = float(risk_per_trade)
        self.max_cash_per_trade = float(max_cash_per_trade)
        self.strategy_size_multipliers = {
            "scalping": 0.55,
            "day_trading": 1.0,
            "swing": 1.25
        }
        self.state_path = state_path or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "data", "virtual_portfolio_state.json")
        )
        self._load_state()
        if event_bus:
            event_bus.subscribe(EventType.SIGNAL_GENERATED, self.handle_signal)
            event_bus.subscribe(EventType.MARKET_DATA_EVENT, self.update_pnl)

    async def handle_signal(self, event: Event):
        signal = event.payload
        action = signal.get("action")
        symbol = signal.get("symbol")
        # Extract price from the incoming signal if available. If not, it will be updated later.
        price = signal.get("price") or signal.get("target_profit") or 1.0 # fallback
        try:
            price = float(price)
        except (TypeError, ValueError):
            return

        if not symbol or not price or price <= 0:
            return
        
        if action == "BUY":
            trade_amount = self._calculate_trade_amount(signal)
            if trade_amount > 0 and self.balance >= trade_amount:
                qty = trade_amount / price
                self.balance -= trade_amount
                
                pos = self.positions.get(symbol, {"qty": 0.0, "avg_price": 0.0, "current_price": price})
                total_cost = pos["qty"] * pos["avg_price"] + trade_amount
                previous_qty = pos["qty"]
                pos["qty"] += qty
                pos["avg_price"] = total_cost / pos["qty"]
                pos["current_price"] = price
                pos["stop_loss"] = self._weighted_exit_level(
                    pos.get("stop_loss"),
                    previous_qty,
                    signal.get("stop_loss"),
                    qty
                )
                pos["target_profit"] = self._weighted_exit_level(
                    pos.get("target_profit"),
                    previous_qty,
                    signal.get("target_profit"),
                    qty
                )
                pos["strategy"] = signal.get("strategy")
                self.positions[symbol] = pos
                
                self._publish_order_filled({
                    "symbol": symbol,
                    "action": action,
                    "price": price,
                    "qty": qty,
                    "balance": self.balance,
                    "notional": trade_amount,
                    "confidence": signal.get("confidence"),
                    "strategy": signal.get("strategy"),
                    "strategy_reason": signal.get("strategy_reason"),
                    "market_regime": signal.get("market_regime"),
                    "capital_tier": signal.get("capital_tier"),
                    "stop_loss": pos.get("stop_loss"),
                    "target_profit": pos.get("target_profit")
                })
                self._save_state()
        elif action == "SELL":
            self._close_position(symbol, price, signal, exit_reason="signal")
                
        self._publish_portfolio()

    async def update_pnl(self, event: Event):
        symbol = event.payload.get("symbol")
        last_price = event.payload.get("ticker", {}).get("last")
        if symbol in self.positions and last_price:
            try:
                last_price = float(last_price)
            except (TypeError, ValueError):
                return

            self.positions[symbol]["current_price"] = last_price
            pos = self.positions[symbol]
            stop_loss = pos.get("stop_loss")
            target_profit = pos.get("target_profit")
            exit_reason = None

            if stop_loss and last_price <= float(stop_loss):
                exit_reason = "stop_loss"
            elif target_profit and last_price >= float(target_profit):
                exit_reason = "target_profit"

            if exit_reason:
                self._close_position(symbol, last_price, {
                    "strategy": pos.get("strategy")
                }, exit_reason=exit_reason)

            self._save_state()
            self._publish_portfolio()

    def reset(self, initial_balance):
        self.initial_balance = float(initial_balance)
        self.balance = self.initial_balance
        self.positions = {}
        self._save_state()
        self._publish_portfolio()
        return self.snapshot()

    def _calculate_trade_amount(self, signal):
        explicit_notional = signal.get("max_notional")
        if explicit_notional is not None:
            try:
                explicit_notional = float(explicit_notional)
                if explicit_notional > 0:
                    return round(min(explicit_notional, self.balance), 8)
            except (TypeError, ValueError):
                pass

        confidence = signal.get("confidence", 0.75)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.75

        confidence = max(0.25, min(confidence, 1.0))
        size_multiplier = self.strategy_size_multipliers.get(signal.get("strategy"), 1.0)
        target_amount = self.initial_balance * self.risk_per_trade * confidence * size_multiplier
        cash_cap = self.balance * self.max_cash_per_trade
        trade_amount = min(target_amount, cash_cap, self.balance)

        return round(max(trade_amount, 0.0), 8)

    def _weighted_exit_level(self, existing_level, existing_qty, new_level, new_qty):
        try:
            new_level = float(new_level)
        except (TypeError, ValueError):
            return existing_level

        if new_level <= 0:
            return existing_level

        try:
            existing_level = float(existing_level or 0)
            existing_qty = float(existing_qty or 0)
            new_qty = float(new_qty or 0)
        except (TypeError, ValueError):
            return new_level

        if existing_level <= 0 or existing_qty <= 0:
            return new_level

        return ((existing_level * existing_qty) + (new_level * new_qty)) / (existing_qty + new_qty)

    def _close_position(self, symbol, price, signal=None, exit_reason="signal"):
        signal = signal or {}
        pos = self.positions.get(symbol)
        if not pos or pos["qty"] <= 0:
            return False

        qty_to_sell = pos["qty"]
        revenue = qty_to_sell * price
        cost_basis = pos["qty"] * pos["avg_price"]
        realized_pnl = revenue - cost_basis
        self.balance += revenue
        del self.positions[symbol]

        self._publish_order_filled({
            "symbol": symbol,
            "action": "SELL",
            "price": price,
            "qty": qty_to_sell,
            "balance": self.balance,
            "notional": revenue,
            "realized_pnl": realized_pnl,
            "exit_reason": exit_reason,
            "strategy": signal.get("strategy") or pos.get("strategy"),
            "strategy_reason": signal.get("strategy_reason"),
            "market_regime": signal.get("market_regime"),
            "capital_tier": signal.get("capital_tier")
        })
        self._save_state()
        return True

    def _publish_order_filled(self, payload):
        if self.event_bus:
            self.event_bus.publish(Event(EventType.ORDER_FILLED, payload))

    def snapshot(self):
        unrealized = 0.0
        portfolio_value = self.balance
        invested_value = 0.0
        
        for p in self.positions.values():
            curr_p = p.get("current_price", p["avg_price"])
            unrealized += (curr_p - p["avg_price"]) * p["qty"]
            position_value = curr_p * p["qty"]
            invested_value += position_value
            portfolio_value += position_value

        return {
            "initial_balance": self.initial_balance,
            "balance": self.balance,
            "unrealized_pnl": unrealized,
            "total_value": portfolio_value,
            "invested_value": invested_value,
            "risk_per_trade": self.risk_per_trade,
            "estimated_next_trade": min(
                self.initial_balance * self.risk_per_trade,
                self.balance * self.max_cash_per_trade,
                self.balance
            ),
            "positions": self.positions
        }

    def _publish_portfolio(self):
        if not self.event_bus:
            return

        self.event_bus.publish(Event(EventType.PORTFOLIO_UPDATE, self.snapshot()))

    def _load_state(self):
        if not os.path.exists(self.state_path):
            return
        if os.path.getsize(self.state_path) == 0:
            return

        try:
            with open(self.state_path, "r", encoding="utf-8") as state_file:
                state = json.load(state_file)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load virtual portfolio state: %s", exc)
            return

        self.initial_balance = float(state.get("initial_balance", self.initial_balance))
        self.balance = float(state.get("balance", self.balance))
        self.positions = state.get("positions", {}) or {}

    def _save_state(self):
        state = {
            "initial_balance": self.initial_balance,
            "balance": self.balance,
            "positions": self.positions
        }
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            with open(self.state_path, "w", encoding="utf-8") as state_file:
                json.dump(state, state_file, indent=2)
        except OSError as exc:
            logger.warning("Could not save virtual portfolio state: %s", exc)
