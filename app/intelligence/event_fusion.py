import re
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.exposure import ExposureMappingService
from app.models.event import MarketEvent
from app.models.news import NewsArticle


class EventFusionEngine:
    """Groups multiple reports describing the same developing event."""

    WINDOW_DAYS = 7
    SIMILARITY_THRESHOLD = 0.30

    @staticmethod
    def _tokens(text: str | None) -> set[str]:
        words = re.findall(r"[a-z0-9]{3,}", (text or "").lower())
        stop = {"the", "and", "for", "with", "from", "that", "this", "has", "have", "into", "after", "over", "will", "could", "would", "about", "india", "says", "said", "its", "are", "was", "were", "been", "their"}
        return set(words) - stop

    @classmethod
    def _text_similarity(cls, left: MarketEvent, right: MarketEvent) -> float:
        a = cls._tokens(" ".join(filter(None, [left.title, left.description])))
        b = cls._tokens(" ".join(filter(None, [right.title, right.description])))
        if not a or not b:
            return 1.0
        return len(a & b) / len(a | b)

    @classmethod
    def find_related(cls, db: Session, entity: str, event_type: str, sector: str | None = None) -> MarketEvent | None:
        normalized = ExposureMappingService.normalize_entity(entity or "")
        cutoff = datetime.utcnow() - timedelta(days=cls.WINDOW_DAYS)
        candidates = db.scalars(
            select(MarketEvent).where(MarketEvent.created_at >= cutoff).order_by(MarketEvent.created_at.desc())
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
        existing.confidence = round(min(1.0, old_confidence + (1.0 - old_confidence) * new_confidence * 0.5), 4)

        if new_event.get("impact") == "HIGH" or existing.impact == "HIGH":
            existing.impact = "HIGH"
        elif new_event.get("impact") == "MEDIUM" or existing.impact == "MEDIUM":
            existing.impact = "MEDIUM"

        if existing.direction == "NEUTRAL" and new_event.get("direction"):
            existing.direction = new_event["direction"]

        evidence = new_event.get("description") or new_event.get("summary") or "Additional evidence detected."
        existing.description = f"{existing.description or existing.title} Additional corroborating report: {evidence}"[:5000]
        db.commit()
        db.refresh(existing)
        return existing

    @classmethod
    def fuse_event(cls, db: Session, event_id: int) -> dict:
        event = db.scalar(select(MarketEvent).where(MarketEvent.id == event_id))
        if not event:
            raise ValueError(f"Event {event_id} not found.")

        anchor = event.event_date or event.created_at
        start = anchor - timedelta(hours=48)
        end = anchor + timedelta(hours=48)
        candidates = db.scalars(select(MarketEvent).where(
            MarketEvent.id != event.id,
            MarketEvent.event_type == event.event_type,
            MarketEvent.event_date >= start,
            MarketEvent.event_date <= end,
        )).all()

        related = []
        for candidate in candidates:
            if ExposureMappingService.normalize_entity(candidate.entity or "") != ExposureMappingService.normalize_entity(event.entity or ""):
                continue
            if event.direction and candidate.direction and event.direction != candidate.direction:
                continue
            if cls._text_similarity(event, candidate) >= cls.SIMILARITY_THRESHOLD:
                related.append(candidate)

        members = [event, *related]
        news_ids = {member.news_id for member in members}
        articles = db.scalars(select(NewsArticle).where(NewsArticle.id.in_(news_ids))).all() if news_ids else []
        sources = sorted({article.source for article in articles if article.source})
        base = max((float(member.confidence or 0.0) for member in members), default=0.0)
        reinforcement = min(0.20, max(0, len(sources) - 1) * 0.05)
        event.confidence = round(min(1.0, base + reinforcement), 4)
        db.commit()

        return {
            "event_id": event.id,
            "related_event_ids": [item.id for item in related],
            "article_count": len(news_ids),
            "independent_source_count": max(1, len(sources)),
            "sources": sources,
            "confidence": event.confidence,
        }
