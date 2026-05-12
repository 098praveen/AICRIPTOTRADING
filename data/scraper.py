import logging
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from config.settings import settings
from models.sentiment import SentimentModel

logger = logging.getLogger(__name__)


class MultiSourceScraper:
    """
    Scrapes real-time data from news, social media, and other crypto sources.
    """

    def __init__(self):
        """
        Initialize API clients and scraping parameters.
        """
        self.news_sources = settings.news_sources
        self.sentiment_model = SentimentModel()
        self.timeout = 8

    def scrape_crypto_news(self):
        """
        Scrape latest crypto news from multiple sources.
        Returns: list of dicts with news data.
        """
        articles = []
        for source in self.news_sources:
            try:
                response = requests.get(source, timeout=self.timeout, headers={"User-Agent": "AICryptoTradingBot/0.1"})
                response.raise_for_status()
            except requests.RequestException as exc:
                logger.warning("Could not fetch news source %s: %s", source, exc)
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            items = soup.find_all("item")
            if not items:
                items = soup.find_all(["article", "item"])

            for item in items[:10]:
                title_node = item.find("title")
                link_node = item.find("link")
                published_node = item.find("pubDate") or item.find("published") or item.find("time")
                title = title_node.get_text(strip=True) if title_node else item.get_text(" ", strip=True)[:140]
                link = link_node.get_text(strip=True) if link_node else item.get("href")
                sentiment = self.sentiment_model.analyze(title)
                articles.append({
                    "source": source,
                    "title": title,
                    "url": link,
                    "published_at": published_node.get_text(strip=True) if published_node else None,
                    "sentiment": sentiment
                })

        return articles

    def scrape_social_sentiment(self):
        """
        Scrape Reddit/Twitter sentiment data.
        Returns: list of dicts with sentiment scores.
        """
        # Offline-safe baseline: score recent news headlines as a social/news proxy.
        articles = self.scrape_crypto_news()
        if not articles:
            return []

        scored = []
        for article in articles:
            scored.append({
                "source": article["source"],
                "text": article["title"],
                "sentiment": article["sentiment"],
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        return scored

    def get_fear_greed_index(self):
        """
        Fetch the current Fear & Greed Index.
        Returns: int or float value.
        """
        try:
            response = requests.get("https://api.alternative.me/fng/", timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
            value = payload.get("data", [{}])[0].get("value")
            return float(value)
        except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
            logger.warning("Could not fetch Fear & Greed Index: %s", exc)
            return None

    def scrape_all_sources(self):
        """
        Aggregate all data sources into a single dict.
        Returns: dict with all scraped data.
        """
        news = self.scrape_crypto_news()
        social = [
            {
                "source": article["source"],
                "text": article["title"],
                "sentiment": article["sentiment"]
            }
            for article in news
        ]
        fear_greed = self.get_fear_greed_index()
        sentiment_scores = [item["sentiment"]["score"] for item in social if item.get("sentiment")]
        aggregate_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "news": news,
            "social_sentiment": social,
            "fear_greed_index": fear_greed,
            "aggregate_sentiment": round(aggregate_sentiment, 4)
        }
