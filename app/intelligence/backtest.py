from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.forward_prediction import ForwardPredictionEngine
from app.intelligence.exposure import ExposureMappingService
from app.models.event import MarketEvent
from app.models.market_data import MarketData
from app.models.stock import Stock


class HistoricalReplayEngine:
    """Replays stored events using only information available at event time.

    This is an evaluation harness for the current baseline intelligence. It does
    not claim that historical replay is equivalent to live execution until the
    live data timestamps are complete and leakage checks pass.
    """

    HORIZONS = (1, 3, 7, 14, 30)

    @staticmethod
    def _price_at_or_after(db: Session, stock_id: int, timestamp):
        return db.scalar(
            select(MarketData)
            .where(
                MarketData.stock_id == stock_id,
                MarketData.timestamp >= timestamp,
            )
            .order_by(MarketData.timestamp.asc())
        )

    @staticmethod
    def _price_at_or_before(db: Session, stock_id: int, timestamp):
        return db.scalar(
            select(MarketData)
            .where(
                MarketData.stock_id == stock_id,
                MarketData.timestamp <= timestamp,
            )
            .order_by(MarketData.timestamp.desc())
        )

    @classmethod
    def evaluate_stock(cls, db: Session, event: MarketEvent, stock: Stock) -> dict:
        event_time = event.event_date or event.created_at
        if not event_time:
            return {"status": "INSUFFICIENT_DATA", "symbol": stock.symbol}

        baseline = cls._price_at_or_before(db, stock.id, event_time)
        if not baseline or not baseline.close:
            return {"status": "INSUFFICIENT_DATA", "symbol": stock.symbol}

        prediction = ForwardPredictionEngine.predict(db, event, stock)
        outcomes = []
        for horizon in cls.HORIZONS:
            future = cls._price_at_or_after(db, stock.id, event_time + timedelta(days=horizon))
            if not future or not future.close:
                continue
            actual = (future.close - baseline.close) / baseline.close * 100.0
            aligned = actual if str(event.direction).upper() in {"POSITIVE", "UP", "BULLISH", "INCREASE"} else -actual
            predicted = next(
                (p for p in prediction.get("predictions", []) if p["horizon_days"] == horizon),
                None,
            )
            outcomes.append({
                "horizon_days": horizon,
                "actual_return_percent": round(actual, 2),
                "actual_direction_correct": aligned > 0,
                "predicted_return_percent": predicted["expected_return_percent"] if predicted else None,
                "predicted_probability": predicted["probability_of_direction"] if predicted else None,
            })

        return {
            "status": "OK" if outcomes else "INSUFFICIENT_DATA",
            "symbol": stock.symbol,
            "event_id": event.id,
            "event_date": event_time.isoformat(),
            "outcomes": outcomes,
        }

    @classmethod
    def replay_event(cls, db: Session, event_id: int) -> dict:
        event = db.scalar(select(MarketEvent).where(MarketEvent.id == event_id))
        if not event:
            raise ValueError(f"Event {event_id} not found.")

        mapping = ExposureMappingService.map_event(db, event_id)
        results = []
        for item in mapping.get("stocks", []):
            stock = db.scalar(select(Stock).where(Stock.symbol == item["symbol"]))
            if stock:
                results.append(cls.evaluate_stock(db, event, stock))

        return {
            "event_id": event_id,
            "event_title": event.title,
            "stocks_evaluated": len(results),
            "results": results,
        }
