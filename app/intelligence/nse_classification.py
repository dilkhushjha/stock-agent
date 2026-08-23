from __future__ import annotations

import time
from datetime import datetime, timezone

import requests
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.stock import Stock

NSE_QUOTE_URL = "https://www.nseindia.com/api/quote-equity"
NSE_HOME = "https://www.nseindia.com/"


class NSEClassificationService:
    """Populate the official NSE Indices four-level company classification.

    NSE's quote endpoint exposes the company's Macro-Economic Sector, Sector,
    Industry and Basic Industry. We persist those values verbatim; no heuristic
    or LLM classification is used.
    """

    @classmethod
    def sync(cls, db: Session, limit: int | None = None, pause_seconds: float = 0.15) -> dict:
        stocks = db.scalars(
            select(Stock)
            .where(Stock.exchange == "NSE", Stock.is_active.is_(True))
            .order_by(Stock.symbol)
        ).all()
        if limit:
            stocks = stocks[:limit]

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151.0 Safari/537.36",
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": NSE_HOME,
            "Connection": "keep-alive",
        })

        # Establish NSE cookies before API calls.
        session.get(NSE_HOME, timeout=20)

        updated = skipped = failed = 0
        failures: list[dict] = []
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        for stock in stocks:
            try:
                response = session.get(
                    NSE_QUOTE_URL,
                    params={"symbol": stock.symbol},
                    timeout=20,
                )
                response.raise_for_status()
                payload = response.json()
                info = payload.get("industryInfo") or {}

                sector = info.get("sector")
                industry = info.get("industry")
                basic = info.get("basicIndustry")
                macro = info.get("macro") or info.get("macroEconomicSector")

                if not any((sector, industry, basic, macro)):
                    skipped += 1
                    failures.append({"symbol": stock.symbol, "reason": "NSE returned no industryInfo"})
                    continue

                stock.macro_economic_sector = macro
                stock.sector = sector
                stock.industry = industry
                stock.basic_industry = basic
                stock.sector_source = "NSE_INDICES"
                stock.classification_updated_at = now
                updated += 1
            except Exception as exc:
                failed += 1
                failures.append({"symbol": stock.symbol, "reason": str(exc)[:200]})

            if pause_seconds:
                time.sleep(pause_seconds)

        db.commit()

        total = db.scalar(
            select(func.count(Stock.id)).where(Stock.exchange == "NSE", Stock.is_active.is_(True))
        ) or 0
        classified = db.scalar(
            select(func.count(Stock.id)).where(
                Stock.exchange == "NSE",
                Stock.is_active.is_(True),
                Stock.sector_source == "NSE_INDICES",
            )
        ) or 0

        return {
            "source": "NSE Indices industry classification",
            "stocks_requested": len(stocks),
            "updated": updated,
            "skipped": skipped,
            "failed": failed,
            "active_nse_universe": total,
            "classified": classified,
            "unclassified": max(0, total - classified),
            "failures": failures[:50],
        }
