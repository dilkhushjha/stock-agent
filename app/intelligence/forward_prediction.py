from datetime import timedelta
from statistics import mean, pstdev

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.pricing import MarketPricingEngine
from app.models.event import MarketEvent
from app.models.market_data import MarketData
from app.models.stock import Stock


class ForwardPredictionEngine:
    """Estimate forward return probabilities from recent market behaviour.

    This is intentionally a baseline predictor, not a claimed ML model. It is
    designed to produce auditable features that can later become training data.
    """

    HORIZONS = (1, 3, 7, 14, 30)
    LOOKBACK_DAYS = 180

    @classmethod
    def _prices(cls, db: Session, stock: Stock, end_time):
        start = end_time - timedelta(days=cls.LOOKBACK_DAYS)
        return db.scalars(
            select(MarketData)
            .where(
                MarketData.stock_id == stock.id,
                MarketData.timestamp >= start,
                MarketData.timestamp <= end_time,
            )
            .order_by(MarketData.timestamp.asc())
        ).all()

    @staticmethod
    def _return(current: float, future: float | None) -> float | None:
        if current is None or not current or future is None:
            return None
        return (future - current) / current * 100.0

    @classmethod
    def predict(cls, db: Session, event: MarketEvent, stock: Stock) -> dict:
        event_time = event.event_date or event.created_at
        if not event_time:
            return {"status": "INSUFFICIENT_DATA", "predictions": []}

        rows = cls._prices(db, stock, event_time)
        if len(rows) < 20:
            return {"status": "INSUFFICIENT_DATA", "predictions": []}

        current = rows[-1].close
        returns = []
        for previous, row in zip(rows, rows[1:]):
            if previous.close:
                returns.append((row.close - previous.close) / previous.close * 100.0)

        mean_return = mean(returns) if returns else 0.0
        volatility = pstdev(returns) if len(returns) > 1 else 1.0
        pricing = MarketPricingEngine.analyze(db, event, stock)
        pricing_bonus = 1.0 if pricing["state"] == "NOT_YET_PRICED_IN" else 0.5 if pricing["state"] in {"EARLY_REACTION", "PARTIALLY_PRICED_IN"} else 0.1
        event_sign = 1 if str(event.direction).upper() in {"POSITIVE", "UP", "BULLISH", "INCREASE"} else -1 if str(event.direction).upper() in {"NEGATIVE", "DOWN", "BEARISH", "DECREASE"} else 0
        confidence = float(event.confidence or 0.0)

        predictions = []
        for horizon in cls.HORIZONS:
            horizon_scale = min(2.0, horizon ** 0.5)
            expected = mean_return * horizon + event_sign * confidence * pricing_bonus * max(volatility, 0.5) * horizon_scale
            sigma = max(volatility * horizon_scale, 0.5)
            z = expected / sigma
            probability = 0.5 + 0.5 * max(-1.0, min(1.0, z / 2.0))
            if event_sign < 0:
                probability = 1.0 - probability

            predictions.append({
                "horizon_days": horizon,
                "expected_return_percent": round(expected, 2),
                "probability_of_direction": round(probability, 3),
                "expected_volatility_percent": round(sigma, 2),
                "data_points": len(rows),
            })

        return {
            "status": "OK",
            "symbol": stock.symbol,
            "event_id": event.id,
            "baseline_daily_return_percent": round(mean_return, 3),
            "baseline_daily_volatility_percent": round(volatility, 3),
            "pricing_state": pricing["state"],
            "predictions": predictions,
        }
