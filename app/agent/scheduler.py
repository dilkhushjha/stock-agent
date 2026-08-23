from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.agent.orchestrator import MarketAgent
from app.data.database import SessionLocal
from app.intelligence.evaluator import PredictionEvaluator
from app.intelligence.alert_engine import OpportunityAlertEngine
from app.intelligence.market_data_provider import YahooFinanceProvider
from app.intelligence.market_data_sync import MarketDataSyncService
from app.models.event import MarketEvent


agent = MarketAgent()
scheduler = BackgroundScheduler()
market_data_provider = YahooFinanceProvider()


def start_scheduler():
    scheduler.add_job(
        agent.run_news_cycle,
        trigger="interval",
        minutes=5,
        id="news_cycle",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        run_market_data_sync,
        trigger="interval",
        minutes=15,
        id="market_data_sync",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        refresh_opportunities,
        trigger="interval",
        minutes=15,
        id="opportunity_refresh",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        run_evaluation,
        trigger="interval",
        minutes=30,
        id="prediction_evaluation",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    print("[SCHEDULER] Market Agent started.")
    print("[SCHEDULER] News cycle: every 5 minutes.")
    print("[SCHEDULER] Market data sync: every 15 minutes.")
    print("[SCHEDULER] Opportunity refresh: every 15 minutes.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)


def run_evaluation():
    print("[EVALUATOR] Checking predictions...")
    db = SessionLocal()
    try:
        result = PredictionEvaluator.evaluate(db)
        print(f"[EVALUATOR] Evaluated: {result['evaluated']}")
    except Exception as exc:
        print(f"[EVALUATOR] Failed: {exc}")
    finally:
        db.close()


def run_market_data_sync():
    print("[MARKET DATA] Synchronizing prices...")
    db = SessionLocal()
    try:
        result = MarketDataSyncService.sync(db=db, provider=market_data_provider)
        print(
            "[MARKET DATA] "
            f"Processed={result['stocks']} "
            f"Succeeded={result['successful']} "
            f"Failed={result['failed']}"
        )
    except Exception as exc:
        print(f"[MARKET DATA] Sync failed: {exc}")
    finally:
        db.close()


def refresh_opportunities():
    """Re-score recent events against the newest market data.

    This is the key to spontaneous updates: we do not retrain the model for
    every event. New prices, volume and pricing state are fed into the existing
    opportunity engine, which can raise, lower or stale an alert.
    """
    print("[OPPORTUNITY] Refreshing recent opportunities...")
    db = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(days=7)
        events = db.scalars(
            select(MarketEvent)
            .where(MarketEvent.created_at >= since)
            .order_by(MarketEvent.created_at.desc())
            .limit(100)
        ).all()

        created = updated = 0
        for event in events:
            try:
                result = OpportunityAlertEngine.generate_for_event(db, event.id)
                created += result.get("alerts_created", 0)
                updated += result.get("alerts_updated", 0)
            except Exception as exc:
                print(f"[OPPORTUNITY] Event {event.id} refresh failed: {exc}")

        print(f"[OPPORTUNITY] Events={len(events)} Created={created} Updated={updated}")
    except Exception as exc:
        print(f"[OPPORTUNITY] Refresh failed: {exc}")
    finally:
        db.close()
