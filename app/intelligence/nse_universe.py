from __future__ import annotations

import csv
import io
from urllib.request import Request, urlopen

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.stock import Stock

NSE_EQUITY_CSV = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
ALLOWED_SERIES = {"EQ", "BE", "BZ"}


class NSEUniverseService:
    """Synchronize the active NSE cash-equity universe.

    This service deliberately does not invent sectors. NSE's equity master is the
    authoritative security master; sector/industry must come from a classification
    source rather than an LLM or arbitrary fallback label.
    """

    @classmethod
    def sync(cls, db: Session) -> dict:
        request = Request(
            NSE_EQUITY_CSV,
            headers={
                "User-Agent": "Mozilla/5.0 StockAgent/1.0",
                "Accept": "text/csv,*/*",
            },
        )
        with urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8-sig")

        reader = csv.DictReader(io.StringIO(payload))
        inserted = updated = skipped = 0
        seen = set()

        for row in reader:
            symbol = (row.get("SYMBOL") or "").strip().upper()
            series = (row.get(" SERIES") or row.get("SERIES") or "").strip().upper()
            name = (row.get("NAME OF COMPANY") or "").strip()
            isin = (row.get(" ISIN NUMBER") or row.get("ISIN NUMBER") or "").strip().upper()

            if not symbol or series not in ALLOWED_SERIES:
                skipped += 1
                continue

            seen.add(symbol)
            stock = db.scalar(select(Stock).where(Stock.symbol == symbol))

            if stock:
                stock.company_name = name or stock.company_name
                stock.yahoo_symbol = f"{symbol}.NS"
                stock.exchange = "NSE"
                stock.isin = isin or stock.isin
                stock.series = series
                stock.is_active = True
                updated += 1
            else:
                db.add(
                    Stock(
                        symbol=symbol,
                        yahoo_symbol=f"{symbol}.NS",
                        exchange="NSE",
                        isin=isin or None,
                        series=series,
                        company_name=name or symbol,
                        is_active=True,
                    )
                )
                inserted += 1

        # Anything previously marked active but absent from today's master is no
        # longer part of the current NSE equity universe.
        if seen:
            active_rows = db.scalars(select(Stock).where(Stock.exchange == "NSE", Stock.is_active.is_(True))).all()
            for stock in active_rows:
                if stock.symbol not in seen:
                    stock.is_active = False

        db.commit()
        active = db.scalar(
            select(func.count(Stock.id)).where(Stock.exchange == "NSE", Stock.is_active.is_(True))
        ) or 0
        classified = db.scalar(
            select(func.count(Stock.id)).where(
                Stock.exchange == "NSE",
                Stock.is_active.is_(True),
                Stock.sector.is_not(None),
                Stock.sector != "",
            )
        ) or 0

        return {
            "source": NSE_EQUITY_CSV,
            "universe": "NSE cash equities",
            "nse_equities_seen": len(seen),
            "inserted": inserted,
            "updated": updated,
            "deactivated": max(0, len(seen) - active) if False else None,
            "skipped": skipped,
            "active_universe": active,
            "sector_classified": classified,
            "sector_unclassified": max(0, active - classified),
            "sector_status": "classification_required",
            "next_step": "Populate NSE/BSE canonical sector and industry classification before sector-aware recommendations.",
        }
