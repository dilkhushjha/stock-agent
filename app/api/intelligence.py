from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.database import get_db
from app.models.event import MarketEvent
from app.models.news import NewsArticle

router = APIRouter(prefix="/intelligence", tags=["Intelligence"])


@router.get("/overview")
def intelligence_overview(
    limit: int = Query(12, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Return the small set of recent news/events that drive the dashboard thesis."""
    rows = db.execute(
        select(MarketEvent, NewsArticle)
        .join(NewsArticle, NewsArticle.id == MarketEvent.news_id)
        .order_by(MarketEvent.created_at.desc())
        .limit(limit)
    ).all()

    items = []
    for event, article in rows:
        items.append(
            {
                "event_id": event.id,
                "news_id": article.id,
                "category": event.event_type or "MARKET",
                "title": article.title,
                "source": article.source,
                "source_url": article.url,
                "published_at": (article.published_at or article.created_at).isoformat(),
                "summary": article.summary or event.description or "",
                "sector": event.sector,
                "entity": event.entity,
                "direction": event.direction,
                "impact": event.impact,
                "confidence": event.confidence,
                "horizon": event.time_horizon,
                "real_world_effect": event.description or _effect_text(event),
            }
        )

    categories = {}
    for item in items:
        categories[item["category"]] = categories.get(item["category"], 0) + 1

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "categories": categories,
        "news": items,
    }


def _effect_text(event: MarketEvent) -> str:
    direction = (event.direction or "").replace("_", " ").lower()
    impact = (event.impact or "").replace("_", " ").lower()
    sector = event.sector or event.entity or "the affected market"
    if direction or impact:
        return f"Potential {direction or 'market'} effect on {sector}; assessed impact is {impact or 'not yet classified'}."
    return f"Potential real-world impact identified for {sector}."
