# File: monitoring/dashboard.py

"""
Trading Dashboard
Handles reporting, monitoring, and alerting.
"""
from datetime import datetime, timezone

from monitoring.performance import PerformanceTracker

class TradingDashboard:
    """
    Provides real-time and daily performance monitoring.
    """

    def __init__(self, performance_tracker=None):
        self.performance_tracker = performance_tracker or PerformanceTracker()
        self.last_health_check = None

    def generate_daily_report(self):
        """
        Generate and send a daily performance summary.
        """
        summary = self.performance_tracker.summary()
        daily_pnl = self.performance_tracker.calculate_daily_pnl()
        today = datetime.now(timezone.utc).date().isoformat()
        return {
            "date": today,
            "daily_pnl": daily_pnl.get(today, 0.0),
            "summary": summary,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

    def real_time_monitoring(self):
        """
        Monitor system health and trading activity in real time.
        """
        self.last_health_check = datetime.now(timezone.utc).isoformat()
        summary = self.performance_tracker.summary()
        return {
            "status": "ok",
            "checked_at": self.last_health_check,
            "trade_count": summary.get("trades", 0),
            "max_drawdown": summary.get("max_drawdown", 0.0),
            "sharpe_ratio": summary.get("sharpe_ratio", 0.0)
        }
