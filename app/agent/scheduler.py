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
from app.ml.train import train as train_model
from app.models.event import MarketEvent


agent = MarketAgent()
scheduler = BackgroundScheduler()
market_data_provider = YahooFinanceProvider()


def start_scheduler():
    scheduler.add_job(agent.run_news_cycle, trigger="interval", minutes=5, id="news_cycle", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(run_live_cycle, trigger="interval", minutes=15, id="live_intelligence_cycle", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(run_evaluation, trigger="interval", minutes=30, id="prediction_evaluation", replace_existing=True, max_instances=1, coalesce=True)

    # Re-train once per week from the accumulated broad-universe history.
    # Predictions remain frequent; training is intentionally much less frequent.
    scheduler.add_job(retrain_model_cycle, trigger="interval", days=7, id="model_retraining", replace_existing=True, max_instances=1, coalesce=True)

    scheduler.add_job(agent.run_news_cycle, trigger="date", run_date=datetime.utcnow() + timedelta(seconds=5), id="news_initial", replace_existing=True)
    scheduler.add_job(run_live_cycle, trigger="date", run_date=datetime.utcnow() + timedelta(seconds=15), id="live_initial", replace_existing=True)

    scheduler.start()
    print("[SCHEDULER] Market Agent started.")
    print("[SCHEDULER] News ingestion + event analysis: every 5 minutes.")
    print("[SCHEDULER] Full market intelligence cycle: every 15 minutes.")
    print("[SCHEDULER] Prediction evaluation: every 30 minutes.")
    print("[SCHEDULER] Model retraining: every 7 days.")


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


def retrain_model_cycle():
    """Re-train from accumulated broad-universe history once per week."""
    print("[RETRAIN] Starting recurrent model training...")
    try:
        result = train_model()
        print(
            "[RETRAIN] Complete: "
            f"stocks={result['training_stocks']}, "
            f"rows={result['training_rows']}, "
            f"version={result['model_version']}"
        )
        return result
    except Exception as exc:
        # Never take the live prediction service down because a retraining run failed.
        # The previous model artifact remains available to the prediction engine.
        print(f"[RETRAIN] Failed; keeping previous model artifact: {exc}")
        return {"status": "failed", "error": str(exc)}


def run_market_data_sync():
    """Refresh only recent OHLCV during live operation."""
    print("[MARKET DATA] Synchronizing recent prices...")
    db = SessionLocal()
    try:
        service = MarketDataSyncService(provider=market_data_provider)
        result = service.sync(db=db, history_days=5, workers=2)
        print(
            "[MARKET DATA] "
            f"Processed={result['requested_stocks']} "
            f"Succeeded={result['successful_stocks']} "
            f"Failed={result['failed_stocks']} "
            f"Inserted={result['inserted_rows']}"
        )
        return result
    except Exception as exc:
        print(f"[MARKET DATA] Sync failed: {exc}")
        return {"successful_stocks": 0, "error": str(exc)}
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
        events = db.scalars(select(MarketEvent).where(MarketEvent.created_at >= since).order_by(MarketEvent.created_at.desc()).limit(100)).all()
        created = updated = 0
        for event in events:
            try:
                result = OpportunityAlertEngine.generate_for_event(db, event.id)
                created += result.get("alerts_created", 0)
                updated += result.get("alerts_updated", 0)
            except Exception as exc:
                print(f"[OPPORTUNITY] Event {event.id} refresh failed: {exc}")
        print(f"[OPPORTUNITY] Events={len(events)} Created={created} Updated={updated}")
        return {"events": len(events), "alerts_created": created, "alerts_updated": updated}
    except Exception as exc:
        print(f"[OPPORTUNITY] Refresh failed: {exc}")
        return {"events": 0, "error": str(exc)}
    finally:
        db.close()


def run_live_cycle():
    """Run the complete recurring market-intelligence pipeline in order."""
    print("\n[LIVE CYCLE] Starting full intelligence cycle...")
    started = datetime.utcnow()
    market = run_market_data_sync()
    predictions = run_ml_prediction_cycle()
    opportunities = refresh_opportunities()
    elapsed = (datetime.utcnow() - started).total_seconds()
    print(
        "[LIVE CYCLE] Complete: "
        f"market_success={market.get('successful_stocks', 0)}, "
        f"predictions={predictions.get('successful', 0)}, "
        f"events={opportunities.get('events', 0)}, "
        f"elapsed={elapsed:.1f}s"
    )
    return {
        "market": market,
        "predictions": {"successful": predictions.get("successful", 0), "error": predictions.get("error")},
        "opportunities": opportunities,
        "elapsed_seconds": elapsed,
    }
