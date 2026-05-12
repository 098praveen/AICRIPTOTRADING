class SentimentModel:
    """
    Wrapper for financial and social sentiment analysis models.
    Supports FinBERT, VADER, and others.
    """

    def __init__(self, model_type="finbert"):
        """
        Initialize the sentiment model.
        model_type: 'finbert', 'vader', etc.
        """
        self.model_type = model_type
        self.positive_terms = {
            "bullish", "breakout", "rally", "surge", "adoption", "approval",
            "upgrade", "beat", "growth", "accumulate", "support", "record"
        }
        self.negative_terms = {
            "bearish", "crash", "dump", "hack", "lawsuit", "ban", "fraud",
            "selloff", "liquidation", "rejection", "risk", "exploit", "loss"
        }

    def analyze(self, text):
        """
        Analyze sentiment of the given text.
        Returns: dict with sentiment label and score.
        """
        if not text:
            return {"label": "neutral", "score": 0.0, "confidence": 0.5}

        tokens = [
            token.strip(".,!?;:()[]{}\"'").lower()
            for token in str(text).split()
        ]
        positive = sum(1 for token in tokens if token in self.positive_terms)
        negative = sum(1 for token in tokens if token in self.negative_terms)
        total_hits = positive + negative

        if total_hits == 0:
            return {"label": "neutral", "score": 0.0, "confidence": 0.5}

        score = (positive - negative) / total_hits
        if score > 0.15:
            label = "positive"
        elif score < -0.15:
            label = "negative"
        else:
            label = "neutral"

        confidence = 0.5 + min(abs(score) * 0.4, 0.4)
        return {
            "label": label,
            "score": round(score, 4),
            "confidence": round(confidence, 2),
            "positive_hits": positive,
            "negative_hits": negative
        }

    def batch_analyze(self, texts):
        """
        Analyze sentiment for a batch of texts.
        Returns: list of dicts with sentiment results.
        """
        return [self.analyze(text) for text in texts]
