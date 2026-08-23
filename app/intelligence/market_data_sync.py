from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.benchmark_ingestion import BenchmarkIngestionService
from app.intelligence.benchmark_registry import BenchmarkRegistry
from app.intelligence.market_data_provider import YahooFinanceProvider
from app.models.market_data import MarketData
from app.models.stock import Stock


class MarketDataSyncService:
    """Synchronizes daily OHLCV data for active stocks and registered benchmarks."""

    def __init__(self, provider=None):
        self.provider = provider or YahooFinanceProvider()

    @staticmethod
    def _upsert_rows(db: Session, stock: Stock, rows: list[dict]) -> tuple[int, int]:
        inserted = updated = 0
        for row in rows:
            timestamp = row.get("timestamp")
            if not timestamp or any(row.get(field) is None for field in ("open", "high", "low", "close")):
                continue
            existing = db.scalar(
                select(MarketData).where(
                    MarketData.stock_id == stock.id,
                    MarketData.timestamp == timestamp,
                )
            )
            values = {
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "adjusted_close": float(row["adjusted_close"]) if row.get("adjusted_close") is not None else None,
                "volume": int(row["volume"]) if row.get("volume") is not None else None,
            }
            if existing:
                for key, value in values.items():
                    setattr(existing, key, value)
                updated += 1
            else:
                db.add(MarketData(stock_id=stock.id, timestamp=timestamp, **values))
                inserted += 1
        return inserted, updated

    def sync(self, db: Session, history_days: int = 365) -> dict:
        end = datetime.utcnow()
        start = end - timedelta(days=history_days)
        results = []

        stocks = db.scalars(
            select(Stock).where(Stock.is_active == True, Stock.sector != "INDEX")
        ).all()
        for stock in stocks:
            try:
                rows = self.provider.history(stock.yahoo_symbol, start, end)
                inserted, updated = self._upsert_rows(db, stock, rows)
                results.append({"symbol": stock.symbol, "inserted": inserted, "updated": updated})
            except Exception as exc:
                results.append({"symbol": stock.symbol, "error": str(exc)})

        for benchmark in BenchmarkRegistry.all():
            try:
                rows = self.provider.history(benchmark.symbol, start, end)
                benchmark_stock = BenchmarkIngestionService.ensure_benchmark_stock(
                    db, benchmark.symbol, benchmark.name
                )
                inserted, updated = self._upsert_rows(db, benchmark_stock, rows)
                results.append({"symbol": benchmark.symbol, "inserted": inserted, "updated": updated})
            except Exception as exc:
                results.append({"symbol": benchmark.symbol, "error": str(exc)})

        db.commit()
        return {
            "stocks": len(stocks),
            "instruments": len(results),
            "successful": sum("error" not in result for result in results),
            "failed": sum("error" in result for result in results),
            "results": results,
        }
