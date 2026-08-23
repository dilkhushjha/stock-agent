from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.exposure import ExposureMappingService
from app.models.event import MarketEvent
from app.models.market_relationship import MarketRelationship


class CausalImpactEngine:
    """Builds an explainable event -> market -> sector/company impact chain."""

    @staticmethod
    def _sign(value: str | None) -> int:
        value = str(value or "").upper()
        if value in {"POSITIVE", "UP", "BULLISH", "INCREASE"}:
            return 1
        if value in {"NEGATIVE", "DOWN", "BEARISH", "DECREASE"}:
            return -1
        return 0

    @classmethod
    def analyze(cls, db: Session, event_id: int) -> dict:
        event = db.scalar(select(MarketEvent).where(MarketEvent.id == event_id))
        if not event:
            raise ValueError(f"Event {event_id} not found.")

        entity = ExposureMappingService.normalize_entity(event.entity or "")
        event_sign = cls._sign(event.direction)

        relationships = db.scalars(
            select(MarketRelationship).where(
                (MarketRelationship.source.ilike(entity))
                | (MarketRelationship.target.ilike(entity))
            )
        ).all()

        chain = []
        current = entity
        visited = set()
        max_hops = 4

        for _ in range(max_hops):
            candidates = [
                r for r in relationships
                if r.id not in visited
                and (
                    r.source.upper() == current.upper()
                    or r.target.upper() == current.upper()
                )
            ]
            if not candidates:
                break

            relationship = max(
                candidates,
                key=lambda r: float(r.sensitivity or 0.5),
            )
            visited.add(relationship.id)

            next_node = (
                relationship.target
                if relationship.source.upper() == current.upper()
                else relationship.source
            )
            relationship_sign = cls._sign(relationship.impact)
            effective_sign = event_sign * relationship_sign
            if effective_sign > 0:
                direction = "POSITIVE"
            elif effective_sign < 0:
                direction = "NEGATIVE"
            else:
                direction = "NEUTRAL"

            chain.append({
                "from": current,
                "to": next_node,
                "relationship": relationship.relationship,
                "direction": direction,
                "sensitivity": relationship.sensitivity,
                "description": relationship.description,
            })
            current = next_node

        return {
            "event_id": event.id,
            "entity": entity,
            "event_direction": event.direction,
            "causal_chain": chain,
            "chain_length": len(chain),
            "explainable": bool(chain),
        }
