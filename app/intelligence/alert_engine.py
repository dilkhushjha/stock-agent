from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.exposure import ExposureMappingService
from app.intelligence.signals import SignalEngine
from app.models.alert import OpportunityAlert
from app.models.event import MarketEvent
from app.models.news import NewsArticle


class OpportunityAlertEngine:
    """Turns a detected market event into user-facing opportunities."""

    MIN_ALERT_SCORE = 55.0

    @staticmethod
    def _risk(score: float, event: MarketEvent) -> str:
        if event.impact == "HIGH" and score >= 75:
            return "MEDIUM"
        if score >= 75:
            return "MEDIUM"
        return "HIGH"

    @staticmethod
    def _action(score: float, direction: str) -> str:
        if direction == "POSITIVE" and score >= 75:
            return "BUY"
        if direction == "POSITIVE" and score >= 55:
            return "WATCH"
        if direction == "NEGATIVE" and score >= 75:
            return "AVOID"
        return "WATCH"

    @classmethod
    def generate_for_event(
        cls,
        db: Session,
        event_id: int,
    ) -> dict:
        event = db.scalar(
            select(MarketEvent).where(MarketEvent.id == event_id)
        )
        if not event:
            raise ValueError(f"Event {event_id} not found.")

        entity = ExposureMappingService.normalize_entity(event.entity or "")
        event.entity = entity
        db.commit()

        mapping = ExposureMappingService.map_event(db, event_id)
        if not mapping["stocks_found"]:
            return {"event_id": event_id, "alerts_created": 0, "alerts": []}

        signal_result = SignalEngine.generate(db=db, event_id=event_id)
        article = db.scalar(
            select(NewsArticle).where(NewsArticle.id == event.news_id)
        )

        alerts = []
        for result in signal_result["results"]:
            score = float(result["score"])
            if score < cls.MIN_ALERT_SCORE:
                continue

            action = cls._action(score, event.direction)

            existing = db.scalar(
                select(OpportunityAlert).where(
                    OpportunityAlert.event_id == event_id,
                    OpportunityAlert.symbol == result["symbol"],
                )
            )
            if existing:
                alerts.append(existing)
                continue

            reason = (
                f"{event.title}. {event.description or ''} "
                f"Event confidence: {event.confidence:.0%}. "
                f"Exposure and current market behaviour produced a "
                f"signal score of {score:.1f}/100."
            )

            alert = OpportunityAlert(
                event_id=event_id,
                symbol=result["symbol"],
                factor=entity,
                action=action,
                confidence=float(event.confidence or 0.0),
                opportunity_score=score,
                expected_horizon=event.time_horizon,
                risk=cls._risk(score, event),
                title=f"Potential {entity} opportunity: {result['symbol']}",
                reason=reason.strip(),
                source_url=article.url if article else None,
                source_name=article.source if article else None,
                status="NEW",
            )
            db.add(alert)
            alerts.append(alert)

        db.commit()

        return {
            "event_id": event_id,
            "entity": entity,
            "alerts_created": sum(1 for a in alerts if a.id),
            "alerts": [
                {
                    "id": a.id,
                    "symbol": a.symbol,
                    "action": a.action,
                    "score": a.opportunity_score,
                    "confidence": a.confidence,
                    "risk": a.risk,
                    "horizon": a.expected_horizon,
                    "title": a.title,
                    "reason": a.reason,
                    "source": a.source_name,
                    "source_url": a.source_url,
                }
                for a in alerts
            ],
        }
