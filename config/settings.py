from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    # Exchange API Keys
    binance_api_key: str = ""
    binance_api_secret: str = ""
    kucoin_api_key: str = ""
    kucoin_api_secret: str = ""

    # Database URLs
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/crypto_db"
    redis_url: str = "redis://localhost:6379/0"

    # App Settings
    environment: str = "development"
    log_level: str = "INFO"

    # Model Paths
    finbert_model: str = "ProsusAI/finbert"
    lstm_model: str = "models/crypto_lstm_model.h5"

    # Social APIs
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "crypto_bot/0.1"
    reddit_subreddit: str = "cryptocurrency"

    # Data sources
    news_sources: List[str] = [
        "https://cointelegraph.com/rss",
        "https://coindesk.com/arc/outboundfeeds/rss/",
        "https://decrypt.co/feed"
    ]

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

settings = Settings()
