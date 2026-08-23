from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean, pstdev

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market_data import MarketData
from app.models.stock import Stock


@dataclass(frozen=True)
class MarketAwarenessScore:
    reaction: float
    volume_confirmation: float
    awareness: float
    status: str
    reason: str


class MarketAwarenessEngine:
    """Estimates how strongly the market has already reacted to an event.

    This is deliberately a baseline statistical signal. It does not claim to
    measure investor awareness directly; it measures observable price/volume
    reaction around the event timestamp.
    """

    BASELINE_DAYS = 20
    REACTION_WINDOW_HOURS = 24

    @staticmethod
    def _rows(db: Session, stock_id: int, start: datetime, end: datetime):
        return db.scalars(
            select(MarketData)
            .where(
                MarketData.stock_id == stock_id,
                MarketData.timestamp >= start,
                MarketData.timestamp <= end,
            )
            .order_by(MarketData.timestamp.asc())
        ).all()

    @classmethod
    def score(cls, db: Session, stock: Stock, event_time: datetime) -> MarketAwarenessScore:
        baseline_end = event_time - timedelta(hours=1)
        baseline_start = event_time - timedelta(days=cls.BASELINE_DAYS)
        reaction_end = event_time + timedelta(hours=cls.REACTION_WINDOW_HOURS)

        baseline = cls._rows(db, stock.id, baseline_start, baseline_end)
        reaction = cls._rows(db, stock.id, event_time, reaction_end)

        if len(baseline) < 5 or not reaction:
            return MarketAwarenessScore(
                reaction=0.0,
                volume_confirmation=0.0,
                awareness=0.0,
                status="INSUFFICIENT_DATA",
                reason="Not enough historical price/volume data to estimate market reaction.",
            )

        reference_close = baseline[-1].close
        reaction_close = reaction[-1].close
        price_move = abs((reaction_close - reference_close) / reference_close) if reference_close else 0.0

        returns = []
        for previous, current in zip(baseline, baseline[1:]):
            if previous.close:
                returns.append((current.close - previous.close) / previous.close)
        volatility = pstdev(returns) if len(returns) >= 2 else 0.0
        standardized_move = price_move / max(volatility, 0.005)
        reaction_score = min(1.0, standardized_move / 3.0)

        baseline_volumes = [row.volume for row in baseline if row.volume is not None and row.volume > 0]
        reaction_volumes = [row.volume for row in reaction if row.volume is not None and row.volume > 0]
        if baseline_volumes and reaction_volumes:
            normal_volume = mean(baseline_volumes)
            volume_ratio = mean(reaction_volumes) / normal_volume if normal_volume else 1.0
            volume_confirmation = min(1.0, max(0.0, (volume_ratio - 1.0) / 3.0))
        else:
            volume_confirmation = 0.0
            volume_ratio = None

        awareness = min(1.0, 0.65 * reaction_score + 0.35 * volume_confirmation)

        if awareness >= 0.70:
            status = "HIGH_AWARENESS"
        elif awareness >= 0.40:
            status = "PARTIAL_AWARENESS"
        else:
            status = "LOW_AWARENESS"

        reason = (
            f"Observed absolute price move={price_move * 100:.2f}% within 24h; "
            f"volume ratio={volume_ratio:.2f}x."
            if volume_ratio is not None
            else f"Observed absolute price move={price_move * 100:.2f}% within 24h; volume unavailable."
        )

        return MarketAwarenessScore(
            reaction=round(reaction_score, 4),
            volume_confirmation=round(volume_confirmation, 4),
            awareness=round(awareness, 4),
            status=status,
            reason=reason,
        )
