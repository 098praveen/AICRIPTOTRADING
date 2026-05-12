"""
Comprehensive Backtester
Simulates multi-strategy trading on historical data.
"""
from datetime import datetime, timezone

from monitoring.performance import PerformanceTracker
from strategies.router import StrategyRouter


class ComprehensiveBacktester:
    """
    Backtesting engine for all strategies and combined portfolio.

    Data can be a list of dicts or a pandas DataFrame with at least:
    timestamp, symbol, last/close. bid and ask are optional.
    """

    def __init__(self, initial_balance=10000.0, fee_bps=10.0, slippage_bps=5.0):
        self.strategies = ["scalping", "swing", "day_trading", "arbitrage"]
        self.initial_balance = float(initial_balance)
        self.fee_bps = float(fee_bps)
        self.slippage_bps = float(slippage_bps)
        self.results = {}

    def backtest_all_strategies(self, start_date=None, end_date=None, data=None):
        """
        Test each strategy and the router-combined portfolio over a historical period.
        """
        rows = self._normalize_rows(data)
        rows = self._filter_rows(rows, start_date, end_date)
        if not rows:
            return {
                "error": "No historical rows supplied. Pass data to backtest_all_strategies(..., data=rows).",
                "required_columns": ["timestamp", "symbol", "last or close"]
            }

        self.results = {
            "combined": self.simulate_combined_portfolio(rows)
        }
        for strategy_name in ["scalping", "day_trading", "swing"]:
            self.results[strategy_name] = self._simulate_strategy(rows, strategy_name)
        return self.results

    def simulate_combined_portfolio(self, data):
        """
        Simulate all strategies running together on the same portfolio.
        """
        return self._simulate_strategy(self._normalize_rows(data), strategy_name=None)

    def generate_performance_report(self):
        """
        Generate a comprehensive performance analysis.
        """
        if not self.results:
            return {"error": "Run a backtest before generating a report."}

        report = {}
        for name, result in self.results.items():
            report[name] = result.get("metrics", {})

        combined = report.get("combined", {})
        buy_and_hold = self.results.get("combined", {}).get("buy_and_hold_return")
        if buy_and_hold is not None:
            report["benchmark"] = {"buy_and_hold_return": buy_and_hold}
            report["edge_vs_buy_and_hold"] = round(combined.get("total_return", 0) - buy_and_hold, 6)

        return report

    def _simulate_strategy(self, rows, strategy_name=None):
        router = StrategyRouter()
        tracker = PerformanceTracker()
        cash = self.initial_balance
        positions = {}
        equity_curve = []
        first_prices = {}
        last_prices = {}

        for row in rows:
            symbol = row["symbol"]
            price = row["last"]
            timestamp = row.get("timestamp") or datetime.now(timezone.utc).isoformat()
            first_prices.setdefault(symbol, price)
            last_prices[symbol] = price

            self._mark_positions(positions, symbol, price)
            exits = self._check_exits(positions, symbol, price, timestamp)
            for exit_trade in exits:
                cash += exit_trade["notional"] - exit_trade["fee"]
                tracker.record_trade(exit_trade)

            snapshot = self._snapshot(cash, positions)
            market_data = {
                "symbol": symbol,
                "last": price,
                "bid": row.get("bid"),
                "ask": row.get("ask"),
                "timestamp": timestamp
            }
            signals = self._signals_for_row(router, strategy_name, market_data, snapshot)

            for signal in signals:
                action = signal.get("action")
                if action == "BUY":
                    trade, cash = self._open_position(cash, positions, signal, timestamp)
                    if trade:
                        tracker.record_trade(trade)
                elif action == "SELL":
                    trade = self._close_position(positions, symbol, price, timestamp, signal, "signal")
                    if trade:
                        cash += trade["notional"] - trade["fee"]
                        tracker.record_trade(trade)

            equity = self._snapshot(cash, positions)["total_value"]
            equity_curve.append({"timestamp": timestamp, "equity": equity})
            tracker.record_equity(timestamp, equity)

        metrics = tracker.summary()
        metrics["ending_value"] = round(equity_curve[-1]["equity"], 8) if equity_curve else self.initial_balance
        metrics["open_positions"] = len(positions)

        return {
            "metrics": metrics,
            "trades": tracker.trades,
            "equity_curve": equity_curve,
            "buy_and_hold_return": self._buy_and_hold_return(first_prices, last_prices)
        }

    def _signals_for_row(self, router, strategy_name, market_data, snapshot):
        if strategy_name is None:
            return router.route_trades(market_data, snapshot)

        context = router._build_market_context(market_data, snapshot)
        strategy = router.strategies[strategy_name]
        signal = strategy.generate_signal({**market_data, "market_context": context})
        if not signal:
            return []

        signal["symbol"] = market_data["symbol"]
        signal["strategy"] = strategy_name
        signal["market_regime"] = context["regime"]
        signal["capital_tier"] = context["capital_tier"]
        signal["spread_bps"] = context["spread_bps"]
        return [signal]

    def _open_position(self, cash, positions, signal, timestamp):
        symbol = signal.get("symbol")
        price = float(signal.get("price") or 0)
        if not symbol or price <= 0 or cash <= 0:
            return None, cash

        confidence = float(signal.get("confidence") or 0.6)
        notional = min(cash * 0.20 * confidence, cash)
        if notional <= 0:
            return None, cash

        fill_price = price * (1 + self.slippage_bps / 10000)
        fee = notional * (self.fee_bps / 10000)
        qty = (notional - fee) / fill_price
        pos = positions.get(symbol, {
            "qty": 0.0,
            "avg_price": 0.0,
            "current_price": fill_price,
            "strategy": signal.get("strategy")
        })
        total_cost = pos["qty"] * pos["avg_price"] + notional
        pos["qty"] += qty
        pos["avg_price"] = total_cost / pos["qty"]
        pos["current_price"] = fill_price
        pos["stop_loss"] = signal.get("stop_loss")
        pos["target_profit"] = signal.get("target_profit")
        pos["strategy"] = signal.get("strategy")
        positions[symbol] = pos

        return {
            "timestamp": timestamp,
            "symbol": symbol,
            "action": "BUY",
            "strategy": signal.get("strategy"),
            "price": fill_price,
            "qty": qty,
            "notional": notional,
            "fee": fee
        }, cash - notional

    def _close_position(self, positions, symbol, price, timestamp, signal=None, exit_reason="signal"):
        pos = positions.get(symbol)
        if not pos or pos["qty"] <= 0:
            return None

        fill_price = float(price) * (1 - self.slippage_bps / 10000)
        notional = pos["qty"] * fill_price
        fee = notional * (self.fee_bps / 10000)
        cost_basis = pos["qty"] * pos["avg_price"]
        realized_pnl = notional - fee - cost_basis
        del positions[symbol]

        return {
            "timestamp": timestamp,
            "symbol": symbol,
            "action": "SELL",
            "strategy": (signal or {}).get("strategy") or pos.get("strategy"),
            "price": fill_price,
            "qty": pos["qty"],
            "notional": notional,
            "fee": fee,
            "realized_pnl": realized_pnl,
            "exit_reason": exit_reason
        }

    def _check_exits(self, positions, symbol, price, timestamp):
        pos = positions.get(symbol)
        if not pos:
            return []

        stop_loss = pos.get("stop_loss")
        target_profit = pos.get("target_profit")
        if stop_loss and price <= float(stop_loss):
            return [self._close_position(positions, symbol, price, timestamp, None, "stop_loss")]
        if target_profit and price >= float(target_profit):
            return [self._close_position(positions, symbol, price, timestamp, None, "target_profit")]
        return []

    def _snapshot(self, cash, positions):
        total_value = cash
        for pos in positions.values():
            total_value += pos["qty"] * pos.get("current_price", pos["avg_price"])
        return {
            "initial_balance": self.initial_balance,
            "balance": cash,
            "total_value": total_value,
            "positions": positions
        }

    def _mark_positions(self, positions, symbol, price):
        if symbol in positions:
            positions[symbol]["current_price"] = price

    def _normalize_rows(self, data):
        if data is None:
            return []
        if hasattr(data, "to_dict"):
            data = data.to_dict("records")

        rows = []
        for item in data:
            price = item.get("last", item.get("close"))
            symbol = item.get("symbol")
            if price is None or not symbol:
                continue
            try:
                price = float(price)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue

            bid = item.get("bid")
            ask = item.get("ask")
            if bid is None:
                bid = price * 0.9995
            if ask is None:
                ask = price * 1.0005

            rows.append({
                "timestamp": item.get("timestamp") or item.get("date"),
                "symbol": symbol,
                "last": price,
                "bid": float(bid),
                "ask": float(ask)
            })

        return sorted(rows, key=lambda row: str(row.get("timestamp") or ""))

    def _filter_rows(self, rows, start_date, end_date):
        if not start_date and not end_date:
            return rows
        filtered = []
        for row in rows:
            ts = str(row.get("timestamp") or "")
            if start_date and ts < str(start_date):
                continue
            if end_date and ts > str(end_date):
                continue
            filtered.append(row)
        return filtered

    def _buy_and_hold_return(self, first_prices, last_prices):
        returns = []
        for symbol, first_price in first_prices.items():
            if first_price:
                returns.append((last_prices[symbol] - first_price) / first_price)
        if not returns:
            return 0.0
        return round(sum(returns) / len(returns), 6)
