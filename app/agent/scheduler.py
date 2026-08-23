from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func, select

from app.agent.orchestrator import MarketAgent
from app.data.database import SessionLocal
from app.intelligence.broad_universe_cycle import DEFAULT_BATCH_SIZE, predict_stock_batch
from app.intelligence.evaluator import PredictionEvaluator
from app.intelligence.alert_engine import OpportunityAlertEngine
from app.intelligence.market_data_provider import YahooFinanceProvider
from app.intelligence.market_data_sync import MarketDataSyncService
from app.ml.train import train as train_model
from app.models.event import MarketEvent
from app.models.stock import Stock


agent = MarketAgent()
scheduler = BackgroundScheduler()
market_data_provider = YahooFinanceProvider()
universe_cursor = 0


def _next_universe_batch():
    global universe_cursor
    db = SessionLocal()
    try:
        total = db.scalar(select(func.count(Stock.id)).where(
            Stock.is_active.is_(True), Stock.exchange == "NSE"
        )) or 0
        if total == 0:
            return 0, 0
        offset = universe_cursor % total
        universe_cursor = (offset + DEFAULT_BATCH_SIZE) % total
        return offset, total
    finally:
        db.close()


def start_scheduler():
    scheduler.add_job(agent.run_news_cycle, trigger="interval", minutes=5, id="news_cycle", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(run_live_cycle, trigger="interval", minutes=15, id="live_intelligence_cycle", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(run_evaluation, trigger="interval", minutes=30, id="prediction_evaluation", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(retrain_model_cycle, trigger="interval", days=7, id="model_retraining", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(agent.run_news_cycle, trigger="date", run_date=datetime.utcnow() + timedelta(seconds=5), id="news_initial", replace_existing=True)
    scheduler.add_job(run_live_cycle, trigger="date", run_date=datetime.utcnow() + timedelta(seconds=15), id="live_initial", replace_existing=True)
    scheduler.start()
    print("[SCHEDULER] Market Agent started.")
    print("[SCHEDULER] News ingestion + event analysis: every 5 minutes.")
    print(f"[SCHEDULER] Broad NSE market/ML scan: {DEFAULT_BATCH_SIZE} stocks per 15-minute cycle, rotating continuously.")
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
    print("[RETRAIN] Starting recurrent model training...")
    try:
        result = train_model()
        print(f"[RETRAIN] Complete: stocks={result['training_stocks']}, rows={result['training_rows']}, version={result['model_version']}")
        return result
    except Exception as exc:
        print(f"[RETRAIN] Failed; keeping previous model artifact: {exc}")
        return {"status": "failed", "error": str(exc)}


def run_market_data_sync(offset: int, batch_size: int):
    print(f"[MARKET DATA] Synchronizing universe batch offset={offset}, size={batch_size}...")
    db = SessionLocal()
    try:
        service = MarketDataSyncService(provider=market_data_provider)
        result = service.sync(db=db, history_days=5, workers=2, offset=offset, limit=batch_size)
        print(f"[MARKET DATA] Processed={result['requested_stocks']} Succeeded={result['successful_stocks']} Failed={result['failed_stocks']} Inserted={result['inserted_rows']}")
        return result
    except Exception as exc:
        print(f"[MARKET DATA] Sync failed: {exc}")
        return {"successful_stocks": 0, "error": str(exc)}
    finally:
        db.close()


def run_ml_prediction_cycle(offset: int, batch_size: int):
    print(f"[ML] Running prediction batch offset={offset}, size={batch_size}...")
    db = SessionLocal()
    try:
        result = predict_stock_batch(db, offset=offset, batch_size=batch_size)
        print(f"[ML] Predictions completed: {result['successful']} successful, {result['failed']} failed.")
        return result
    except Exception as exc:
        print(f"[ML] Prediction cycle failed: {exc}")
        return {"successful": 0, "error": str(exc)}
    finally:
        db.close()


def refresh_opportunities():
    print("[OPPORTUNITY] Refreshing recent opportunities...")
    db = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(days=7)
        events = db.scalars(select(MarketEvent).where(
            MarketEvent.created_at >= since
        ).order_by(MarketEvent.created_at.desc()).limit(100)).all()
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
    print("\n[LIVE CYCLE] Starting rotating full-universe intelligence cycle...")
    started = datetime.utcnow()
    offset, total = _next_universe_batch()
    batch_size = min(DEFAULT_BATCH_SIZE, total) if total else DEFAULT_BATCH_SIZE
    market = run_market_data_sync(offset, batch_size)
    predictions = run_ml_prediction_cycle(offset, batch_size)
    opportunities = refresh_opportunities()
    elapsed = (datetime.utcnow() - started).total_seconds()
    print(f"[LIVE CYCLE] Complete: batch={offset}:{offset + batch_size}/{total}, market_success={market.get('successful_stocks', 0)}, predictions={predictions.get('successful', 0)}, events={opportunities.get('events', 0)}, elapsed={elapsed:.1f}s")
    return {
        "universe": {"offset": offset, "batch_size": batch_size, "total": total},
        "market": market,
        "predictions": {"successful": predictions.get("successful", 0), "error": predictions.get("error")},
        "opportunities": opportunities,
        "elapsed_seconds": elapsed,
    }
