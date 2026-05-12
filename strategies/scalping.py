class ScalpingStrategy:
    """
    Implements high-frequency scalping logic for small, quick profits.
    """

    def generate_signal(self, data):
        """
        Generate a trading signal based on scalping criteria.
        Returns: dict with action, target profit, stop loss, and confidence.
        """
        price = float(data.get("last") or 0)
        context = data.get("market_context", {})
        if price <= 0:
            return None

        last_return = context.get("last_return", 0.0)
        trend = context.get("trend", 0.0)
        volatility = context.get("volatility", 0.0)
        has_position = context.get("has_position", False)

        if last_return > 0 and trend >= -0.001:
            action = "BUY"
        elif has_position and last_return < 0 and trend <= 0.001:
            action = "SELL"
        else:
            return None

        confidence = 0.58 + min(abs(last_return) * 120, 0.18) + min(volatility * 80, 0.12)
        confidence = round(min(confidence, 0.88), 2)

        return {
            "action": action,
            "price": price,
            "target_profit": price * 1.0035 if action == "BUY" else price * 0.9965,
            "stop_loss": price * 0.998 if action == "BUY" else price * 1.002,
            "confidence": confidence,
            "timeframe": "seconds-minutes"
        }
