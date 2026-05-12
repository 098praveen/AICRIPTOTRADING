# File: monitoring/performance.py

"""
Performance Tracker
Tracks and analyzes trading performance metrics.
"""
from collections import defaultdict
from datetime import datetime, timezone
from math import sqrt

class PerformanceTracker:
    """
    Tracks trade statistics, win rate, drawdown, and other KPIs.
    """

    def __init__(self):
        self.trades = []
        self.equity_curve = []

    def record_trade(self, trade):
        """
        Record a completed trade for performance analysis.
        """
        if not trade:
            return
        recorded = dict(trade)
        recorded.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        self.trades.append(recorded)

    def record_equity(self, timestamp, equity):
        try:
            equity = float(equity)
        except (TypeError, ValueError):
            return
        self.equity_curve.append({
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "equity": equity
        })

    def calculate_daily_pnl(self):
        """
        Calculate profit and loss for the current day.
        """
        daily = defaultdict(float)
        for trade in self.trades:
            pnl = float(trade.get("realized_pnl") or trade.get("net_pnl") or 0)
            day = self._day_key(trade.get("timestamp"))
            daily[day] += pnl
        return dict(sorted(daily.items()))

    def calculate_win_rate(self):
        """
        Calculate the win rate of all recorded trades.
        """
        closed = [trade for trade in self.trades if self._trade_pnl(trade) is not None]
        if not closed:
            return 0.0
        wins = sum(1 for trade in closed if self._trade_pnl(trade) > 0)
        return wins / len(closed)

    def calculate_max_drawdown(self):
        """
        Calculate the maximum drawdown experienced.
        """
        if not self.equity_curve:
            return 0.0

        peak = self.equity_curve[0]["equity"]
        max_drawdown = 0.0
        for point in self.equity_curve:
            equity = point["equity"]
            peak = max(peak, equity)
            if peak > 0:
                max_drawdown = min(max_drawdown, (equity - peak) / peak)
        return abs(max_drawdown)

    def calculate_sharpe_ratio(self):
        """
        Calculate the Sharpe ratio for the strategy/portfolio.
        """
        returns = self._equity_returns()
        if len(returns) < 2:
            return 0.0

        mean_return = sum(returns) / len(returns)
        variance = sum((value - mean_return) ** 2 for value in returns) / (len(returns) - 1)
        std_dev = sqrt(variance)
        if std_dev == 0:
            return 0.0
        return (mean_return / std_dev) * sqrt(252)

    def calculate_profit_factor(self):
        wins = 0.0
        losses = 0.0
        for trade in self.trades:
            pnl = self._trade_pnl(trade)
            if pnl is None:
                continue
            if pnl > 0:
                wins += pnl
            elif pnl < 0:
                losses += abs(pnl)
        if losses == 0:
            return float("inf") if wins > 0 else 0.0
        return wins / losses

    def summary(self):
        closed = [trade for trade in self.trades if self._trade_pnl(trade) is not None]
        total_pnl = sum(self._trade_pnl(trade) or 0 for trade in closed)
        start_equity = self.equity_curve[0]["equity"] if self.equity_curve else 0.0
        end_equity = self.equity_curve[-1]["equity"] if self.equity_curve else start_equity
        total_return = ((end_equity - start_equity) / start_equity) if start_equity else 0.0
        return {
            "trades": len(closed),
            "total_pnl": round(total_pnl, 8),
            "total_return": round(total_return, 6),
            "win_rate": round(self.calculate_win_rate(), 4),
            "max_drawdown": round(self.calculate_max_drawdown(), 6),
            "sharpe_ratio": round(self.calculate_sharpe_ratio(), 4),
            "profit_factor": self.calculate_profit_factor(),
            "daily_pnl": self.calculate_daily_pnl()
        }

    def _equity_returns(self):
        returns = []
        for previous, current in zip(self.equity_curve, self.equity_curve[1:]):
            previous_equity = previous["equity"]
            if previous_equity:
                returns.append((current["equity"] - previous_equity) / previous_equity)
        return returns

    def _trade_pnl(self, trade):
        if "realized_pnl" in trade:
            return float(trade.get("realized_pnl") or 0)
        if "net_pnl" in trade:
            return float(trade.get("net_pnl") or 0)
        return None

    def _day_key(self, timestamp):
        if isinstance(timestamp, datetime):
            return timestamp.date().isoformat()
        if not timestamp:
            return datetime.now(timezone.utc).date().isoformat()
        return str(timestamp).split("T")[0].split(" ")[0]
