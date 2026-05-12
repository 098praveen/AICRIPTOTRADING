class ArbitrageStrategy:
    """
    Detects simple cross-exchange arbitrage opportunities.

    Expected input shape:
    {
        "symbol": "BTC/USDT",
        "exchanges": {
            "binance": {"bid": 100.0, "ask": 100.1, "fee_bps": 10},
            "kucoin": {"bid": 101.0, "ask": 101.1, "fee_bps": 10}
        }
    }
    """

    def __init__(self, min_net_profit_bps=12.0, default_fee_bps=10.0, slippage_bps=4.0):
        self.min_net_profit_bps = float(min_net_profit_bps)
        self.default_fee_bps = float(default_fee_bps)
        self.slippage_bps = float(slippage_bps)

    def generate_signal(self, data):
        """
        Generate a paper-trading arbitrage signal.
        Returns None when the edge does not survive fees and slippage.
        """
        exchanges = data.get("exchanges") or {}
        symbol = data.get("symbol")
        if len(exchanges) < 2:
            return None

        quotes = []
        for name, quote in exchanges.items():
            try:
                bid = float(quote.get("bid") or 0)
                ask = float(quote.get("ask") or 0)
                fee_bps = float(quote.get("fee_bps", self.default_fee_bps))
            except (TypeError, ValueError):
                continue

            if bid > 0 and ask > 0 and ask >= bid:
                quotes.append({
                    "exchange": name,
                    "bid": bid,
                    "ask": ask,
                    "fee_bps": fee_bps
                })

        if len(quotes) < 2:
            return None

        buy_quote = min(quotes, key=lambda quote: quote["ask"])
        sell_quote = max(quotes, key=lambda quote: quote["bid"])
        if buy_quote["exchange"] == sell_quote["exchange"]:
            return None

        gross_bps = ((sell_quote["bid"] - buy_quote["ask"]) / buy_quote["ask"]) * 10000
        total_cost_bps = buy_quote["fee_bps"] + sell_quote["fee_bps"] + (2 * self.slippage_bps)
        net_profit_bps = gross_bps - total_cost_bps
        if net_profit_bps < self.min_net_profit_bps:
            return None

        confidence = min(0.95, 0.55 + (net_profit_bps / 100))
        return {
            "action": "ARBITRAGE",
            "symbol": symbol,
            "buy_exchange": buy_quote["exchange"],
            "sell_exchange": sell_quote["exchange"],
            "buy_price": buy_quote["ask"],
            "sell_price": sell_quote["bid"],
            "price": buy_quote["ask"],
            "gross_profit_bps": round(gross_bps, 2),
            "estimated_cost_bps": round(total_cost_bps, 2),
            "net_profit_bps": round(net_profit_bps, 2),
            "confidence": round(confidence, 2),
            "timeframe": "cross-exchange"
        }
