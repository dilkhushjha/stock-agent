from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.news.rss_collector import RSSNewsCollector
from app.models.news import NewsArticle


class NewsIngestionService:

    @staticmethod
    def ingest_feed(
        db: Session,
        feed_url: str,
        source: str,
        limit: int = 20,
    ) -> dict:

        articles = RSSNewsCollector.collect(
            feed_url=feed_url,
            source=source,
            limit=limit,
        )

        inserted = 0
        skipped = 0

        for article in articles:

            existing = db.scalar(
                select(NewsArticle).where(
                    NewsArticle.url
                    == article["url"]
                )
            )

            if existing:
                skipped += 1
                continue

            news_article = NewsArticle(
                title=article["title"],
                url=article["url"],
                source=article["source"],
                published_at=article["published_at"],
                summary=article["summary"],
                content=article["content"],
                language=article["language"],
            )

            db.add(news_article)

            inserted += 1

        db.commit()

        return {
            "source": source,
            "articles_found": len(articles),
            "articles_inserted": inserted,
            "articles_skipped": skipped,
        }