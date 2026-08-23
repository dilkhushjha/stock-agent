from apscheduler.schedulers.background import (
    BackgroundScheduler,
)

from app.agent.orchestrator import (
    MarketAgent,
)
from app.data.database import SessionLocal

from app.intelligence.evaluator import (
    PredictionEvaluator,
)


agent = MarketAgent()

scheduler = BackgroundScheduler()


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

    scheduler.start()

    print(
        "[SCHEDULER] Market Agent started."
    )

    print(
        "[SCHEDULER] News cycle: every 5 minutes."
    )


def stop_scheduler():

    if scheduler.running:

        scheduler.shutdown(
            wait=False
        )


def run_evaluation():

    print(
        "[EVALUATOR] Checking predictions..."
    )

    db = SessionLocal()

    try:

        result = (
            PredictionEvaluator.evaluate(
                db
            )
        )

        print(
            f"[EVALUATOR] Evaluated: "
            f"{result['evaluated']}"
        )

    finally:

        db.close()
