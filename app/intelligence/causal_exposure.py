from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.exposure import ExposureMappingService
from app.models.event import MarketEvent
from app.models.stock import Stock
from app.models.exposure import StockExposure


@dataclass(frozen=True)
class CausalOpportunity:
    symbol: str
    direction: str
    exposure_strength: float
    causal_strength: float
    rationale: str


class CausalExposureEngine:
    """Ranks directly mapped stocks by the strength of the economic linkage.

    The current version uses the curated exposure graph as its causal prior.
    It intentionally does not pretend that a static mapping proves causality;
    later versions can combine this prior with fundamentals, commodity prices,
    supply-chain data and observed market reactions.
    """

    @classmethod
    def analyze(cls, db: Session, event_id: int) -> dict:
        event = db.scalar(select(MarketEvent).where(MarketEvent.id == event_id))
        if not event:
            raise ValueError(f"Event {event_id} not found.")

        mapping = ExposureMappingService.map_event(db, event_id)
        opportunities = []

        for item in mapping.get("exposures", []):
            stock = db.scalar(select(Stock).where(Stock.symbol == item["symbol"]))
            if not stock:
                continue

            exposure = db.scalar(
                select(StockExposure).where(
                    StockExposure.stock_id == stock.id,
                    StockExposure.entity == mapping["entity"],
                )
            )
            strength = float(item.get("exposure_strength") or 0.0)
            event_confidence = float(event.confidence or 0.0)
            causal_strength = min(1.0, strength * event_confidence)

            direction = item.get("direction", "NEUTRAL")
            rationale = (
                f"{mapping['entity']} event has a curated {strength:.0%} exposure to "
                f"{item['symbol']}; event confidence is {event_confidence:.0%}."
            )
            opportunities.append(
                CausalOpportunity(
                    symbol=item["symbol"],
                    direction=direction,
                    exposure_strength=round(strength, 4),
                    causal_strength=round(causal_strength, 4),
                    rationale=rationale,
                ).__dict__
            )

        opportunities.sort(key=lambda x: x["causal_strength"], reverse=True)
        return {
            "event_id": event_id,
            "entity": mapping.get("entity"),
            "opportunities": opportunities,
        }
