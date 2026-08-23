from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.backtest import EventOutcome
from app.models.event import MarketEvent
from app.models.stock import Stock

from app.intelligence.statistics import (
    OutcomeStatistics,
)


class HistoricalStatsService:

    @staticmethod
    def get_stock_statistics(
        db: Session,
        symbol: str,
    ) -> dict:

        stock = db.scalar(
            select(Stock).where(
                Stock.symbol == symbol
            )
        )

        if not stock:
            raise ValueError(
                f"Stock {symbol} not found."
            )

        outcomes = db.scalars(
            select(EventOutcome).where(
                EventOutcome.stock_id
                == stock.id
            )
        ).all()

        returns_1d = [
            outcome.return_1d
            for outcome in outcomes
        ]

        returns_5d = [
            outcome.return_5d
            for outcome in outcomes
        ]

        returns_20d = [
            outcome.return_20d
            for outcome in outcomes
        ]

        return {
            "symbol": symbol,

            "events": len(outcomes),

            "1d": OutcomeStatistics.calculate(
                returns_1d
            ),

            "5d": OutcomeStatistics.calculate(
                returns_5d
            ),

            "20d": OutcomeStatistics.calculate(
                returns_20d
            ),
        }