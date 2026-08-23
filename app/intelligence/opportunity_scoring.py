from __future__ import annotations

from dataclasses import dataclass

from app.intelligence.causal_exposure import CausalExposureEngine
from app.intelligence.event_novelty import EventNoveltyEngine
from app.intelligence.forward_return import ForwardReturnEngine
from app.intelligence.market_awareness import MarketAwarenessEngine


@dataclass(frozen=True)
class OpportunityScore:
    symbol: str
    score: float
    action: str
    confidence: float
    risk: str
    expected_horizon: str
    expected_return_percent: float | None
    probability_positive: float | None
    expected_downside_percent: float | None
    components: dict
    explanation: str


class OpportunityScoringEngine:
    """Combines event, causal, market and forward-return evidence."""

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

            as_of = event.event_date or event.created_at
            awareness = MarketAwarenessEngine.score(db, stock, as_of)
            early_signal = 1.0 - awareness.awareness
            forecasts = ForwardReturnEngine.forecast(db, stock, as_of)
            forecast = next((item for item in forecasts if item.horizon_days == 7), None)

            # A forecast strengthens the ranking only when there is historical evidence.
            forecast_signal = 0.0
            if forecast:
                forecast_signal = min(1.0, max(-1.0, forecast.expected_return_percent / 10.0))

            components = {
                "novelty": round(novelty.novelty, 4),
                "importance": round(novelty.importance, 4),
                "causal_strength": round(candidate["causal_strength"], 4),
                "market_early_signal": round(early_signal, 4),
                "forward_return_signal": round(forecast_signal, 4),
            }

            raw_score = (
                0.22 * novelty.novelty
                + 0.18 * novelty.importance
                + 0.32 * candidate["causal_strength"]
                + 0.18 * early_signal
                + 0.10 * max(0.0, forecast_signal)
            )
            score = round(min(100.0, max(0.0, 100 * raw_score)), 2)

            if score >= 75:
                action = "BUY" if candidate["direction"] == "POSITIVE" else "AVOID"
                risk = "MEDIUM"
            elif score >= 55:
                action, risk = "WATCH", "MEDIUM"
            else:
                action, risk = "IGNORE", "HIGH"

            probability = forecast.probability_positive if forecast else None
            confidence = (
                0.35 * float(event.confidence or 0.0)
                + 0.25 * candidate["causal_strength"]
                + 0.20 * early_signal
                + 0.20 * (forecast.confidence if forecast else 0.0)
            )
            confidence = round(min(0.95, max(0.05, confidence)), 4)
            horizon = "1-7D" if awareness.status == "LOW_AWARENESS" else "1-3D"

            forecast_text = (
                f"7D historical analogue expects {forecast.expected_return_percent:+.2f}% "
                f"with {forecast.probability_positive:.0%} probability of a positive return."
                if forecast else
                "Insufficient historical analogue data for a 7D return forecast."
            )
            explanation = (
                f"Event novelty={novelty.novelty:.0%}, importance={novelty.importance:.0%}; "
                f"{candidate['symbol']} causal strength={candidate['causal_strength']:.0%}; "
                f"market awareness={awareness.awareness:.0%}. {forecast_text} "
                f"{candidate['rationale']}"
            )

            results.append(OpportunityScore(
                symbol=candidate["symbol"], score=score, action=action,
                confidence=confidence, risk=risk, expected_horizon=horizon,
                expected_return_percent=(forecast.expected_return_percent if forecast else None),
                probability_positive=probability,
                expected_downside_percent=(forecast.expected_downside_percent if forecast else None),
                components=components, explanation=explanation,
            ))

        return sorted(results, key=lambda item: item.score, reverse=True)
