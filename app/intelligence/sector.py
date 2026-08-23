from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.market.sectors import SECTOR_MAP
from app.models.market_data import MarketData
from app.models.stock import Stock


class SectorIntelligenceService:

    @staticmethod
    def get_sector_snapshot(
        db: Session,
        sector: str,
    ) -> dict:

        sector = sector.strip()

        symbols = [
            symbol
            for symbol, mapped_sector in SECTOR_MAP.items()
            if mapped_sector.lower() == sector.lower()
        ]

        if not symbols:
            raise ValueError(
                f"No stocks found for sector '{sector}'."
            )

        stocks = db.scalars(
            select(Stock).where(
                Stock.symbol.in_(symbols)
            )
        ).all()

        if not stocks:
            raise ValueError(
                f"No stored market data found for sector '{sector}'."
            )

        stock_results = []

        for stock in stocks:

            records = db.scalars(
                select(MarketData)
                .where(
                    MarketData.stock_id == stock.id
                )
                .order_by(
                    MarketData.timestamp.asc()
                )
            ).all()

            if not records:
                continue

            closes = [
                record.close
                for record in records
            ]

            latest_price = closes[-1]

            return_5d = None

            if len(closes) >= 6:
                return_5d = (
                    (closes[-1] / closes[-6]) - 1
                ) * 100

            stock_results.append(
                {
                    "symbol": stock.symbol,
                    "price": round(latest_price, 2),
                    "return_5d_percent": (
                        round(return_5d, 2)
                        if return_5d is not None
                        else None
                    ),
                }
            )

        valid_returns = [
            item["return_5d_percent"]
            for item in stock_results
            if item["return_5d_percent"] is not None
        ]

        sector_return = None

        if valid_returns:
            sector_return = (
                sum(valid_returns)
                / len(valid_returns)
            )

        if sector_return is None:
            sector_trend = "INSUFFICIENT_DATA"

        elif sector_return > 2:
            sector_trend = "STRONG_BULLISH"

        elif sector_return > 0:
            sector_trend = "BULLISH"

        elif sector_return < -2:
            sector_trend = "STRONG_BEARISH"

        else:
            sector_trend = "BEARISH"

        return {
            "sector": sector,
            "stocks_analyzed": len(stock_results),
            "average_5d_return_percent": (
                round(sector_return, 2)
                if sector_return is not None
                else None
            ),
            "sector_trend": sector_trend,
            "stocks": stock_results,
        }