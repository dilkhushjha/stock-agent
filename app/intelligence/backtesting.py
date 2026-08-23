from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.backtest import EventOutcome
from app.models.event import MarketEvent
from app.models.exposure import StockExposure
from app.models.market_data import MarketData
from app.models.stock import Stock


class EventBacktestService:

    @staticmethod
    def _calculate_return(
        prices: list[float],
        days: int,
    ) -> float | None:

        if len(prices) <= days:
            return None

        start_price = prices[0]
        end_price = prices[days]

        if start_price <= 0:
            return None

        return round(
            ((end_price - start_price) / start_price) * 100,
            2,
        )

    @staticmethod
    def calculate_event_outcome(
        db: Session,
        event_id: int,
    ) -> dict:

        event = db.scalar(
            select(MarketEvent).where(
                MarketEvent.id == event_id
            )
        )

        if not event:
            raise ValueError(
                f"Event {event_id} not found."
            )

        if not event.event_date:
            raise ValueError(
                "Event does not have an event_date."
            )

        exposures = db.scalars(
            select(StockExposure).where(
                StockExposure.entity == event.entity.upper()
            )
        ).all()

        if not exposures:
            raise ValueError(
                f"No exposures found for {event.entity}."
            )

        results = []

        start_datetime = event.event_date

        end_datetime = (
            start_datetime + timedelta(days=35)
        )

        for exposure in exposures:

            stock = db.scalar(
                select(Stock).where(
                    Stock.id == exposure.stock_id
                )
            )

            if not stock:
                continue

            market_rows = db.scalars(
                select(MarketData)
                .where(
                    MarketData.stock_id == stock.id,
                    MarketData.timestamp >= start_datetime,
                    MarketData.timestamp <= end_datetime,
                )
                .order_by(
                    MarketData.timestamp.asc()
                )
            ).all()

            if not market_rows:
                continue

            prices = [
                row.close
                for row in market_rows
            ]

            event_price = prices[0]

            outcome = EventOutcome(
                event_id=event.id,
                stock_id=stock.id,
                event_price=event_price,
                return_1d=(
                    EventBacktestService
                    ._calculate_return(prices, 1)
                ),
                return_5d=(
                    EventBacktestService
                    ._calculate_return(prices, 5)
                ),
                return_20d=(
                    EventBacktestService
                    ._calculate_return(prices, 20)
                ),
            )

            db.add(outcome)

            results.append(
                {
                    "symbol": stock.symbol,
                    "event_price": event_price,
                    "return_1d": outcome.return_1d,
                    "return_5d": outcome.return_5d,
                    "return_20d": outcome.return_20d,
                }
            )

        db.commit()

        return {
            "event_id": event.id,
            "entity": event.entity,
            "event_date": event.event_date,
            "results": results,
        }