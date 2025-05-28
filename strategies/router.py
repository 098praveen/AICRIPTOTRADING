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

    def route_trades(self, market_data, ai_signals):
        """
        Decide which strategies to activate based on AI signals and market data.
        Returns: list of trade decisions.
        """
        pass