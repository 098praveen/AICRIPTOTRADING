import random

class ScalpingStrategy:
    """
    Implements high-frequency scalping logic for small, quick profits.
    """

    def generate_signal(self, data):
        """
        Generate a trading signal based on scalping criteria.
        Returns: dict with action, target profit, stop loss, and confidence.
        """
        # DUMMY LOGIC: 5% chance to generate a trade signal on each tick
        if random.random() < 0.05:
            action = random.choice(["BUY", "SELL"])
            price = data.get("last", 0)
            return {
                "action": action,
                "price": price,
                "target_profit": price * 1.01 if action == "BUY" else price * 0.99,
                "stop_loss": price * 0.995 if action == "BUY" else price * 1.005,
                "confidence": round(random.uniform(0.7, 0.99), 2)
            }
        return None