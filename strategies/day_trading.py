class DayTradingStrategy:
    """
    Implements day trading logic for intraday trades.
    """

    def generate_signal(self, data):
        """
        Generate a trading signal based on day trading criteria.
        Returns: dict with action, target profit, stop loss, and confidence.
        """
        price = float(data.get("last") or 0)
        context = data.get("market_context", {})
        if price <= 0:
            return None

        trend = context.get("trend", 0.0)
        volatility = context.get("volatility", 0.0)
        has_position = context.get("has_position", False)

        if trend > 0.002:
            action = "BUY"
        elif has_position and trend < -0.002:
            action = "SELL"
        else:
            return None

        trend_score = min(abs(trend) * 55, 0.22)
        volatility_penalty = min(max(volatility - 0.004, 0) * 35, 0.08)
        confidence = round(min(0.62 + trend_score - volatility_penalty, 0.9), 2)

        return {
            "action": action,
            "price": price,
            "target_profit": price * 1.012 if action == "BUY" else price * 0.988,
            "stop_loss": price * 0.993 if action == "BUY" else price * 1.007,
            "confidence": confidence,
            "timeframe": "intraday"
        }
