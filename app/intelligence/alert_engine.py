from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.exposure import ExposureMappingService
from app.intelligence.signals import SignalEngine
from app.models.alert import OpportunityAlert
from app.models.event import MarketEvent
from app.models.news import NewsArticle


class OpportunityAlertEngine:
    """Turns market events into user-facing opportunities and refreshes them as evidence changes."""

    MIN_ALERT_SCORE = 55.0

    @staticmethod
    def _risk(score: float, event: MarketEvent) -> str:
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
    def generate_for_event(cls, db: Session, event_id: int) -> dict:
        event = db.scalar(select(MarketEvent).where(MarketEvent.id == event_id))
        if not event:
            raise ValueError(f"Event {event_id} not found.")

        entity = ExposureMappingService.normalize_entity(event.entity or "")
        event.entity = entity
        db.commit()

        mapping = ExposureMappingService.map_event(db, event_id)
        if not mapping["stocks_found"]:
            return {"event_id": event_id, "alerts_created": 0, "alerts_updated": 0, "alerts": []}

        signal_result = SignalEngine.generate(db=db, event_id=event_id)
        article = db.scalar(select(NewsArticle).where(NewsArticle.id == event.news_id))

        alerts = []
        created_count = 0
        updated_count = 0
        confidence = float(event.confidence or 0.0)

        for result in signal_result["results"]:
            score = float(result["score"])
            existing = db.scalar(
                select(OpportunityAlert).where(
                    OpportunityAlert.event_id == event_id,
                    OpportunityAlert.symbol == result["symbol"],
                )
            )

            if score < cls.MIN_ALERT_SCORE:
                if existing and existing.status == "NEW":
                    existing.status = "STALE"
                    updated_count += 1
                continue

            action = cls._action(score, result["direction"])
            reason = (
                f"{event.title}. {event.description or ''} "
                f"Event confidence: {confidence:.0%}. "
                f"Exposure and current market behaviour produced a "
                f"signal score of {score:.1f}/100."
            ).strip()

            if existing:
                # A developing event may cross the alert threshold later.
                # Refresh the existing alert instead of creating duplicates.
                previous_action = existing.action
                existing.action = action
                existing.confidence = confidence
                existing.opportunity_score = score
                existing.expected_horizon = event.time_horizon
                existing.risk = cls._risk(score, event)
                existing.title = f"Potential {entity} opportunity: {result['symbol']}"
                existing.reason = reason
                existing.source_url = article.url if article else existing.source_url
                existing.source_name = article.source if article else existing.source_name
                existing.status = "NEW"
                updated_count += 1
                alerts.append(existing)
                continue

            alert = OpportunityAlert(
                event_id=event_id,
                symbol=result["symbol"],
                factor=entity,
                action=action,
                confidence=confidence,
                opportunity_score=score,
                expected_horizon=event.time_horizon,
                risk=cls._risk(score, event),
                title=f"Potential {entity} opportunity: {result['symbol']}",
                reason=reason,
                source_url=article.url if article else None,
                source_name=article.source if article else None,
                status="NEW",
            )
            db.add(alert)
            alerts.append(alert)
            created_count += 1

        db.commit()

        return {
            "event_id": event_id,
            "entity": entity,
            "alerts_created": created_count,
            "alerts_updated": updated_count,
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
