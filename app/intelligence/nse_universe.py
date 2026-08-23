from __future__ import annotations

import csv
import io
from urllib.request import Request, urlopen

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.stock import Stock

NSE_EQUITY_CSV = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"


class NSEUniverseService:
    """Keep the StockAgent universe aligned with the listed NSE equity universe."""

    @classmethod
    def sync(cls, db: Session) -> dict:
        request = Request(NSE_EQUITY_CSV, headers={"User-Agent": "Mozilla/5.0 StockAgent/1.0", "Accept": "text/csv,*/*"})
        with urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8-sig")

        reader = csv.DictReader(io.StringIO(payload))
        inserted = updated = 0
        seen = set()
        for row in reader:
            symbol = (row.get("SYMBOL") or "").strip().upper()
            series = (row.get(" SERIES") or row.get("SERIES") or "").strip().upper()
            name = (row.get("NAME OF COMPANY") or "").strip()
            if not symbol or series not in {"EQ", "BE", "BZ"}:
                continue
            seen.add(symbol)
            stock = db.scalar(select(Stock).where(Stock.symbol == symbol))
            if stock:
                stock.company_name = name or stock.company_name
                stock.yahoo_symbol = f"{symbol}.NS"
                stock.is_active = True
                if stock.sector == "INDEX":
                    stock.sector = None
                updated += 1
            else:
                db.add(Stock(symbol=symbol, yahoo_symbol=f"{symbol}.NS", company_name=name or symbol, is_active=True))
                inserted += 1
        db.commit()
        active = db.scalar(select(func.count(Stock.id)).where(Stock.is_active.is_(True))) or 0
        return {"source": NSE_EQUITY_CSV, "nse_equities_seen": len(seen), "inserted": inserted, "updated": updated, "active_universe": active, "next_step": "Run market-data sync to populate OHLCV for the expanded universe."}
