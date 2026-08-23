from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.exposure import ExposureMappingService
from app.models.event import MarketEvent


class EventFusionEngine:
    """Groups multiple recent articles describing the same developing event."""

    WINDOW_DAYS = 7

    @classmethod
    def find_related(
        cls,
        db: Session,
        entity: str,
        event_type: str,
        sector: str | None = None,
    ) -> MarketEvent | None:
        normalized = ExposureMappingService.normalize_entity(entity or "")
        cutoff = datetime.utcnow() - timedelta(days=cls.WINDOW_DAYS)

        candidates = db.scalars(
            select(MarketEvent)
            .where(MarketEvent.created_at >= cutoff)
            .order_by(MarketEvent.created_at.desc())
        ).all()

        for candidate in candidates:
            candidate_entity = ExposureMappingService.normalize_entity(candidate.entity or "")
            if candidate_entity != normalized:
                continue
            if (candidate.event_type or "").upper() != (event_type or "").upper():
                continue
            if sector and candidate.sector and candidate.sector.upper() != sector.upper():
                continue
            return candidate

        return None

    @classmethod
    def merge(cls, db: Session, existing: MarketEvent, new_event: dict) -> MarketEvent:
        old_confidence = float(existing.confidence or 0.0)
        new_confidence = float(new_event.get("confidence") or 0.0)

        existing.confidence = round(
            min(1.0, old_confidence + (1.0 - old_confidence) * new_confidence * 0.5),
            4,
        )

        if new_event.get("impact") == "HIGH" or existing.impact == "HIGH":
            existing.impact = "HIGH"
        elif new_event.get("impact") == "MEDIUM" or existing.impact == "MEDIUM":
            existing.impact = "MEDIUM"

        if existing.direction == "NEUTRAL" and new_event.get("direction"):
            existing.direction = new_event["direction"]

        evidence = new_event.get("description") or new_event.get("summary") or "Additional evidence detected."
        existing.description = (
            f"{existing.description or existing.title} "
            f"Additional corroborating report: {evidence}"
        )[:5000]

        db.commit()
        db.refresh(existing)
        return existing
