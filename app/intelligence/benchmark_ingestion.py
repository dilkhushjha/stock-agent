from datetime import datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.benchmark_registry import BenchmarkRegistry
from app.models.market_data import MarketData
from app.models.stock import Stock


class BenchmarkIngestionService:
    """Stores benchmark OHLCV rows using the same MarketData schema as stocks.

    The service deliberately accepts normalized provider rows instead of coupling
    the intelligence layer to one external market-data vendor.
    """

    @staticmethod
    def ensure_benchmark_stock(db: Session, benchmark_symbol: str, name: str) -> Stock:
        stock = db.scalar(select(Stock).where(Stock.yahoo_symbol == benchmark_symbol))
        if stock:
            return stock

        stock = Stock(
            symbol=benchmark_symbol,
            yahoo_symbol=benchmark_symbol,
            company_name=name,
            sector="INDEX",
            industry="Benchmark Index",
            is_active=True,
        )
        db.add(stock)
        db.flush()
        return stock

    @classmethod
    def ingest_rows(
        cls,
        db: Session,
        benchmark_symbol: str,
        benchmark_name: str,
        rows: Iterable[dict],
    ) -> dict:
        stock = cls.ensure_benchmark_stock(db, benchmark_symbol, benchmark_name)
        inserted = 0
        skipped = 0

        for row in rows:
            timestamp = row.get("timestamp")
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).replace(tzinfo=None)
            if not timestamp:
                skipped += 1
                continue

            existing = db.scalar(
                select(MarketData).where(
                    MarketData.stock_id == stock.id,
                    MarketData.timestamp == timestamp,
                )
            )
            if existing:
                skipped += 1
                continue

            if any(row.get(field) is None for field in ("open", "high", "low", "close")):
                skipped += 1
                continue

            db.add(
                MarketData(
                    stock_id=stock.id,
                    timestamp=timestamp,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    adjusted_close=float(row["adjusted_close"]) if row.get("adjusted_close") is not None else None,
                    volume=int(row["volume"]) if row.get("volume") is not None else None,
                )
            )
            inserted += 1

        db.commit()
        return {
            "benchmark_symbol": benchmark_symbol,
            "benchmark_name": benchmark_name,
            "market_data_stock_id": stock.id,
            "inserted": inserted,
            "skipped": skipped,
        }

    @classmethod
    def ingest_registry_rows(cls, db: Session, rows_by_symbol: dict[str, Iterable[dict]]) -> list[dict]:
        results = []
        for benchmark in BenchmarkRegistry.all():
            rows = rows_by_symbol.get(benchmark.symbol, [])
            results.append(cls.ingest_rows(db, benchmark.symbol, benchmark.name, rows))
        return results
