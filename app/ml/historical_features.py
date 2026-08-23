import pandas as pd
import numpy as np


class HistoricalFeatureBuilder:

    FEATURE_COLUMNS = [
        "return_1d",
        "return_5d",
        "return_20d",
        "volatility_5d",
        "volatility_20d",
        "sma20_distance",
        "sma50_distance",
        "volume_ratio",
        "high_low_range",
        "close_position",
        "momentum_5d",
        "momentum_20d",
    ]

    TARGET_COLUMNS = [
        "target_return_5d",
        "target_return_10d",
        "target_return_20d",
    ]

    @staticmethod
    def build(
        data: pd.DataFrame,
    ) -> pd.DataFrame:

        df = data.copy()

        if df.empty:
            return df

        df = (
            df.sort_values("timestamp")
            .reset_index(drop=True)
        )

        # -----------------------------------------
        # Historical returns
        # -----------------------------------------

        df["return_1d"] = (
            df["close"]
            .pct_change(1)
            * 100
        )

        df["return_5d"] = (
            df["close"]
            .pct_change(5)
            * 100
        )

        df["return_20d"] = (
            df["close"]
            .pct_change(20)
            * 100
        )

        # -----------------------------------------
        # Volatility
        # -----------------------------------------

        daily_returns = (
            df["close"].pct_change()
        )

        df["volatility_5d"] = (
            daily_returns
            .rolling(5)
            .std()
            * np.sqrt(252)
            * 100
        )

        df["volatility_20d"] = (
            daily_returns
            .rolling(20)
            .std()
            * np.sqrt(252)
            * 100
        )

        # -----------------------------------------
        # Moving averages
        # -----------------------------------------

        df["sma20"] = (
            df["close"]
            .rolling(20)
            .mean()
        )

        df["sma50"] = (
            df["close"]
            .rolling(50)
            .mean()
        )

        df["sma20_distance"] = (
            (
                df["close"]
                / df["sma20"]
            ) - 1
        ) * 100

        df["sma50_distance"] = (
            (
                df["close"]
                / df["sma50"]
            ) - 1
        ) * 100

        # -----------------------------------------
        # Volume
        # -----------------------------------------

        volume_average = (
            df["volume"]
            .rolling(20)
            .mean()
        )

        df["volume_ratio"] = (
            df["volume"]
            / volume_average
        )

        # -----------------------------------------
        # Price structure
        # -----------------------------------------

        df["high_low_range"] = (
            (
                df["high"]
                - df["low"]
            )
            / df["close"]
        ) * 100

        df["close_position"] = (
            (
                df["close"]
                - df["low"]
            )
            /
            (
                df["high"]
                - df["low"]
                + 1e-9
            )
        )

        # -----------------------------------------
        # Momentum
        # -----------------------------------------

        df["momentum_5d"] = (
            (
                df["close"]
                / df["close"].shift(5)
            ) - 1
        ) * 100

        df["momentum_20d"] = (
            (
                df["close"]
                / df["close"].shift(20)
            ) - 1
        ) * 100

        # -----------------------------------------
        # Future targets
        # -----------------------------------------

        df["target_return_5d"] = (
            (
                df["close"].shift(-5)
                / df["close"]
            ) - 1
        ) * 100

        df["target_return_10d"] = (
            (
                df["close"].shift(-10)
                / df["close"]
            ) - 1
        ) * 100

        df["target_return_20d"] = (
            (
                df["close"].shift(-20)
                / df["close"]
            ) - 1
        ) * 100

        # -----------------------------------------
        # Report data availability
        # -----------------------------------------

        required_columns = (
            HistoricalFeatureBuilder
            .FEATURE_COLUMNS
            +
            HistoricalFeatureBuilder
            .TARGET_COLUMNS
        )

        usable_before_drop = (
            df[required_columns]
            .notna()
            .all(axis=1)
            .sum()
        )

        print(
            f"[FEATURES] "
            f"Raw rows: {len(df)} | "
            f"Usable rows: {usable_before_drop}"
        )

        # -----------------------------------------
        # Remove unusable rows
        # -----------------------------------------

        df = df.dropna(
            subset=required_columns
        )

        return df