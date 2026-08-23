from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.intelligence.benchmark_registry import BenchmarkRegistry
from app.intelligence.opportunity_scoring import OpportunityScoringEngine
from app.models.market_data import MarketData
from app.models.stock import Stock


class HistoricalReplayRunner:
    """Replay decisions at an event timestamp without using future observations."""

    HORIZONS = (1, 3, 7, 14, 30)

    @staticmethod
    def _close_at_or_after(db, stock_id: int, timestamp):
        return db.scalar(
            select(MarketData.close)
            .where(MarketData.stock_id == stock_id, MarketData.timestamp >= timestamp)
            .order_by(MarketData.timestamp.asc())
        )

    @staticmethod
    def _close_at_or_before(db, stock_id: int, timestamp):
        return db.scalar(
            select(MarketData.close)
            .where(MarketData.stock_id == stock_id, MarketData.timestamp <= timestamp)
            .order_by(MarketData.timestamp.desc())
        )

    @classmethod
    def replay_event(cls, db, event_id: int) -> list[dict]:
        from app.models.event import MarketEvent

        event = db.scalar(select(MarketEvent).where(MarketEvent.id == event_id))
        if not event:
            raise ValueError(f"Event {event_id} not found.")

        event_time = event.event_date or event.created_at
        scores = OpportunityScoringEngine.score_event(db, event_id)
        results = []

        benchmark = BenchmarkRegistry.select(event.entity)
        benchmark_stock = db.scalar(select(Stock).where(Stock.yahoo_symbol == benchmark.symbol)) if benchmark else None
        benchmark_start = cls._close_at_or_before(db, benchmark_stock.id, event_time) if benchmark_stock else None

        for score in scores:
            stock = db.scalar(select(Stock).where(Stock.symbol == score.symbol))
            if not stock:
                continue

            start_close = cls._close_at_or_before(db, stock.id, event_time)
            if start_close is None or start_close == 0:
                continue

            outcomes = []
            for days in cls.HORIZONS:
                target_time = event_time + timedelta(days=days)
                target_close = cls._close_at_or_after(db, stock.id, target_time)
                if target_close is None:
                    continue

                actual_return = ((target_close - start_close) / start_close) * 100
                benchmark_return = None
                if benchmark_start is not None:
                    benchmark_end = cls._close_at_or_after(db, benchmark_stock.id, target_time)
                    if benchmark_end is not None and benchmark_start:
                        benchmark_return = ((benchmark_end - benchmark_start) / benchmark_start) * 100

                predicted_return = score.expected_return_percent if days == 7 else None
                outcomes.append({
                    "horizon_days": days,
                    "actual_return_percent": round(actual_return, 4),
                    "predicted_return_percent": predicted_return,
                    "predicted_probability": score.probability_positive,
                    "actual_direction_correct": (
                        actual_return >= 0 if score.action == "BUY" else actual_return < 0
                    ),
                    "excess_return_percent": (
                        round(actual_return - benchmark_return, 4)
                        if benchmark_return is not None else None
                    ),
                })

            results.append({
                "event_id": event_id,
                "symbol": score.symbol,
                "sector": getattr(stock, "sector", "UNKNOWN"),
                "event_type": getattr(event, "event_type", "UNKNOWN"),
                "opportunity_score": score.score,
                "action": score.action,
                "outcomes": outcomes,
            })

        return results
