"""
AI Trade Manager
Manages all open trades, dynamic stop losses, scaling, and trade lifecycle.
"""
from datetime import datetime, timezone

class AITradeManager:
    """
    AI-powered manager for open trades and portfolio.
    """

    def __init__(self, portfolio_manager=None, risk_manager=None):
        self.active_trades = {}
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager

    def manage_all_trades(self):
        """
        Continuously manage all open positions (stop loss, take profit, scaling).
        """
        decisions = {}
        positions = self._positions()
        for trade_id, trade in positions.items():
            decisions[trade_id] = self.evaluate_trade_continuation(trade, {
                "price": trade.get("current_price", trade.get("avg_price"))
            })
        return decisions

    def evaluate_trade_continuation(self, trade, new_data):
        """
        AI logic to decide whether to hold, adjust, or close a trade.
        Returns: dict with action and parameters.
        """
        try:
            avg_price = float(trade.get("avg_price") or 0)
            current_price = float(new_data.get("price") or trade.get("current_price") or avg_price)
            stop_loss = float(trade.get("stop_loss") or 0)
            target_profit = float(trade.get("target_profit") or 0)
        except (TypeError, ValueError):
            return {"action": "hold", "reason": "Missing trade pricing data."}

        if avg_price <= 0 or current_price <= 0:
            return {"action": "hold", "reason": "Invalid trade pricing data."}

        pnl_pct = (current_price - avg_price) / avg_price
        if stop_loss and current_price <= stop_loss:
            return {"action": "close", "reason": "stop_loss", "pnl_pct": pnl_pct}
        if target_profit and current_price >= target_profit:
            return {"action": "close", "reason": "target_profit", "pnl_pct": pnl_pct}

        if pnl_pct > 0.015:
            trailing_stop = current_price * 0.992
            if trailing_stop > stop_loss:
                return {
                    "action": "adjust_stop",
                    "new_stop": trailing_stop,
                    "reason": "Protecting profitable position.",
                    "pnl_pct": pnl_pct
                }

        if pnl_pct < -0.01:
            return {"action": "reduce_or_close", "percentage": 0.5, "reason": "Loss threshold reached.", "pnl_pct": pnl_pct}

        return {"action": "hold", "reason": "Trade remains inside planned risk range.", "pnl_pct": pnl_pct}

    def partial_close(self, trade_id, percentage):
        """
        Partially close a position (scale out).
        """
        positions = self._positions()
        trade = positions.get(trade_id)
        if not trade:
            return {"status": "rejected", "reason": "unknown trade"}

        try:
            percentage = float(percentage)
        except (TypeError, ValueError):
            return {"status": "rejected", "reason": "invalid percentage"}

        if percentage <= 0 or percentage > 1:
            return {"status": "rejected", "reason": "percentage must be between 0 and 1"}

        qty = float(trade.get("qty") or 0)
        close_qty = qty * percentage
        trade["qty"] = qty - close_qty
        trade["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.active_trades[trade_id] = trade
        return {
            "status": "scaled_out",
            "trade_id": trade_id,
            "closed_qty": close_qty,
            "remaining_qty": trade["qty"]
        }

    def close_position(self, trade_id, reason):
        """
        Close a trade and record the reason.
        """
        positions = self._positions()
        trade = positions.get(trade_id)
        if not trade:
            return {"status": "rejected", "reason": "unknown trade"}

        price = float(trade.get("current_price") or trade.get("avg_price") or 0)
        close_position = getattr(self.portfolio_manager, "_close_position", None)
        if callable(close_position) and price > 0:
            closed = close_position(trade_id, price, {"strategy": trade.get("strategy")}, reason)
            return {"status": "closed" if closed else "rejected", "trade_id": trade_id, "reason": reason}

        trade["closed_at"] = datetime.now(timezone.utc).isoformat()
        trade["close_reason"] = reason
        self.active_trades.pop(trade_id, None)
        return {"status": "closed", "trade_id": trade_id, "reason": reason}

    def adjust_stop_loss(self, trade_id, new_stop):
        """
        Adjust stop loss for a specific trade.
        """
        if self.risk_manager:
            return self.risk_manager.adjust_stop_loss(trade_id, new_stop)

        positions = self._positions()
        if trade_id not in positions:
            return False

        try:
            new_stop = float(new_stop)
        except (TypeError, ValueError):
            return False

        if new_stop <= 0:
            return False

        positions[trade_id]["stop_loss"] = new_stop
        return True

    def position_sizing_ai(self, signal, market_conditions):
        """
        AI determines optimal position size for a new trade.
        Returns: float (position size as fraction of portfolio).
        """
        if self.risk_manager:
            return self.risk_manager.calculate_position_size(signal, market_conditions)

        confidence = float(signal.get("confidence") or 0.5)
        volatility = float(market_conditions.get("volatility") or 0)
        base_size = 0.10 * max(0.25, min(confidence, 1.0))
        volatility_penalty = min(volatility * 10, 0.06)
        return max(0.0, min(base_size - volatility_penalty, 0.20))

    def _positions(self):
        if self.portfolio_manager and hasattr(self.portfolio_manager, "positions"):
            return self.portfolio_manager.positions
        return self.active_trades
