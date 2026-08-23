from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market_data import MarketData
from app.models.stock import Stock


@dataclass(frozen=True)
class ForwardReturnForecast:
    horizon_days: int
    expected_return_percent: float
    probability_positive: float
    expected_downside_percent: float
    confidence: float
    method: str


class ForwardReturnEngine:
    """Historical analogue baseline for forward-return estimation.

    This deliberately avoids claiming ML precision. It estimates what happened
    after comparable recent daily moves and reports the sample size/confidence.
    """

    LOOKBACK_DAYS = 252
    ANALOGUE_TOLERANCE = 0.01

    @classmethod
    def forecast(cls, db: Session, stock: Stock, as_of, horizons=(1, 3, 7, 14)) -> list[ForwardReturnForecast]:
        rows = db.scalars(
            select(MarketData)
            .where(
                MarketData.stock_id == stock.id,
                MarketData.timestamp <= as_of,
                MarketData.timestamp >= as_of - timedelta(days=cls.LOOKBACK_DAYS),
            )
            .order_by(MarketData.timestamp.asc())
        ).all()

        if len(rows) < 30:
            return []

        returns = []
        for previous, current in zip(rows, rows[1:]):
            if previous.close:
                returns.append((current.timestamp, (current.close - previous.close) / previous.close))

        recent_return = returns[-1][1]
        analogues = [item for item in returns[:-1] if abs(item[1] - recent_return) <= cls.ANALOGUE_TOLERANCE]

        forecasts = []
        for horizon in horizons:
            future_returns = []
            for timestamp, _ in analogues:
                target = timestamp + timedelta(days=horizon)
                start_close = cls._close_at_or_after(db, stock.id, timestamp)
                end_close = cls._close_at_or_after(db, stock.id, target)
                if start_close and end_close:
                    future_returns.append((end_close - start_close) / start_close)

            if not future_returns:
                continue

            expected = mean(future_returns)
            positive_probability = sum(value > 0 for value in future_returns) / len(future_returns)
            downside = mean(value for value in future_returns if value < 0) if any(value < 0 for value in future_returns) else 0.0
            confidence = min(0.90, 0.20 + 0.05 * min(len(future_returns), 14))

            forecasts.append(ForwardReturnForecast(
                horizon_days=horizon,
                expected_return_percent=round(expected * 100, 3),
                probability_positive=round(positive_probability, 4),
                expected_downside_percent=round(downside * 100, 3),
                confidence=round(confidence, 4),
                method="historical_analogue_baseline",
            ))

        return forecasts

    @staticmethod
    def _close_at_or_after(db: Session, stock_id: int, timestamp):
        return db.scalar(
            select(MarketData.close)
            .where(MarketData.stock_id == stock_id, MarketData.timestamp >= timestamp)
            .order_by(MarketData.timestamp.asc())
        )
