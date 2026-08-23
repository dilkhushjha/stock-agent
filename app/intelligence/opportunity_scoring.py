from __future__ import annotations

from dataclasses import dataclass

from app.intelligence.causal_exposure import CausalExposureEngine
from app.intelligence.event_novelty import EventNoveltyEngine
from app.intelligence.market_awareness import MarketAwarenessEngine


@dataclass(frozen=True)
class OpportunityScore:
    symbol: str
    score: float
    action: str
    confidence: float
    risk: str
    expected_horizon: str
    components: dict
    explanation: str


class OpportunityScoringEngine:
    """Combines independent signals into an explainable opportunity ranking."""

    @classmethod
    def score_event(cls, db, event_id: int, stock_symbol: str | None = None) -> list[OpportunityScore]:
        from sqlalchemy import select
        from app.models.event import MarketEvent
        from app.models.stock import Stock

        event = db.scalar(select(MarketEvent).where(MarketEvent.id == event_id))
        if not event:
            raise ValueError(f"Event {event_id} not found.")

        novelty = EventNoveltyEngine.score(db, event)
        causal = CausalExposureEngine.analyze(db, event_id)
        results = []

        for candidate in causal["opportunities"]:
            if stock_symbol and candidate["symbol"] != stock_symbol:
                continue
            stock = db.scalar(select(Stock).where(Stock.symbol == candidate["symbol"]))
            if not stock:
                continue

            awareness = MarketAwarenessEngine.score(db, stock, event.event_date or event.created_at)
            early_signal = 1.0 - awareness.awareness
            components = {
                "novelty": round(novelty.novelty, 4),
                "importance": round(novelty.importance, 4),
                "causal_strength": round(candidate["causal_strength"], 4),
                "market_early_signal": round(early_signal, 4),
            }
            score = round(min(100.0, max(0.0, 100 * (
                0.25 * novelty.novelty
                + 0.20 * novelty.importance
                + 0.35 * candidate["causal_strength"]
                + 0.20 * early_signal
            ))), 2)

            if score >= 75:
                action = "BUY" if candidate["direction"] == "POSITIVE" else "AVOID"
                risk = "MEDIUM"
            elif score >= 55:
                action, risk = "WATCH", "MEDIUM"
            else:
                action, risk = "IGNORE", "HIGH"

            confidence = round(min(0.95, max(0.05,
                0.45 * float(event.confidence or 0.0)
                + 0.30 * candidate["causal_strength"]
                + 0.25 * early_signal
            )), 4)
            horizon = "1-7D" if awareness.status == "LOW_AWARENESS" else "1-3D"
            explanation = (
                f"Event novelty={novelty.novelty:.0%}, importance={novelty.importance:.0%}; "
                f"{candidate['symbol']} causal strength={candidate['causal_strength']:.0%}; "
                f"market awareness={awareness.awareness:.0%}. {candidate['rationale']}"
            )
            results.append(OpportunityScore(
                symbol=candidate["symbol"], score=score, action=action,
                confidence=confidence, risk=risk, expected_horizon=horizon,
                components=components, explanation=explanation,
            ))
        return sorted(results, key=lambda item: item.score, reverse=True)
