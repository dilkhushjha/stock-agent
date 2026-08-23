from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.database import get_db
from app.models.alert import OpportunityAlert
from app.models.event import MarketEvent


router = APIRouter(prefix="/alerts", tags=["Opportunity Alerts"])


@router.get("/latest")
def latest_alerts(limit: int = 20, db: Session = Depends(get_db)):
    limit = min(max(limit, 1), 100)
    alerts = db.scalars(
        select(OpportunityAlert)
        .order_by(OpportunityAlert.created_at.desc())
        .limit(limit)
    ).all()

    result = []
    for alert in alerts:
        event = db.scalar(select(MarketEvent).where(MarketEvent.id == alert.event_id))
        result.append({
            "id": alert.id,
            "symbol": alert.symbol,
            "factor": alert.factor,
            "action": alert.action,
            "priority": "HIGH" if alert.opportunity_score >= 75 else "MEDIUM" if alert.opportunity_score >= 55 else "LOW",
            "confidence": alert.confidence,
            "opportunity_score": alert.opportunity_score,
            "expected_horizon": alert.expected_horizon,
            "risk": alert.risk,
            "title": alert.title,
            "reason": alert.reason,
            "source": alert.source_name,
            "source_url": alert.source_url,
            "event_id": alert.event_id,
            "event_type": event.event_type if event else None,
            "event_time": event.created_at.isoformat() if event and event.created_at else None,
            "status": alert.status,
            "created_at": alert.created_at.isoformat(),
        })
    return result


@router.get("/live")
def live_alerts(limit: int = 10, db: Session = Depends(get_db)):
    """Concise feed for the live dashboard/notification layer."""
    limit = min(max(limit, 1), 50)
    alerts = db.scalars(
        select(OpportunityAlert)
        .where(OpportunityAlert.status == "NEW")
        .order_by(OpportunityAlert.created_at.desc())
        .limit(limit)
    ).all()

    return [
        {
            "id": alert.id,
            "symbol": alert.symbol,
            "priority": "HIGH" if alert.opportunity_score >= 75 else "MEDIUM" if alert.opportunity_score >= 55 else "LOW",
            "action": alert.action,
            "score": round(alert.opportunity_score, 1),
            "title": alert.title,
            "reason": alert.reason,
            "source": alert.source_name,
            "source_url": alert.source_url,
            "horizon": alert.expected_horizon,
            "risk": alert.risk,
            "created_at": alert.created_at.isoformat(),
        }
        for alert in alerts
    ]


@router.patch("/{alert_id}/read")
def mark_alert_read(alert_id: int, db: Session = Depends(get_db)):
    alert = db.scalar(select(OpportunityAlert).where(OpportunityAlert.id == alert_id))
    if not alert:
        return {"updated": False, "reason": "not_found"}
    alert.status = "READ"
    db.commit()
    return {"updated": True, "id": alert.id, "status": alert.status}
