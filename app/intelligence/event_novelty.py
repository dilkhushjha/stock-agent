from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.event import MarketEvent


@dataclass(frozen=True)
class NoveltyScore:
    novelty: float
    importance: float
    combined: float
    reason: str


class EventNoveltyEngine:
    """Scores whether an event is genuinely new and economically important."""

    LOOKBACK_DAYS = 30

    IMPACT_WEIGHT = {"LOW": 0.25, "MEDIUM": 0.60, "HIGH": 1.0}

    @classmethod
    def score(cls, db: Session, event: MarketEvent) -> NoveltyScore:
        event_time = event.event_date or event.created_at or datetime.utcnow()
        cutoff = event_time - timedelta(days=cls.LOOKBACK_DAYS)

        prior_count = db.scalar(
            select(func.count(MarketEvent.id)).where(
                MarketEvent.id != event.id,
                MarketEvent.event_type == event.event_type,
                MarketEvent.entity == event.entity,
                MarketEvent.created_at >= cutoff,
                MarketEvent.created_at <= event_time,
            )
        ) or 0

        novelty = max(0.10, min(1.0, 1.0 / (1.0 + 0.35 * prior_count)))
        impact = cls.IMPACT_WEIGHT.get((event.impact or "MEDIUM").upper(), 0.60)
        confidence = max(0.0, min(1.0, float(event.confidence or 0.0)))

        importance = min(1.0, 0.60 * impact + 0.40 * confidence)
        combined = min(1.0, 0.55 * novelty + 0.45 * importance)

        if prior_count == 0:
            reason = "No matching event for the entity/type was found in the 30-day lookback."
        else:
            reason = f"{prior_count} similar event(s) found in the 30-day lookback."

        return NoveltyScore(
            novelty=round(novelty, 4),
            importance=round(importance, 4),
            combined=round(combined, 4),
            reason=reason,
        )
