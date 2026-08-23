from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.analytics import MarketAnalyticsService
from app.models.event import MarketEvent
from app.models.exposure import StockExposure
from app.models.signal import MarketSignal
from app.models.stock import Stock


class SignalEngine:

    IMPACT_WEIGHT = {
        "LOW": 0.35,
        "MEDIUM": 0.65,
        "HIGH": 1.0,
    }

    DIRECTION_MULTIPLIER = {
        "POSITIVE": 1.0,
        "NEGATIVE": -1.0,
        "NEUTRAL": 0.0,
    }

    @staticmethod
    def _momentum_score(return_5d: float | None) -> float:
        if return_5d is None:
            return 0.5
        if return_5d >= 5:
            return 1.0
        if return_5d >= 2:
            return 0.8
        if return_5d > 0:
            return 0.65
        if return_5d > -2:
            return 0.45
        if return_5d > -5:
            return 0.25
        return 0.1

    @staticmethod
    def _volume_score(volume_ratio: float | None) -> float:
        if volume_ratio is None:
            return 0.5
        if volume_ratio >= 3:
            return 1.0
        if volume_ratio >= 2:
            return 0.85
        if volume_ratio >= 1.5:
            return 0.7
        if volume_ratio >= 1:
            return 0.55
        return 0.35

    @staticmethod
    def _direction_multiplier(direction: str | None) -> float:
        return SignalEngine.DIRECTION_MULTIPLIER.get(
            str(direction or "NEUTRAL").upper(),
            0.0,
        )

    @classmethod
    def generate(cls, db: Session, event_id: int) -> dict:
        event = db.scalar(
            select(MarketEvent).where(MarketEvent.id == event_id)
        )
        if not event:
            raise ValueError(f"Event {event_id} not found.")

        exposures = db.scalars(
            select(StockExposure).where(
                StockExposure.entity == event.entity.upper()
            )
        ).all()
        if not exposures:
            raise ValueError(f"No stock exposures found for {event.entity}.")

        impact_score = cls.IMPACT_WEIGHT.get(event.impact, 0.35)
        confidence = event.confidence if event.confidence is not None else 0.3
        event_direction = cls._direction_multiplier(event.direction)
        results = []

        for exposure in exposures:
            stock = db.scalar(
                select(Stock).where(Stock.id == exposure.stock_id)
            )
            if not stock:
                continue

            try:
                analytics = MarketAnalyticsService.get_snapshot(
                    db=db,
                    symbol=stock.symbol,
                )
            except ValueError:
                continue

            momentum = cls._momentum_score(
                analytics["returns"]["5d_percent"]
            )
            volume = cls._volume_score(analytics["volume_ratio"])
            trend_score = {
                "BULLISH": 1.0,
                "BEARISH": 0.2,
                "NEUTRAL": 0.5,
            }.get(analytics["trend"], 0.5)

            # The event direction describes the commodity/industry.
            # Exposure direction describes how that event affects this stock.
            # Combining both prevents errors such as treating higher interest
            # rates as bullish for banks whose exposure is explicitly negative.
            exposure_direction = cls._direction_multiplier(exposure.direction)
            effective_direction = event_direction * exposure_direction

            event_score = (
                impact_score
                * confidence
                * exposure.exposure_strength
            )

            market_confirmation = (
                momentum * 0.45
                + volume * 0.25
                + trend_score * 0.30
            )

            if effective_direction > 0:
                alignment = market_confirmation
            elif effective_direction < 0:
                alignment = 1 - market_confirmation
            else:
                alignment = 0.5

            score = round(
                max(0, min(100, event_score * alignment * 100)),
                2,
            )

            if score >= 75:
                signal = "HIGH_ATTENTION"
            elif score >= 55:
                signal = "WATCH"
            elif score >= 35:
                signal = "NEUTRAL"
            else:
                signal = "LOW_PRIORITY"

            stock_direction = (
                "POSITIVE" if effective_direction > 0
                else "NEGATIVE" if effective_direction < 0
                else "NEUTRAL"
            )

            explanation = (
                f"Event={event.event_type}; "
                f"event direction={event.direction}; "
                f"stock exposure={exposure.direction}; "
                f"stock impact={stock_direction}; "
                f"impact={event.impact}; confidence={confidence:.2f}; "
                f"exposure={exposure.exposure_strength:.2f}; "
                f"5D return={analytics['returns']['5d_percent']}; "
                f"trend={analytics['trend']}; "
                f"volume ratio={analytics['volume_ratio']}"
            )

            db.add(MarketSignal(
                event_id=event.id,
                stock_id=stock.id,
                score=score,
                signal=signal,
                explanation=explanation,
            ))

            results.append({
                "symbol": stock.symbol,
                "score": score,
                "signal": signal,
                "direction": stock_direction,
                "explanation": explanation,
            })

        db.commit()
        results.sort(key=lambda item: item["score"], reverse=True)

        return {
            "event_id": event.id,
            "entity": event.entity,
            "direction": event.direction,
            "results": results,
        }
