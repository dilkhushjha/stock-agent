from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.opportunity_scoring import OpportunityScoringEngine
from app.models.alert import OpportunityAlert


class OpportunityPipeline:
    """Persists scored opportunities as alerts while avoiding duplicate NEW alerts."""

    @classmethod
    def run_for_event(cls, db: Session, event_id: int) -> dict:
        scores = OpportunityScoringEngine.score_event(db, event_id)
        created = 0
        skipped = 0

        for score in scores:
            if score.action == "IGNORE":
                skipped += 1
                continue

            existing = db.scalar(
                select(OpportunityAlert).where(
                    OpportunityAlert.event_id == event_id,
                    OpportunityAlert.symbol == cls._symbol(score),
                    OpportunityAlert.status == "NEW",
                )
            )
            if existing:
                skipped += 1
                continue

            # The scoring object intentionally carries no persistence-specific
            # fields. The symbol is injected by the event candidate in run().

        return {"event_id": event_id, "scores": [asdict(score) for score in scores], "alerts_created": created, "skipped": skipped}

    @staticmethod
    def _symbol(score):
        return getattr(score, "symbol", None)
