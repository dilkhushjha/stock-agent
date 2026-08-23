from sqlalchemy import select

from app.data.database import SessionLocal

from app.services.news_ingestion import (
    NewsIngestionService,
)

from app.models.news import NewsArticle

from app.intelligence.relevance import (
    NewsRelevance,
)

from app.intelligence.event_extractor import (
    EventExtractor,
)

from app.intelligence.signal_engine import (
    SignalEngine,
)


class MarketAgent:

    def __init__(self):

        self.news_service = (
            NewsIngestionService()
        )

        self.signal_engine = SignalEngine()

    def run_news_cycle(self):

        print(
            "\n[AGENT] Starting news cycle..."
        )

        db = SessionLocal()

        try:

            result = self.news_service.run(db)

            print(
                f"[AGENT] Collected: "
                f"{result['collected']}"
            )

            print(
                f"[AGENT] New articles: "
                f"{result['inserted']}"
            )

            self.process_pending_news(db)

            return result

        except Exception as exc:

            print(
                f"[AGENT ERROR] {exc}"
            )

            return {
                "error": str(exc)
            }

        finally:

            db.close()

    def process_pending_news(
        self,
        db,
    ):

        articles = db.scalars(
            select(NewsArticle)
            .where(
                NewsArticle.is_processed
                == False
            )
            .order_by(
                NewsArticle.published_at.desc()
            )
            .limit(10)
        ).all()

        print(
            f"[AGENT] Pending articles: "
            f"{len(articles)}"
        )

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

                print(
                    f"\n[AGENT] Processing:"
                    f" {article.title}"
                )

                event = EventExtractor.extract(
                    title=article.title,
                    content=article.content or "",
                )

                if event.get(
                    "is_market_relevant"
                ) is not True:

                    print(
                        "[AGENT] "
                        "Not market relevant."
                    )

                    article.is_processed = True

                    continue

                print(
                    "[AGENT] Event:"
                    f" {event.get('event_type')}"
                )

                print(
                    "[AGENT] Factor:"
                    f" {event.get('factor')}"
                )

                print(
                    "[AGENT] Direction:"
                    f" {event.get('direction')}"
                )

                factor = event.get(
                    "factor"
                )

                direction = event.get(
                    "direction"
                )

                if (
                    factor
                    and factor != "OTHER"
                    and direction
                    in ["UP", "DOWN"]
                ):

                    signals = (
                        self.signal_engine.generate(
                            db=db,
                            factor=factor,
                            direction=direction,
                        )
                    )

                    print(
                        "[AGENT] Signals generated:"
                        f" {len(signals)}"
                    )

                    for signal in signals[:5]:

                        print(
                            f"  "
                            f"{signal['symbol']} "
                            f"→ "
                            f"{signal['impact']} "
                            f"({signal['signal_score']})"
                        )

                article.is_processed = True

            except Exception as exc:

                print(
                    "[AGENT] Article processing "
                    f"failed: {exc}"
                )

        db.commit()
