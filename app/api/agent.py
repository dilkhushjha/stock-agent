from sqlalchemy import select
from fastapi import APIRouter

from app.agent.orchestrator import MarketAgent
from app.data.database import SessionLocal
from app.intelligence.alert_engine import OpportunityAlertEngine
from app.models.event import MarketEvent

router = APIRouter(prefix="/agent", tags=["Live Agent"])


@router.post("/run-now")
def run_now():
    """Run live ingestion and refresh recent events into user-facing opportunities."""
    result = MarketAgent().run_news_cycle()
    db = SessionLocal()
    refreshed = 0
    try:
        events = db.scalars(
            select(MarketEvent).order_by(MarketEvent.created_at.desc()).limit(20)
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

    result["recent_events_refreshed"] = refreshed
    return result
