from apscheduler.schedulers.background import BackgroundScheduler

from app.agent.orchestrator import MarketAgent
from app.data.database import SessionLocal
from app.intelligence.evaluator import PredictionEvaluator
from app.intelligence.market_data_provider import YahooFinanceProvider
from app.intelligence.market_data_sync import MarketDataSyncService


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
        run_evaluation,
        trigger="interval",
        minutes=15,
        id="prediction_evaluation",
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

    scheduler.start()
    print("[SCHEDULER] Market Agent started.")
    print("[SCHEDULER] News cycle: every 5 minutes.")
    print("[SCHEDULER] Market data sync: every 15 minutes.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)


def run_evaluation():
    print("[EVALUATOR] Checking predictions...")
    db = SessionLocal()
    try:
        result = PredictionEvaluator.evaluate(db)
        print(f"[EVALUATOR] Evaluated: {result['evaluated']}")
    finally:
        db.close()


def run_market_data_sync():
    print("[MARKET DATA] Synchronizing prices...")
    db = SessionLocal()
    try:
        result = MarketDataSyncService.sync(
            db=db,
            provider=market_data_provider,
        )
        print(
            "[MARKET DATA] "
            f"Processed={result['processed']} "
            f"Succeeded={result['succeeded']} "
            f"Failed={result['failed']}"
        )
    except Exception as exc:
        print(f"[MARKET DATA] Sync failed: {exc}")
    finally:
        db.close()
