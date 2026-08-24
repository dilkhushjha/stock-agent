from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

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


IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)

agent = MarketAgent()
scheduler = BackgroundScheduler(timezone=IST)
market_data_provider = YahooFinanceProvider()
universe_cursor = 0
last_cycle = None
last_cycle_result = None


def market_status():
    now = datetime.now(IST)
    weekday = now.weekday() < 5
    in_session = weekday and MARKET_OPEN <= now.time().replace(tzinfo=None) <= MARKET_CLOSE
    return {
        "timestamp": now.isoformat(),
        "timezone": "Asia/Kolkata",
        "is_weekday": weekday,
        "market_open": in_session,
        "session": "OPEN" if in_session else ("PRE_MARKET" if weekday and now.time().replace(tzinfo=None) < MARKET_OPEN else "CLOSED"),
    }


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
    # News is a 24x7 input: events can happen outside market hours.
    scheduler.add_job(agent.run_news_cycle, trigger="interval", minutes=5, id="news_cycle", replace_existing=True, max_instances=1, coalesce=True)

    # Market-dependent intelligence runs only during the trading session.
    scheduler.add_job(run_live_cycle, trigger="interval", minutes=15, id="live_intelligence_cycle", replace_existing=True, max_instances=1, coalesce=True)

    # Re-check predictions frequently enough to capture forward outcomes.
    scheduler.add_job(run_evaluation, trigger="interval", minutes=30, id="prediction_evaluation", replace_existing=True, max_instances=1, coalesce=True)

    # Recurrent learning is intentionally slower and never blocks live cycles.
    scheduler.add_job(retrain_model_cycle, trigger="interval", days=7, id="model_retraining", replace_existing=True, max_instances=1, coalesce=True)

    # Prime the intelligence engine immediately after startup.
    scheduler.add_job(agent.run_news_cycle, trigger="date", run_date=datetime.now(IST) + timedelta(seconds=5), id="news_initial", replace_existing=True)
    scheduler.add_job(run_live_cycle, trigger="date", run_date=datetime.now(IST) + timedelta(seconds=15), id="live_initial", replace_existing=True)

    # Pre-market synthesis: collect overnight/news from the previous session before 09:15.
    scheduler.add_job(agent.run_news_cycle, trigger="cron", day_of_week="mon-fri", hour=8, minute=45, id="premarket_news", replace_existing=True, max_instances=1, coalesce=True)

    # Post-market capture: preserve the day's final state for next-day historical reasoning.
    scheduler.add_job(run_post_market_cycle, trigger="cron", day_of_week="mon-fri", hour=15, minute=40, id="post_market_cycle", replace_existing=True, max_instances=1, coalesce=True)

    scheduler.start()
    print("[SCHEDULER] Market Agent started in Asia/Kolkata.")
    print("[SCHEDULER] News ingestion/event intelligence: every 5 minutes, 24x7.")
    print(f"[SCHEDULER] Live market/ML scan: {DEFAULT_BATCH_SIZE} NSE stocks per 15-minute trading-session cycle.")
    print("[SCHEDULER] Pre-market synthesis: 08:45 IST weekdays.")
    print("[SCHEDULER] Post-market capture: 15:40 IST weekdays.")
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


def run_live_cycle(force: bool = False):
    global last_cycle, last_cycle_result
    status = market_status()
    if not force and not status["market_open"]:
        print(f"[LIVE CYCLE] Skipped: market session is {status['session']}.")
        return {"status": "skipped", "reason": status["session"], "market": status}

    print("\n[LIVE CYCLE] Starting rotating full-universe intelligence cycle...")
    started = datetime.now(IST)
    offset, total = _next_universe_batch()
    batch_size = min(DEFAULT_BATCH_SIZE, total) if total else DEFAULT_BATCH_SIZE
    market = run_market_data_sync(offset, batch_size)
    predictions = run_ml_prediction_cycle(offset, batch_size)
    opportunities = refresh_opportunities()
    elapsed = (datetime.now(IST) - started).total_seconds()
    result = {
        "status": "completed",
        "market": market_status(),
        "universe": {"offset": offset, "batch_size": batch_size, "total": total},
        "market_data": market,
        "predictions": {"successful": predictions.get("successful", 0), "failed": predictions.get("failed", 0), "error": predictions.get("error")},
        "opportunities": opportunities,
        "elapsed_seconds": elapsed,
    }
    last_cycle = datetime.now(IST)
    last_cycle_result = result
    print(f"[LIVE CYCLE] Complete: batch={offset}:{offset + batch_size}/{total}, market_success={market.get('successful_stocks', 0)}, predictions={predictions.get('successful', 0)}, events={opportunities.get('events', 0)}, elapsed={elapsed:.1f}s")
    return result


def run_post_market_cycle():
    print("[POST-MARKET] Capturing final session intelligence...")
    try:
        result = agent.run_news_cycle()
        result["live"] = run_live_cycle(force=True)
        return result
    except Exception as exc:
        print(f"[POST-MARKET] Failed: {exc}")
        return {"status": "failed", "error": str(exc)}
