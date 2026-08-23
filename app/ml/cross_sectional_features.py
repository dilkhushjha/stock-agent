import pandas as pd


class CrossSectionalFeatureBuilder:
    """
    Builds stock-relative features.

    These features measure how strongly a stock is
    performing relative to:
        1. The broad market (NIFTY 50)
        2. The stock's own sector

    All calculations use information available on
    the same timestamp.
    """

    FEATURE_COLUMNS = [
        "relative_market_return_1d",
        "relative_market_return_5d",
        "relative_market_return_20d",
        "relative_sector_return_1d",
        "relative_sector_return_5d",
        "relative_sector_return_20d",
        "market_rank_5d",
        "market_rank_20d",
        "sector_rank_5d",
        "sector_rank_20d",
    ]

    @staticmethod
    def build(
        stock_data: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Add cross-sectional features to the stock dataset.

        Expected columns:

        Stock:
            symbol
            timestamp
            return_1d
            return_5d
            return_20d

        Market:
            nifty_return_1d
            nifty_return_5d
            nifty_return_20d

        Sector:
            sector_return_1d
            sector_return_5d
            sector_return_20d

        Optional:
            sector
        """

        df = stock_data.copy()

        if df.empty:
            return df

        required = [
            "timestamp",
            "return_1d",
            "return_5d",
            "return_20d",
            "nifty_return_1d",
            "nifty_return_5d",
            "nifty_return_20d",
            "sector_return_1d",
            "sector_return_5d",
            "sector_return_20d",
        ]

        missing = [
            column
            for column in required
            if column not in df.columns
        ]

        if missing:
            raise ValueError(
                "Missing columns required for "
                f"cross-sectional features: {missing}"
            )

        # --------------------------------------------------
        # Normalize timestamp
        # --------------------------------------------------

        df["timestamp"] = pd.to_datetime(
            df["timestamp"]
        ).dt.normalize()

        # --------------------------------------------------
        # Relative performance vs NIFTY
        # --------------------------------------------------

        df["relative_market_return_1d"] = (
            df["return_1d"]
            - df["nifty_return_1d"]
        )

        df["relative_market_return_5d"] = (
            df["return_5d"]
            - df["nifty_return_5d"]
        )

        df["relative_market_return_20d"] = (
            df["return_20d"]
            - df["nifty_return_20d"]
        )

        # --------------------------------------------------
        # Relative performance vs sector
        # --------------------------------------------------

        df["relative_sector_return_1d"] = (
            df["return_1d"]
            - df["sector_return_1d"]
        )

        df["relative_sector_return_5d"] = (
            df["return_5d"]
            - df["sector_return_5d"]
        )

        df["relative_sector_return_20d"] = (
            df["return_20d"]
            - df["sector_return_20d"]
        )

        # --------------------------------------------------
        # Cross-sectional market ranking
        #
        # Rank stocks against all stocks on the
        # same trading date.
        #
        # pct=True gives values between 0 and 1.
        # Higher = stronger relative performance.
        # --------------------------------------------------

        df["market_rank_5d"] = (
            df.groupby("timestamp")[
                "return_5d"
            ]
            .rank(
                method="average",
                pct=True,
            )
        )

        df["market_rank_20d"] = (
            df.groupby("timestamp")[
                "return_20d"
            ]
            .rank(
                method="average",
                pct=True,
            )
        )

        # --------------------------------------------------
        # Sector rankings
        #
        # Rank stocks only against their own sector.
        # --------------------------------------------------

        if "sector" in df.columns:

            df["sector_rank_5d"] = (
                df.groupby(
                    ["timestamp", "sector"],
                    dropna=False,
                )["return_5d"]
                .rank(
                    method="average",
                    pct=True,
                )
            )

            df["sector_rank_20d"] = (
                df.groupby(
                    ["timestamp", "sector"],
                    dropna=False,
                )["return_20d"]
                .rank(
                    method="average",
                    pct=True,
                )
            )

        else:

            # Sector information is not available.
            # Keep the columns so the final feature
            # schema remains consistent.
            df["sector_rank_5d"] = pd.NA
            df["sector_rank_20d"] = pd.NA

        return df
