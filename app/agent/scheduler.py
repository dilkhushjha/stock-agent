from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.agent.orchestrator import MarketAgent
from app.data.database import SessionLocal
from app.intelligence.evaluator import PredictionEvaluator
from app.intelligence.alert_engine import OpportunityAlertEngine
from app.intelligence.market_data_provider import YahooFinanceProvider
from app.intelligence.market_data_sync import MarketDataSyncService
from app.ml.prediction_engine import MLPredictionEngine
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
        run_ml_prediction_cycle,
        trigger="interval",
        minutes=15,
        id="ml_prediction_cycle",
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

    scheduler.add_job(
        run_ml_prediction_cycle,
        trigger="date",
        run_date=datetime.utcnow() + timedelta(seconds=5),
        id="ml_prediction_initial",
        replace_existing=True,
    )

    scheduler.start()
    print("[SCHEDULER] Market Agent started.")
    print("[SCHEDULER] News cycle: every 5 minutes.")
    print("[SCHEDULER] Market data sync: every 15 minutes (recent window).")
    print("[SCHEDULER] ML predictions: every 15 minutes.")
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
    """Refresh only recent OHLCV during live operation.

    Historical bootstrap is intentionally separate so the 24x7 scheduler does
    not repeatedly download hundreds of days for every stock.
    """
    print("[MARKET DATA] Synchronizing recent prices...")
    db = SessionLocal()
    try:
        service = MarketDataSyncService(provider=market_data_provider)
        result = service.sync(db=db, history_days=5, workers=8)
        print(
            "[MARKET DATA] "
            f"Processed={result['requested_stocks']} "
            f"Succeeded={result['successful_stocks']} "
            f"Failed={result['failed_stocks']} "
            f"Inserted={result['inserted_rows']}"
        )
    except Exception as exc:
        print(f"[MARKET DATA] Sync failed: {exc}")
    finally:
        db.close()


def run_ml_prediction_cycle():
    """Run the currently promoted model against the newest available data."""
    print("[ML] Running live prediction cycle...")
    db = SessionLocal()
    try:
        engine = MLPredictionEngine(db)
        engine.load_model_artifact()
        results = engine.predict_all()
        successful = len(results)
        print(f"[ML] Predictions completed: {successful}")
        return {"successful": successful, "results": results}
    except Exception as exc:
        print(f"[ML] Prediction cycle failed: {exc}")
        return {"successful": 0, "error": str(exc)}
    finally:
        db.close()


def refresh_opportunities():
    """Re-score recent events against the newest market data and predictions."""
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
