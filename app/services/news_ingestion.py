from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.news_collector import NewsCollector
from app.intelligence.deduplication import (
    NewsDeduplicator,
)
from app.models.news import NewsArticle


class NewsIngestionService:

    def __init__(self):
        self.collector = NewsCollector()

    def run(
        self,
        db: Session,
    ) -> dict:

        raw_articles = self.collector.collect()

        unique_articles = (
            NewsDeduplicator.deduplicate(
                raw_articles
            )
        )

        inserted = 0
        skipped = 0

        for article in unique_articles:

            existing = db.scalar(
                select(NewsArticle).where(
                    NewsArticle.fingerprint
                    == article["fingerprint"]
                )
            )

            if existing:

                skipped += 1
                continue

            news = NewsArticle(
                title=article["title"],
                url=article["url"],
                content=article["content"],
                source=article["source"],
                published_at=article["published_at"],
                fingerprint=article["fingerprint"],
                is_processed=False,
            )

            db.add(news)

            inserted += 1

        db.commit()

        return {
            "sources": len(
                self.collector.sources
            ),
            "collected": len(raw_articles),
            "unique": len(unique_articles),
            "inserted": inserted,
            "skipped": skipped,
        }