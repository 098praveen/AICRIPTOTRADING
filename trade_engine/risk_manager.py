"""
Risk Manager
Handles position sizing, stop loss, and portfolio risk controls.
"""

class RiskManager:
    """
    Manages risk for all trades and portfolio.
    """

    def __init__(
        self,
        portfolio_manager,
        max_risk_per_trade=0.01,
        max_cash_per_trade=0.20,
        max_symbol_exposure=0.35,
        min_confidence=0.55,
        max_spread_bps=18.0,
    ):
        """
        Initialize with a portfolio manager instance.
        """
        self.portfolio_manager = portfolio_manager
        self.max_risk_per_trade = float(max_risk_per_trade)
        self.max_cash_per_trade = float(max_cash_per_trade)
        self.max_symbol_exposure = float(max_symbol_exposure)
        self.min_confidence = float(min_confidence)
        self.max_spread_bps = float(max_spread_bps)

    def calculate_position_size(self, signal, market_conditions):
        """
        Calculate position size as a fraction of portfolio value.
        """
        snapshot = self.portfolio_manager.snapshot()
        total_value = float(snapshot.get("total_value") or 0)
        cash = float(snapshot.get("balance") or 0)
        if total_value <= 0 or cash <= 0:
            return 0.0

        try:
            price = float(signal.get("price") or market_conditions.get("price") or 0)
            stop_loss = float(signal.get("stop_loss") or 0)
            confidence = float(signal.get("confidence") or 0)
        except (TypeError, ValueError):
            return 0.0

        if price <= 0 or confidence < self.min_confidence:
            return 0.0

        action = signal.get("action")
        if action == "SELL":
            return 1.0

        if action == "ARBITRAGE":
            confidence_scale = min(max(confidence, 0.0), 1.0)
            return min(self.max_cash_per_trade * confidence_scale, cash / total_value)

        if action != "BUY":
            return 0.0

        stop_distance = abs(price - stop_loss) / price if stop_loss > 0 else 0.015
        stop_distance = max(stop_distance, 0.002)
        risk_budget = total_value * self.max_risk_per_trade
        risk_based_notional = risk_budget / stop_distance
        cash_cap = cash * self.max_cash_per_trade
        confidence_cap = cash_cap * min(max(confidence, 0.25), 1.0)
        notional = min(risk_based_notional, cash_cap, confidence_cap, cash)

        return max(0.0, min(notional / total_value, self.max_cash_per_trade))

    def apply_risk_filters(self, trade_decisions):
        """
        Filter or adjust trade decisions based on risk parameters.
        Returns: filtered list of trade decisions.
        """
        if not trade_decisions:
            return []

        snapshot = self.portfolio_manager.snapshot()
        total_value = float(snapshot.get("total_value") or 0)
        cash = float(snapshot.get("balance") or 0)
        positions = snapshot.get("positions") or {}
        filtered = []

        for decision in trade_decisions:
            symbol = decision.get("symbol")
            action = decision.get("action")
            context = {
                "price": decision.get("price"),
                "spread_bps": decision.get("spread_bps", decision.get("market_spread_bps", 0))
            }

            try:
                confidence = float(decision.get("confidence") or 0)
                spread_bps = float(context["spread_bps"] or 0)
                price = float(decision.get("price") or 0)
            except (TypeError, ValueError):
                continue

            if price <= 0 or confidence < self.min_confidence:
                continue

            if spread_bps > self.max_spread_bps:
                continue

            if action == "SELL":
                if symbol in positions and float(positions[symbol].get("qty") or 0) > 0:
                    approved = dict(decision)
                    approved["risk_approved"] = True
                    approved["risk_reason"] = "Exit approved for existing position."
                    filtered.append(approved)
                continue

            if action == "ARBITRAGE":
                size_fraction = self.calculate_position_size(decision, context)
                if size_fraction <= 0:
                    continue
                approved = dict(decision)
                approved["position_size_fraction"] = round(size_fraction, 6)
                approved["max_notional"] = round(total_value * size_fraction, 8)
                approved["risk_approved"] = True
                approved["risk_reason"] = "Arbitrage edge survives configured costs."
                filtered.append(approved)
                continue

            if action != "BUY" or not symbol or total_value <= 0 or cash <= 0:
                continue

            current_position = positions.get(symbol) or {}
            current_price = float(current_position.get("current_price") or current_position.get("avg_price") or price)
            current_exposure = float(current_position.get("qty") or 0) * current_price
            max_symbol_notional = total_value * self.max_symbol_exposure
            remaining_symbol_capacity = max(0.0, max_symbol_notional - current_exposure)
            size_fraction = self.calculate_position_size(decision, context)
            max_notional = min(total_value * size_fraction, remaining_symbol_capacity, cash)

            if max_notional <= 0:
                continue

            approved = dict(decision)
            approved["position_size_fraction"] = round(max_notional / total_value, 6)
            approved["max_notional"] = round(max_notional, 8)
            approved["risk_approved"] = True
            approved["risk_reason"] = "Position size capped by cash, stop risk, and symbol exposure."
            filtered.append(approved)

        return filtered

    def adjust_stop_loss(self, trade_id, new_stop):
        """
        Dynamically adjust stop loss for an open trade.
        """
        positions = getattr(self.portfolio_manager, "positions", {})
        if trade_id not in positions:
            return False

        try:
            new_stop = float(new_stop)
        except (TypeError, ValueError):
            return False

        if new_stop <= 0:
            return False

        positions[trade_id]["stop_loss"] = new_stop
        save_state = getattr(self.portfolio_manager, "_save_state", None)
        publish = getattr(self.portfolio_manager, "_publish_portfolio", None)
        if callable(save_state):
            save_state()
        if callable(publish):
            publish()
        return True
