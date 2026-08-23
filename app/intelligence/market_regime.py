from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class MarketRegime:
    name: str
    confidence: float
    reason: str

    @property
    def regime(self):
        return self.name


class MarketRegimeDetector:
    """
    Detects broad market regime from OHLCV data.

    Expected dataframe columns:
        timestamp
        close

    Optional:
        open
        high
        low
        volume
    """

    def __init__(
        self,
        sma_fast: int = 20,
        sma_slow: int = 50,
        volatility_window: int = 20,
    ):
        self.sma_fast = sma_fast
        self.sma_slow = sma_slow
        self.volatility_window = volatility_window

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def detect(
        self,
        data: pd.DataFrame,
    ) -> MarketRegime:

        if data is None or data.empty:
            return MarketRegime(
                name="UNKNOWN",
                confidence=0.0,
                reason="No market data available.",
            )

        df = data.copy()

        if "close" not in df.columns:
            return MarketRegime(
                name="UNKNOWN",
                confidence=0.0,
                reason="Market data does not contain close prices.",
            )

        df["close"] = pd.to_numeric(
            df["close"],
            errors="coerce",
        )

        df = df.dropna(
            subset=["close"]
        )

        if len(df) < self.sma_fast:
            return MarketRegime(
                name="UNKNOWN",
                confidence=0.0,
                reason="Insufficient market data.",
            )

        close = df["close"]

        sma_fast = (
            close
            .rolling(self.sma_fast)
            .mean()
            .iloc[-1]
        )

        if len(df) >= self.sma_slow:
            sma_slow = (
                close
                .rolling(self.sma_slow)
                .mean()
                .iloc[-1]
            )
        else:
            sma_slow = sma_fast

        current_price = float(
            close.iloc[-1]
        )

        # ------------------------------------------------------
        # Returns
        # ------------------------------------------------------

        return_5d = self._return(
            close,
            5,
        )

        return_20d = self._return(
            close,
            20,
        )

        # ------------------------------------------------------
        # SMA distances
        # ------------------------------------------------------

        distance_fast = (
            (current_price / sma_fast) - 1
        ) * 100

        distance_slow = (
            (current_price / sma_slow) - 1
        ) * 100

        # ------------------------------------------------------
        # Volatility
        # ------------------------------------------------------

        returns = (
            close
            .pct_change()
            .dropna()
        )

        if len(returns) >= self.volatility_window:
            volatility = (
                returns
                .tail(self.volatility_window)
                .std()
                * np.sqrt(252)
                * 100
            )
        else:
            volatility = (
                returns.std()
                * np.sqrt(252)
                * 100
            )

        # ------------------------------------------------------
        # Trend score
        # ------------------------------------------------------

        score = 0.0

        if current_price > sma_fast:
            score += 1.0
        else:
            score -= 1.0

        if current_price > sma_slow:
            score += 1.0
        else:
            score -= 1.0

        if return_5d > 0:
            score += 0.5
        else:
            score -= 0.5

        if return_20d > 0:
            score += 1.0
        else:
            score -= 1.0

        # ------------------------------------------------------
        # Regime
        # ------------------------------------------------------

        if score >= 2.5:

            regime = "BULLISH"

            confidence = self._confidence(
                score,
                4.0,
            )

            reason = (
                "Price is above key moving averages "
                "with positive short and medium-term momentum."
            )

        elif score <= -2.5:

            regime = "BEARISH"

            confidence = self._confidence(
                abs(score),
                4.0,
            )

            reason = (
                "Price is below key moving averages "
                "with negative short and medium-term momentum."
            )

        else:

            regime = "SIDEWAYS"

            confidence = 0.50 + (
                abs(score) / 4.0
            ) * 0.20

            reason = (
                "Market momentum is mixed and "
                "does not show a strong directional trend."
            )

        # ------------------------------------------------------
        # High volatility adjustment
        # ------------------------------------------------------

        if volatility > 35:

            confidence *= 0.90

            reason += (
                " Volatility is elevated, reducing confidence."
            )

        confidence = min(
            0.95,
            max(
                0.50,
                confidence,
            ),
        )

        return MarketRegime(
            name=regime,
            confidence=round(
                confidence,
                4,
            ),
            reason=reason,
        )

    # ==========================================================
    # ALIASES
    # ==========================================================

    def detect_regime(
        self,
        data: pd.DataFrame,
    ) -> MarketRegime:

        return self.detect(data)

    # ==========================================================
    # HELPERS
    # ==========================================================

    @staticmethod
    def _return(
        close: pd.Series,
        periods: int,
    ) -> float:

        if len(close) <= periods:
            return 0.0

        previous = float(
            close.iloc[-periods - 1]
        )

        current = float(
            close.iloc[-1]
        )

        if previous == 0:
            return 0.0

        return (
            (current / previous) - 1
        ) * 100

    @staticmethod
    def _confidence(
        value: float,
        maximum: float,
    ) -> float:

        strength = min(
            1.0,
            value / maximum,
        )

        return (
            0.50
            + strength * 0.45
        )


# ==============================================================
# BACKWARD-COMPATIBLE FUNCTION
# ==============================================================

def detect_market_regime(
    data: pd.DataFrame,
) -> MarketRegime:

    detector = MarketRegimeDetector()

    return detector.detect(
        data
    )
