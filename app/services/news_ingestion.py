from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.news_collector import NewsCollector
from app.intelligence.deduplication import NewsDeduplicator
from app.models.news import NewsArticle


class NewsIngestionService:
    def __init__(self):
        self.collector = NewsCollector()

    def run(self, db: Session) -> dict:
        raw_articles = self.collector.collect()
        unique_articles = NewsDeduplicator.deduplicate(raw_articles)

        inserted = 0
        skipped = 0
        duplicate_urls = 0
        seen_urls = set()
        seen_fingerprints = set()

        for article in unique_articles:
            fingerprint = article.get("fingerprint")
            url = article.get("url")

            # Fingerprints catch the same story published through different URLs;
            # URLs catch feed refreshes where the collector generated a different
            # fingerprint for an already stored article.
            if (url and url in seen_urls) or (
                fingerprint and fingerprint in seen_fingerprints
            ):
                skipped += 1
                duplicate_urls += int(bool(url and url in seen_urls))
                continue

            existing = None
            if fingerprint:
                existing = db.scalar(
                    select(NewsArticle).where(NewsArticle.fingerprint == fingerprint)
                )
            if existing is None and url:
                existing = db.scalar(
                    select(NewsArticle).where(NewsArticle.url == url)
                )

            if existing:
                skipped += 1
                duplicate_urls += int(bool(url and existing.url == url))
                continue

            news = NewsArticle(
                title=article["title"],
                url=url,
                content=article.get("content"),
                source=article.get("source"),
                category=article.get("category"),
                is_international=bool(article.get("is_international", False)),
                published_at=article.get("published_at"),
                fingerprint=fingerprint,
                is_processed=False,
            )
            db.add(news)
            inserted += 1
            if url:
                seen_urls.add(url)
            if fingerprint:
                seen_fingerprints.add(fingerprint)

        db.commit()

        return {
            "sources": len(self.collector.sources),
            "collected": len(raw_articles),
            "unique": len(unique_articles),
            "inserted": inserted,
            "skipped": skipped,
            "duplicate_urls": duplicate_urls,
        }
