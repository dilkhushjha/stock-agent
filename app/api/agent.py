from fastapi import APIRouter
from sqlalchemy import select

from app.agent.orchestrator import MarketAgent
from app.agent.scheduler import market_status, run_live_cycle
from app.data.database import SessionLocal
from app.intelligence.alert_engine import OpportunityAlertEngine
from app.models.event import MarketEvent


router = APIRouter(prefix="/agent", tags=["Live Agent"])


@router.get("/status")
def status():
    from app.agent import scheduler as scheduler_module
    current = market_status()
    return {
        **current,
        "scheduler_running": scheduler_module.scheduler.running,
        "last_cycle": scheduler_module.last_cycle.isoformat() if scheduler_module.last_cycle else None,
        "last_cycle_result": {
            "status": scheduler_module.last_cycle_result.get("status"),
            "universe": scheduler_module.last_cycle_result.get("universe"),
            "predictions": scheduler_module.last_cycle_result.get("predictions"),
            "opportunities": scheduler_module.last_cycle_result.get("opportunities"),
            "elapsed_seconds": scheduler_module.last_cycle_result.get("elapsed_seconds"),
        } if scheduler_module.last_cycle_result else None,
    }


@router.post("/run-now")
def run_now():
    """Run the complete live intelligence cycle immediately."""
    result = MarketAgent().run_news_cycle()
    live_result = run_live_cycle(force=True)

    db = SessionLocal()
    refreshed = 0
    try:
        events = db.scalars(
            select(MarketEvent)
            .order_by(MarketEvent.created_at.desc())
            .limit(20)
        ).all()
        for event in events:
            try:
                OpportunityAlertEngine.generate_for_event(db, event.id)
                refreshed += 1
            except Exception as exc:
                print(f"[AGENT] Opportunity refresh failed for event {event.id}: {exc}")
        db.commit()
    finally:
        db.close()

    result["live"] = live_result
    result["recent_events_refreshed"] = refreshed
    return result
