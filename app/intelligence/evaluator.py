from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.prediction import (
    SignalPrediction,
)

from app.models.market_data import (
    MarketData,
)


class PredictionEvaluator:

    @staticmethod
    def evaluate(
        db: Session,
    ):

        predictions = db.scalars(
            select(SignalPrediction).where(
                SignalPrediction.evaluated == 0
            )
        ).all()

        evaluated = 0

        for prediction in predictions:

            if prediction.price_at_signal is None:
                continue

            prices = PredictionEvaluator._get_prices(
                db,
                prediction,
            )

            prediction.return_1h = prices.get(
                "1h"
            )

            prediction.return_1d = prices.get(
                "1d"
            )

            prediction.return_3d = prices.get(
                "3d"
            )

            prediction.return_5d = prices.get(
                "5d"
            )

            # Only mark evaluated when
            # enough time has passed.
            signal_time = prediction.signal_time

            if (
                datetime.utcnow()
                - signal_time
            ).total_seconds() >= 5 * 86400:

                prediction.evaluated = 1

                evaluated += 1

        db.commit()

        return {
            "evaluated": evaluated,
        }

    @staticmethod
    def _get_prices(
        db: Session,
        prediction,
    ):

        result = {}

        horizons = {
            "1h": timedelta(hours=1),
            "1d": timedelta(days=1),
            "3d": timedelta(days=3),
            "5d": timedelta(days=5),
        }

        for name, delta in horizons.items():

            target_time = (
                prediction.signal_time
                + delta
            )

            price = db.scalar(
                select(MarketData.close)
                .where(
                    MarketData.stock_id
                    == prediction.stock_id,
                    MarketData.timestamp
                    >= target_time,
                )
                .order_by(
                    MarketData.timestamp.asc()
                )
                .limit(1)
            )

            if price is None:
                continue

            result[name] = round(
                (
                    price
                    - prediction.price_at_signal
                )
                / prediction.price_at_signal
                * 100,
                4,
            )

        return result