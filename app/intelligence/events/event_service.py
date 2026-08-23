from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import MarketEvent
from app.models.news import NewsArticle
from app.intelligence.events.event_extractor import (
    EventExtractor,
)


class EventIntelligenceService:

    def __init__(self):
        self.extractor = EventExtractor()

    def process_article(
        self,
        db: Session,
        article_id: int,
    ) -> dict:

        article = db.scalar(
            select(NewsArticle).where(
                NewsArticle.id == article_id
            )
        )

        if not article:
            raise ValueError(
                f"Article {article_id} not found."
            )

        existing_event = db.scalar(
            select(MarketEvent).where(
                MarketEvent.news_id == article_id
            )
        )

        if existing_event:
            return {
                "status": "already_processed",
                "event_id": existing_event.id,
            }

        result = self.extractor.extract(
            title=article.title,
            content=article.content or article.summary or "",
        )

        event = MarketEvent(
            news_id=article.id,
            event_date=(
                article.published_at
                or article.created_at
            ),
            event_type=result["event_type"],
            title=result["title"],
            description=result["description"],
            entity=result["entity"],
            sector=result["sector"],
            direction=result["direction"],
            impact=result["impact"],
            confidence=result["confidence"],
            time_horizon=result["time_horizon"],
        )

        db.add(event)

        article.is_processed = True

        db.commit()
        db.refresh(event)

        return {
            "status": "processed",
            "event_id": event.id,
            "event": result,
        }