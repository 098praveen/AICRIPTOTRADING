class PricePredictionModel:
    """
    Wrapper for price prediction models (LSTM, YOLOv5, etc.).
    """

    def __init__(self, model_type="lstm"):
        """
        Initialize the price prediction model.
        model_type: 'lstm', 'yolov5', etc.
        """
        self.model_type = model_type

    def predict(self, ohlcv_data):
        """
        Predict price movement given OHLCV data.
        Returns: dict with prediction and confidence.
        """
        rows = self._normalize_rows(ohlcv_data)
        if len(rows) < 5:
            return {
                "prediction": "neutral",
                "confidence": 0.5,
                "reason": "Not enough candles for a reliable technical estimate."
            }

        closes = [row["close"] for row in rows]
        short_window = closes[-5:]
        long_window = closes[-20:] if len(closes) >= 20 else closes
        short_ma = sum(short_window) / len(short_window)
        long_ma = sum(long_window) / len(long_window)
        momentum = (closes[-1] - closes[-5]) / closes[-5] if closes[-5] else 0.0
        volatility = self._volatility(closes[-20:])
        ma_edge = (short_ma - long_ma) / long_ma if long_ma else 0.0
        score = (ma_edge * 0.65) + (momentum * 0.35)

        if score > 0.0015:
            prediction = "up"
        elif score < -0.0015:
            prediction = "down"
        else:
            prediction = "neutral"

        confidence = 0.5 + min(abs(score) * 60, 0.35) - min(volatility * 12, 0.18)
        confidence = max(0.5, min(confidence, 0.88))
        return {
            "prediction": prediction,
            "confidence": round(confidence, 2),
            "score": round(score, 6),
            "momentum": round(momentum, 6),
            "volatility": round(volatility, 6),
            "short_ma": round(short_ma, 8),
            "long_ma": round(long_ma, 8)
        }

    def batch_predict(self, batch_ohlcv):
        """
        Predict price movement for a batch of OHLCV data.
        Returns: list of dicts with predictions.
        """
        return [self.predict(item) for item in batch_ohlcv]

    def _normalize_rows(self, ohlcv_data):
        if ohlcv_data is None:
            return []
        if hasattr(ohlcv_data, "to_dict"):
            ohlcv_data = ohlcv_data.to_dict("records")

        rows = []
        for item in ohlcv_data:
            if isinstance(item, (list, tuple)):
                close = item[4] if len(item) > 4 else None
            else:
                close = item.get("close", item.get("last"))
            try:
                close = float(close)
            except (TypeError, ValueError):
                continue
            if close > 0:
                rows.append({"close": close})
        return rows

    def _volatility(self, closes):
        returns = []
        for previous, current in zip(closes, closes[1:]):
            if previous:
                returns.append((current - previous) / previous)
        if len(returns) < 2:
            return 0.0
        mean_return = sum(returns) / len(returns)
        variance = sum((value - mean_return) ** 2 for value in returns) / len(returns)
        return variance ** 0.5
