from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.opportunity_scoring import OpportunityScoringEngine
from app.models.alert import OpportunityAlert
from app.models.event import MarketEvent


class OpportunityPipeline:
    """Runs scoring and persists actionable opportunities as deduplicated alerts."""

    @classmethod
    def run_for_event(cls, db: Session, event_id: int) -> dict:
        event = db.scalar(select(MarketEvent).where(MarketEvent.id == event_id))
        if not event:
            raise ValueError(f"Event {event_id} not found.")

        scores = OpportunityScoringEngine.score_event(db, event_id)
        created = 0
        skipped = 0
        persisted = []

        for score in scores:
            if score.action == "IGNORE":
                skipped += 1
                continue

            existing = db.scalar(select(OpportunityAlert).where(
                OpportunityAlert.event_id == event_id,
                OpportunityAlert.symbol == score.symbol,
                OpportunityAlert.status == "NEW",
            ))
            if existing:
                skipped += 1
                continue

            alert = OpportunityAlert(
                event_id=event_id,
                symbol=score.symbol,
                factor=event.event_type,
                action=score.action,
                confidence=score.confidence,
                opportunity_score=score.score,
                expected_horizon=score.expected_horizon,
                risk=score.risk,
                title=f"Potential {score.action.lower()} opportunity: {score.symbol}",
                reason=score.explanation,
                source_url=None,
                source_name="StockAgent Intelligence Pipeline",
                status="NEW",
            )
            db.add(alert)
            created += 1
            persisted.append(score.symbol)

        db.commit()
        return {
            "event_id": event_id,
            "scores": [asdict(score) for score in scores],
            "alerts_created": created,
            "alerts_skipped": skipped,
            "symbols": persisted,
        }
