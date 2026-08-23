from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.market.universe import INDIAN_STOCKS
from app.models.market_data import MarketData
from app.models.stock import Stock


class MarketAnalyticsService:

    @staticmethod
    def get_snapshot(
        db: Session,
        symbol: str,
    ) -> dict:

        symbol = symbol.upper()

        if symbol not in INDIAN_STOCKS:
            raise ValueError(
                f"{symbol} is not available in the stock universe."
            )

        stock = db.scalar(
            select(Stock).where(Stock.symbol == symbol)
        )

        if not stock:
            raise ValueError(
                f"No stored market data found for {symbol}. "
                f"Ingest data first."
            )

        records = db.scalars(
            select(MarketData)
            .where(MarketData.stock_id == stock.id)
            .order_by(MarketData.timestamp.asc())
        ).all()

        if not records:
            raise ValueError(
                f"No market data found for {symbol}."
            )

        closes = [record.close for record in records]
        volumes = [
            record.volume
            for record in records
            if record.volume is not None
        ]

        latest = records[-1]

        # --------------------------------------------------
        # Returns
        # --------------------------------------------------

        return_1d = None
        return_5d = None
        return_20d = None

        if len(closes) >= 2:
            return_1d = (
                (closes[-1] / closes[-2]) - 1
            ) * 100

        if len(closes) >= 6:
            return_5d = (
                (closes[-1] / closes[-6]) - 1
            ) * 100

        if len(closes) >= 21:
            return_20d = (
                (closes[-1] / closes[-21]) - 1
            ) * 100

        # --------------------------------------------------
        # Moving averages
        # --------------------------------------------------

        ma_5 = None
        ma_20 = None

        if len(closes) >= 5:
            ma_5 = sum(closes[-5:]) / 5

        if len(closes) >= 20:
            ma_20 = sum(closes[-20:]) / 20

        # --------------------------------------------------
        # Volume anomaly
        # --------------------------------------------------

        volume_ratio = None

        if len(volumes) >= 21:
            average_volume = sum(volumes[-21:-1]) / 20

            if average_volume > 0:
                volume_ratio = volumes[-1] / average_volume

        # --------------------------------------------------
        # Trend
        # --------------------------------------------------

        trend = "NEUTRAL"

        if ma_5 is not None and ma_20 is not None:

            if ma_5 > ma_20:
                trend = "BULLISH"

            elif ma_5 < ma_20:
                trend = "BEARISH"

        # --------------------------------------------------
        # Momentum
        # --------------------------------------------------

        momentum = "NEUTRAL"

        if return_5d is not None:

            if return_5d > 3:
                momentum = "STRONG_POSITIVE"

            elif return_5d > 1:
                momentum = "POSITIVE"

            elif return_5d < -3:
                momentum = "STRONG_NEGATIVE"

            elif return_5d < -1:
                momentum = "NEGATIVE"

        return {
            "symbol": symbol,
            "latest_price": latest.close,
            "latest_timestamp": latest.timestamp.isoformat(),

            "returns": {
                "1d_percent": round(return_1d, 2)
                if return_1d is not None
                else None,

                "5d_percent": round(return_5d, 2)
                if return_5d is not None
                else None,

                "20d_percent": round(return_20d, 2)
                if return_20d is not None
                else None,
            },

            "moving_averages": {
                "ma_5": round(ma_5, 2)
                if ma_5 is not None
                else None,

                "ma_20": round(ma_20, 2)
                if ma_20 is not None
                else None,
            },

            "volume_ratio": round(volume_ratio, 2)
            if volume_ratio is not None
            else None,

            "trend": trend,
            "momentum": momentum,

            "data_points": len(records),
        }