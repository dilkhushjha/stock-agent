from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.causal_impact import CausalImpactEngine
from app.intelligence.exposure import ExposureMappingService
from app.intelligence.signals import SignalEngine
from app.models.alert import OpportunityAlert
from app.models.event import MarketEvent
from app.models.news import NewsArticle


class OpportunityAlertEngine:
    """Turns market events into user-facing opportunities and refreshes them as evidence changes."""

    MIN_ALERT_SCORE = 55.0

    @staticmethod
    def _risk(score: float, event: MarketEvent, causal_strength: float) -> str:
        if score >= 75 and causal_strength >= 0.6:
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

    @staticmethod
    def _causal_strength(causal: dict) -> float:
        chain = causal.get("causal_chain", [])
        if not chain:
            return 0.0

        sensitivities = [
            float(step.get("sensitivity") or 0.5)
            for step in chain
        ]
        average = sum(sensitivities) / len(sensitivities)
        length_bonus = min(0.25, len(chain) * 0.05)
        return min(1.0, average + length_bonus)

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
        causal = CausalImpactEngine.analyze(db=db, event_id=event_id)
        causal_strength = cls._causal_strength(causal)
        article = db.scalar(select(NewsArticle).where(NewsArticle.id == event.news_id))

        alerts = []
        created_count = 0
        updated_count = 0
        confidence = float(event.confidence or 0.0)

        for result in signal_result["results"]:
            market_score = float(result["score"])
            # Causal evidence is deliberately additive, not dominant. Market
            # behaviour still has to confirm the thesis.
            score = round(
                min(100.0, market_score * 0.75 + (causal_strength * 100.0) * 0.25),
                2,
            )

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
            chain_text = " → ".join(
                [causal.get("entity", entity)]
                + [step["to"] for step in causal.get("causal_chain", [])]
            )
            reason = (
                f"{event.title}. {event.description or ''} "
                f"Event confidence: {confidence:.0%}. "
                f"Causal chain: {chain_text or 'not established'}. "
                f"Causal strength: {causal_strength:.0%}. "
                f"Market signal: {market_score:.1f}/100; "
                f"combined opportunity score: {score:.1f}/100."
            ).strip()

            if existing:
                existing.action = action
                existing.confidence = confidence
                existing.opportunity_score = score
                existing.expected_horizon = event.time_horizon
                existing.risk = cls._risk(score, event, causal_strength)
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
                risk=cls._risk(score, event, causal_strength),
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
            "causal_strength": causal_strength,
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
