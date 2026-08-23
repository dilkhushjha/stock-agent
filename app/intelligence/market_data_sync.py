from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.benchmark_ingestion import BenchmarkIngestionService
from app.intelligence.benchmark_registry import BenchmarkRegistry
from app.intelligence.market_data_provider import YahooFinanceProvider
from app.models.market_data import MarketData
from app.models.stock import Stock


class MarketDataSyncService:
    """Synchronize daily OHLCV data for the broad active NSE universe.

    Yahoo Finance rate-limits aggressive parallel chart requests. The bootstrap
    path therefore deliberately uses a conservative worker ceiling; reliability
    is more important than shaving a few minutes from a multi-thousand-stock load.
    """

    def __init__(self, provider=None):
        self.provider = provider or YahooFinanceProvider()

    @staticmethod
    def _upsert_rows(db: Session, stock: Stock, rows: list[dict]) -> tuple[int, int]:
        inserted = updated = 0
        if not rows:
            return inserted, updated

        timestamps = [row.get("timestamp") for row in rows if row.get("timestamp")]
        existing_rows = db.scalars(
            select(MarketData).where(
                MarketData.stock_id == stock.id,
                MarketData.timestamp.in_(timestamps),
            )
        ).all()
        existing = {row.timestamp: row for row in existing_rows}

        for row in rows:
            timestamp = row.get("timestamp")
            if not timestamp or any(row.get(field) is None for field in ("open", "high", "low", "close")):
                continue

            values = {
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "adjusted_close": float(row["adjusted_close"]) if row.get("adjusted_close") is not None else None,
                "volume": int(row["volume"]) if row.get("volume") is not None else None,
            }
            current = existing.get(timestamp)
            if current:
                for key, value in values.items():
                    setattr(current, key, value)
                updated += 1
            else:
                db.add(MarketData(stock_id=stock.id, timestamp=timestamp, **values))
                inserted += 1
        return inserted, updated

    def _fetch(self, symbol: str, start: datetime, end: datetime) -> tuple[str, list[dict], str | None]:
        try:
            return symbol, self.provider.history(symbol, start, end), None
        except Exception as exc:
            return symbol, [], str(exc)

    def sync(
        self,
        db: Session,
        history_days: int = 5,
        limit: int | None = None,
        workers: int = 2,
    ) -> dict:
        """Sync a recent window for live operation or a larger window for bootstrap.

        Use history_days=365/730 for historical bootstrap. The live scheduler should
        use a small window because historical rows are already persisted.
        Yahoo requests are intentionally capped at four concurrent workers and
        normally run with two to avoid provider throttling.
        """
        end = datetime.utcnow()
        start = end - timedelta(days=max(1, history_days))

        query = select(Stock).where(
            Stock.is_active.is_(True),
            Stock.exchange == "NSE",
            Stock.symbol.is_not(None),
        ).order_by(Stock.symbol)
        stocks = db.scalars(query).all()
        if limit is not None:
            stocks = stocks[:max(0, limit)]

        fetch_results = {}
        stock_failures = []
        worker_count = max(1, min(int(workers), 4))
        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            futures = {
                pool.submit(self._fetch, stock.yahoo_symbol, start, end): stock
                for stock in stocks
                if stock.yahoo_symbol
            }
            for future in as_completed(futures):
                stock = futures[future]
                symbol, rows, error = future.result()
                fetch_results[stock.id] = rows
                if error:
                    stock_failures.append({"symbol": symbol, "error": error})

        inserted = updated = successful = 0
        results = []
        for stock in stocks:
            rows = fetch_results.get(stock.id, [])
            if rows:
                ins, upd = self._upsert_rows(db, stock, rows)
                inserted += ins
                updated += upd
                successful += 1
                results.append({"symbol": stock.symbol, "rows": len(rows), "inserted": ins, "updated": upd})
            else:
                results.append({"symbol": stock.symbol, "rows": 0, "error": "No data returned"})

        benchmark_failures = []
        for benchmark in BenchmarkRegistry.all():
            try:
                rows = self.provider.history(benchmark.symbol, start, end)
                benchmark_stock = BenchmarkIngestionService.ensure_benchmark_stock(
                    db, benchmark.symbol, benchmark.name
                )
                ins, upd = self._upsert_rows(db, benchmark_stock, rows)
                inserted += ins
                updated += upd
                results.append({"symbol": benchmark.symbol, "rows": len(rows), "inserted": ins, "updated": upd})
            except Exception as exc:
                benchmark_failures.append({"symbol": benchmark.symbol, "error": str(exc)})

        db.commit()
        return {
            "history_days": history_days,
            "requested_stocks": len(stocks),
            "successful_stocks": successful,
            "failed_stocks": len(stock_failures),
            "inserted_rows": inserted,
            "updated_rows": updated,
            "failed": stock_failures,
            "benchmark_failures": benchmark_failures,
            "results": results,
        }
