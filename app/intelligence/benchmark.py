from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market_data import MarketData
from app.models.stock import Stock


class BenchmarkEngine:
    """Calculates stock returns relative to a stored benchmark instrument."""

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

    @classmethod
    def excess_return(
        cls,
        db: Session,
        stock: Stock,
        benchmark: Stock,
        event_time,
        horizon_days: int,
    ) -> dict:
        stock_base = cls._price_at_or_before(db, stock.id, event_time)
        benchmark_base = cls._price_at_or_before(db, benchmark.id, event_time)
        stock_future = cls._price_at_or_after(
            db, stock.id, event_time + timedelta(days=horizon_days)
        )
        benchmark_future = cls._price_at_or_after(
            db, benchmark.id, event_time + timedelta(days=horizon_days)
        )

        if not all((stock_base, benchmark_base, stock_future, benchmark_future)):
            return {"status": "INSUFFICIENT_DATA"}
        if not all((stock_base.close, benchmark_base.close)):
            return {"status": "INSUFFICIENT_DATA"}

        stock_return = (stock_future.close - stock_base.close) / stock_base.close * 100.0
        benchmark_return = (
            (benchmark_future.close - benchmark_base.close) / benchmark_base.close * 100.0
        )

        return {
            "status": "OK",
            "horizon_days": horizon_days,
            "stock_return_percent": round(stock_return, 2),
            "benchmark_return_percent": round(benchmark_return, 2),
            "excess_return_percent": round(stock_return - benchmark_return, 2),
            "outperformed": stock_return > benchmark_return,
        }
