from collections import defaultdict, deque
from statistics import pstdev

from strategies.scalping import ScalpingStrategy
from strategies.swing import SwingStrategy
from strategies.day_trading import DayTradingStrategy
from strategies.arbitrage import ArbitrageStrategy

class StrategyRouter:
    """
    Routes trading signals to the appropriate strategy based on AI decision logic.
    """

    def __init__(self):
        self.strategies = {
            'scalping': ScalpingStrategy(),
            'swing': SwingStrategy(),
            'day_trading': DayTradingStrategy(),
            'arbitrage': ArbitrageStrategy()
        }
        self.price_history = defaultdict(lambda: deque(maxlen=80))

    def route_trades(self, market_data, portfolio_snapshot=None, ai_signals=None):
        """
        Decide which strategies to activate based on AI signals and market data.
        Returns: list of trade decisions.
        """
        if market_data.get("exchanges"):
            signal = self.strategies["arbitrage"].generate_signal(market_data)
            if signal:
                signal["strategy"] = "arbitrage"
                signal["strategy_reason"] = "Cross-exchange spread is large enough after fees and slippage."
                return [signal]

        context = self._build_market_context(market_data, portfolio_snapshot or {})
        selected_strategy, reason = self._select_strategy(context)
        if not selected_strategy:
            return []

        enriched_data = {
            **market_data,
            "market_context": context
        }
        signal = self.strategies[selected_strategy].generate_signal(enriched_data)
        if not signal:
            return []

        signal["symbol"] = market_data.get("symbol")
        signal["strategy"] = selected_strategy
        signal["strategy_reason"] = reason
        signal["market_regime"] = context["regime"]
        signal["capital_tier"] = context["capital_tier"]
        signal["spread_bps"] = context["spread_bps"]
        return [signal]

    def _build_market_context(self, market_data, portfolio_snapshot):
        symbol = market_data.get("symbol")
        price = float(market_data.get("last") or 0)
        bid = market_data.get("bid")
        ask = market_data.get("ask")
        history = self.price_history[symbol]
        if price > 0:
            history.append(price)

        returns = []
        prices = list(history)
        for previous, current in zip(prices, prices[1:]):
            if previous:
                returns.append((current - previous) / previous)

        trend = 0.0
        if len(prices) >= 6 and prices[0]:
            trend = (prices[-1] - prices[0]) / prices[0]

        last_return = returns[-1] if returns else 0.0
        volatility = pstdev(returns[-20:]) if len(returns) >= 2 else 0.0

        spread_bps = 0.0
        try:
            bid = float(bid or 0)
            ask = float(ask or 0)
            midpoint = (bid + ask) / 2
            if bid > 0 and ask > 0 and midpoint > 0:
                spread_bps = ((ask - bid) / midpoint) * 10000
        except (TypeError, ValueError):
            spread_bps = 0.0

        initial_balance = float(portfolio_snapshot.get("initial_balance") or 0)
        balance = float(portfolio_snapshot.get("balance") or 0)
        total_value = float(portfolio_snapshot.get("total_value") or balance)
        positions = portfolio_snapshot.get("positions") or {}
        position = positions.get(symbol) or {}
        has_position = float(position.get("qty") or 0) > 0
        cash_ratio = balance / initial_balance if initial_balance else 1.0

        if total_value < 1000:
            capital_tier = "micro"
        elif total_value < 10000:
            capital_tier = "small"
        elif total_value < 50000:
            capital_tier = "standard"
        else:
            capital_tier = "large"

        if volatility >= 0.004:
            regime = "volatile"
        elif abs(trend) >= 0.006:
            regime = "trending"
        elif abs(trend) >= 0.002:
            regime = "momentum"
        else:
            regime = "range"

        return {
            "symbol": symbol,
            "price": price,
            "trend": trend,
            "last_return": last_return,
            "volatility": volatility,
            "spread_bps": spread_bps,
            "initial_balance": initial_balance,
            "balance": balance,
            "total_value": total_value,
            "cash_ratio": cash_ratio,
            "capital_tier": capital_tier,
            "has_position": has_position,
            "history_length": len(history),
            "regime": regime
        }

    def _select_strategy(self, context):
        if context["price"] <= 0 or context["history_length"] < 6:
            return None, "Waiting for enough live price history."

        if context["balance"] <= 0 or context["cash_ratio"] < 0.03:
            if context["has_position"]:
                return "day_trading", "Capital is low; only managing open risk."
            return None, "Capital is too low to open a realistic new position."

        if context["spread_bps"] > 18:
            return None, "Spread is too wide for a realistic simulated fill."

        regime = context["regime"]
        capital_tier = context["capital_tier"]

        if regime == "volatile" and capital_tier in {"micro", "small", "standard"}:
            return "scalping", "High volatility with manageable capital favors fast scalps."

        if regime == "trending" and capital_tier in {"standard", "large"}:
            return "swing", "Stronger trend and deeper capital favor a swing setup."

        if regime in {"momentum", "trending"}:
            return "day_trading", "Intraday momentum is strong enough for a day trade."

        if regime == "range" and context["spread_bps"] <= 8 and abs(context["last_return"]) > 0.0004:
            return "scalping", "Range-bound market with tight spread favors scalping."

        return None, "No clean edge from current market conditions."
