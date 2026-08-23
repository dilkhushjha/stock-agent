from sqlalchemy import select

from app.data.database import SessionLocal
from app.intelligence.alert_engine import OpportunityAlertEngine
from app.intelligence.events.event_service import EventIntelligenceService
from app.intelligence.relevance import NewsRelevance
from app.models.news import NewsArticle
from app.services.news_ingestion import NewsIngestionService


class MarketAgent:
    """Runs the proactive event -> impact -> opportunity pipeline."""

    def __init__(self):
        self.news_service = NewsIngestionService()
        self.event_service = EventIntelligenceService()

    def run_news_cycle(self):
        print("\n[AGENT] Starting intelligence cycle...")
        db = SessionLocal()

        try:
            result = self.news_service.run(db)
            print(f"[AGENT] Collected: {result['collected']}")
            print(f"[AGENT] New articles: {result['inserted']}")

            result["opportunities"] = self.process_pending_news(db)
            return result

        except Exception as exc:
            print(f"[AGENT ERROR] {exc}")
            return {"error": str(exc)}
        finally:
            db.close()

    def process_pending_news(self, db):
        articles = db.scalars(
            select(NewsArticle)
            .where(NewsArticle.is_processed == False)
            .order_by(NewsArticle.published_at.desc())
            .limit(10)
        ).all()

        print(f"[AGENT] Pending articles: {len(articles)}")

        total_alerts = 0
        events_created = 0

        for article in articles:
            try:
                relevance = NewsRelevance.score(
                    {
                        "title": article.title,
                        "content": article.content or "",
                    }
                )

                if relevance < 2:
                    article.is_processed = True
                    continue

                event_result = self.event_service.process_article(
                    db=db,
                    article_id=article.id,
                )
                event_id = event_result["event_id"]

                if event_result.get("status") == "processed":
                    events_created += 1

                alert_result = OpportunityAlertEngine.generate_for_event(
                    db=db,
                    event_id=event_id,
                )
                created = alert_result.get("alerts_created", 0)
                total_alerts += created

                print(
                    f"[AGENT] {article.title[:80]} -> "
                    f"event={event_id}, alerts={created}"
                )

            except Exception as exc:
                print(f"[AGENT] Article processing failed: {exc}")

        db.commit()

        return {
            "articles_processed": len(articles),
            "events_created": events_created,
            "alerts_created": total_alerts,
        }
