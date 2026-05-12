class SwingStrategy:
    """
    Implements swing trading logic for medium-term trades.
    """

    def generate_signal(self, data):
        """
        Generate a trading signal based on swing trading criteria.
        Returns: dict with action, target profit, stop loss, and confidence.
        """
        price = float(data.get("last") or 0)
        context = data.get("market_context", {})
        if price <= 0:
            return None

        trend = context.get("trend", 0.0)
        volatility = context.get("volatility", 0.0)
        has_position = context.get("has_position", False)

        if trend > 0.006 and volatility < 0.006:
            action = "BUY"
        elif has_position and trend < -0.005:
            action = "SELL"
        else:
            return None

        confidence = 0.66 + min(abs(trend) * 30, 0.2) - min(volatility * 18, 0.08)
        confidence = round(min(max(confidence, 0.55), 0.92), 2)

        return {
            "action": action,
            "price": price,
            "target_profit": price * 1.04 if action == "BUY" else price * 0.96,
            "stop_loss": price * 0.975 if action == "BUY" else price * 1.025,
            "confidence": confidence,
            "timeframe": "multi-day"
        }
