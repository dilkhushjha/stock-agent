from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.data.database import get_db
from app.data.news.news_ingestion import (
    NewsIngestionService,
)
from app.intelligence.events.event_service import (
    EventIntelligenceService,
)
from sqlalchemy import select

from app.models.news import NewsArticle
from app.data.news.sources import NEWS_SOURCES
from app.intelligence.exposure import (
    ExposureMappingService,
)
from app.intelligence.signals import SignalEngine
from app.services.news_ingestion import (
    NewsIngestionService,
)


router = APIRouter(
    prefix="/news",
    tags=["News"],
)


@router.post("/ingest")
def ingest_news(
    db: Session = Depends(get_db),
):

    results = []

    for source in NEWS_SOURCES:

        try:

            result = NewsIngestionService.ingest_feed(
                db=db,
                feed_url=source["url"],
                source=source["name"],
            )

            results.append(result)

        except Exception as exc:

            results.append(
                {
                    "source": source["name"],
                    "error": str(exc),
                }
            )

    return {
        "sources_processed": len(results),
        "results": results,
    }

@router.post("/process/{article_id}")
def process_article(
    article_id: int,
    db: Session = Depends(get_db),
):

    try:

        service = EventIntelligenceService()

        return service.process_article(
            db=db,
            article_id=article_id,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

@router.get("/latest")
def get_latest_news(
    limit: int = 10,
    db: Session = Depends(get_db),
):

    limit = min(max(limit, 1), 50)

    articles = db.scalars(
        select(NewsArticle)
        .order_by(
            NewsArticle.published_at.desc()
        )
        .limit(limit)
    ).all()

    return [
        {
            "id": article.id,
            "title": article.title,
            "source": article.source,
            "published_at": (
                article.published_at.isoformat()
                if article.published_at
                else None
            ),
            "url": article.url,
            "processed": article.is_processed,
        }
        for article in articles
    ]


@router.post("/events/{event_id}/map")
def map_event_exposure(
    event_id: int,
    db: Session = Depends(get_db),
):

    try:

        return ExposureMappingService.map_event(
            db=db,
            event_id=event_id,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

@router.post("/events/{event_id}/signal")
def generate_signal(
    event_id: int,
    db: Session = Depends(get_db),
):

    try:

        return SignalEngine.generate(
            db=db,
            event_id=event_id,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

@router.post("/collect")
def collect_news(
    db: Session = Depends(get_db),
):

    try:

        service = NewsIngestionService()

        return service.run(db)

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )