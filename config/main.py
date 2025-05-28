"""
Main Entrypoint for AI Crypto Trading System
"""

from data.pipeline import DataPipeline
from models.sentiment import SentimentModel
from models.price_prediction import PricePredictionModel
from strategies.router import StrategyRouter
from trade_engine.trade_manager import AITradeManager
from monitoring.dashboard import TradingDashboard

def main():
    """
    Initializes and starts the AI Crypto Trading System.
    """
    # Initialize data pipeline
    data_pipeline = DataPipeline()

    # Initialize AI models
    sentiment_model = SentimentModel()
    price_model = PricePredictionModel()

    # Initialize strategy router
    strategy_router = StrategyRouter()

    # Initialize trade manager
    trade_manager = AITradeManager()

    # Initialize dashboard
    dashboard = TradingDashboard()

    # TODO: Implement system startup, scheduling, and main trading loop

    print("🚀 AI Crypto Trading System initialized. Ready to trade!")

if __name__ == "__main__":
    main()


