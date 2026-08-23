from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import MarketEvent
from app.models.market_data import MarketData
from app.models.stock import Stock


class MarketPricingEngine:
    """Estimates how much of an event thesis the market has already priced in."""

    BASELINE_DAYS = 30
    MAX_REACTION_DAYS = 10

    @staticmethod
    def _sign(direction: str | None) -> int:
        value = str(direction or "").upper()
        if value in {"POSITIVE", "UP", "BULLISH", "INCREASE"}:
            return 1
        if value in {"NEGATIVE", "DOWN", "BEARISH", "DECREASE"}:
            return -1
        return 0

    @classmethod
    def analyze(cls, db: Session, event: MarketEvent, stock: Stock) -> dict:
        event_time = event.event_date or event.created_at
        if not event_time:
            return cls._empty()

        rows = db.scalars(
            select(MarketData)
            .where(
                MarketData.stock_id == stock.id,
                MarketData.timestamp >= event_time - timedelta(days=cls.BASELINE_DAYS),
                MarketData.timestamp <= event_time + timedelta(days=cls.MAX_REACTION_DAYS),
            )
            .order_by(MarketData.timestamp.asc())
        ).all()

        before = [r for r in rows if r.timestamp < event_time]
        after = [r for r in rows if r.timestamp >= event_time]
        if not before or not after:
            return cls._empty()

        reference = before[-1].close
        if not reference:
            return cls._empty()

        reaction = ((after[-1].close - reference) / reference) * 100
        aligned = reaction * cls._sign(event.direction)

        daily_returns = []
        previous = None
        for row in before[-21:]:
            if previous and previous.close:
                daily_returns.append(abs((row.close - previous.close) / previous.close * 100))
            previous = row

        baseline = sum(daily_returns) / len(daily_returns) if daily_returns else 1.0
        expected_reaction = max(2.0, min(15.0, baseline * 3.0))
        priced_in_ratio = max(0.0, min(1.0, aligned / expected_reaction))
        remaining_potential = round((1.0 - priced_in_ratio) * 100, 2)

        if priced_in_ratio >= 0.85:
            state = "MOSTLY_PRICED_IN"
        elif priced_in_ratio >= 0.50:
            state = "PARTIALLY_PRICED_IN"
        elif aligned > 0:
            state = "EARLY_REACTION"
        else:
            state = "NOT_YET_PRICED_IN"

        return {
            "reaction_percent": round(reaction, 2),
            "aligned_reaction_percent": round(aligned, 2),
            "baseline_daily_move_percent": round(baseline, 2),
            "expected_reaction_percent": round(expected_reaction, 2),
            "priced_in_ratio": round(priced_in_ratio, 3),
            "remaining_potential_percent": remaining_potential,
            "state": state,
            "data_points": len(rows),
        }

    @staticmethod
    def _empty() -> dict:
        return {
            "reaction_percent": None,
            "aligned_reaction_percent": None,
            "baseline_daily_move_percent": None,
            "expected_reaction_percent": None,
            "priced_in_ratio": None,
            "remaining_potential_percent": None,
            "state": "INSUFFICIENT_DATA",
            "data_points": 0,
        }
