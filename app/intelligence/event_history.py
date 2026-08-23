from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import MarketEvent
from app.models.exposure import StockExposure
from app.models.stock import Stock
from app.models.market_data import MarketData
from app.models.backtest import EventOutcome


class EventHistoryService:

    @staticmethod
    def build_outcome(
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
                StockExposure.entity
                == event.entity.upper()
            )
        ).all()

        if not exposures:
            return {
                "event_id": event.id,
                "entity": event.entity,
                "stocks": [],
            }

        results = []

        for exposure in exposures:

            stock = db.scalar(
                select(Stock).where(
                    Stock.id == exposure.stock_id
                )
            )

            if not stock:
                continue

            rows = db.scalars(
                select(MarketData)
                .where(
                    MarketData.stock_id == stock.id,
                    MarketData.timestamp
                    >= event.event_date,
                )
                .order_by(
                    MarketData.timestamp.asc()
                )
                .limit(21)
            ).all()

            if not rows:
                continue

            event_price = rows[0].close

            def future_return(days: int):

                if len(rows) <= days:
                    return None

                future_price = rows[days].close

                if not event_price:
                    return None

                return round(
                    (
                        (future_price - event_price)
                        / event_price
                    ) * 100,
                    2,
                )

            existing = db.scalar(
                select(EventOutcome).where(
                    EventOutcome.event_id
                    == event.id,
                    EventOutcome.stock_id
                    == stock.id,
                )
            )

            if existing:

                outcome = existing

                outcome.event_price = event_price
                outcome.return_1d = future_return(1)
                outcome.return_5d = future_return(5)
                outcome.return_20d = future_return(20)

            else:

                outcome = EventOutcome(
                    event_id=event.id,
                    stock_id=stock.id,
                    event_price=event_price,
                    return_1d=future_return(1),
                    return_5d=future_return(5),
                    return_20d=future_return(20),
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
            "stocks": results,
        }
