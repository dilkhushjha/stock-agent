from fastapi import APIRouter

from app.data.database import SessionLocal
from app.models.market_data import MarketData


router = APIRouter(
    prefix="/regime",
    tags=["Market Regime"],
)


@router.get("/")
def get_market_regime():

    db = SessionLocal()

    try:
        rows = (
            db.query(MarketData)
            .order_by(MarketData.timestamp.desc())
            .limit(60)
            .all()
        )

        if not rows:
            return {
                "regime": "UNKNOWN",
                "confidence": 0.0,
                "reason": "No market data available.",
                "metrics": {},
            }

        rows = list(reversed(rows))

        closes = [
            float(row.close)
            for row in rows
            if row.close is not None
        ]

        if len(closes) < 20:
            return {
                "regime": "UNKNOWN",
                "confidence": 0.0,
                "reason": "Insufficient market data.",
                "metrics": {},
            }

        current = closes[-1]

        close_5d = closes[-6] if len(closes) >= 6 else closes[0]
        close_20d = closes[-21] if len(closes) >= 21 else closes[0]

        return_5d = (
            (current / close_5d) - 1
        ) * 100

        return_20d = (
            (current / close_20d) - 1
        ) * 100

        sma20 = sum(closes[-20:]) / 20

        distance_sma20 = (
            (current / sma20) - 1
        ) * 100

        regime = "SIDEWAYS"

        if return_20d > 3 and distance_sma20 > 1:
            regime = "BULLISH"

        elif return_20d < -3 and distance_sma20 < -1:
            regime = "BEARISH"

        confidence = min(
            0.95,
            max(
                0.50,
                0.50
                + abs(return_20d) / 20
                + abs(distance_sma20) / 20,
            ),
        )

        if regime == "BULLISH":
            reason = (
                "Market is trading above its 20-day average "
                "with positive medium-term momentum."
            )

        elif regime == "BEARISH":
            reason = (
                "Market is trading below its 20-day average "
                "with negative medium-term momentum."
            )

        else:
            reason = (
                "Market momentum is mixed and does not show "
                "a strong directional trend."
            )

        return {
            "regime": regime,
            "confidence": round(confidence, 4),
            "reason": reason,
            "metrics": {
                "return_5d": round(return_5d, 4),
                "return_20d": round(return_20d, 4),
                "distance_sma20": round(
                    distance_sma20,
                    4,
                ),
            },
        }

    finally:
        db.close()