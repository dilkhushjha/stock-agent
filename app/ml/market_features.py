import pandas as pd
import numpy as np
import yfinance as yf


class MarketFeatureBuilder:
    """
    Builds broad Indian market features using NIFTY 50
    and INDIA VIX.
    """

    NIFTY_SYMBOL = "^NSEI"
    VIX_SYMBOL = "^INDIAVIX"

    @staticmethod
    def fetch_market_data(
        start_date,
        end_date,
    ) -> pd.DataFrame:

        nifty = yf.download(
            MarketFeatureBuilder.NIFTY_SYMBOL,
            start=start_date,
            end=end_date,
            interval="1d",
            auto_adjust=False,
            progress=False,
        )

        vix = yf.download(
            MarketFeatureBuilder.VIX_SYMBOL,
            start=start_date,
            end=end_date,
            interval="1d",
            auto_adjust=False,
            progress=False,
        )

        if nifty.empty:
            raise ValueError(
                "Unable to fetch NIFTY 50 data."
            )

        nifty = (
            MarketFeatureBuilder
            ._normalize_columns(nifty)
        )

        nifty["nifty_return_1d"] = (
            nifty["close"].pct_change(1) * 100
        )

        nifty["nifty_return_5d"] = (
            nifty["close"].pct_change(5) * 100
        )

        nifty["nifty_return_20d"] = (
            nifty["close"].pct_change(20) * 100
        )

        nifty["nifty_volatility_20d"] = (
            nifty["close"]
            .pct_change()
            .rolling(20)
            .std()
            * np.sqrt(252)
            * 100
        )

        nifty["nifty_sma20"] = (
            nifty["close"]
            .rolling(20)
            .mean()
        )

        nifty["nifty_sma50"] = (
            nifty["close"]
            .rolling(50)
            .mean()
        )

        nifty["nifty_sma20_distance"] = (
            (
                nifty["close"]
                / nifty["nifty_sma20"]
            ) - 1
        ) * 100

        nifty["nifty_sma50_distance"] = (
            (
                nifty["close"]
                / nifty["nifty_sma50"]
            ) - 1
        ) * 100

        result_columns = [
            "timestamp",
            "nifty_return_1d",
            "nifty_return_5d",
            "nifty_return_20d",
            "nifty_volatility_20d",
            "nifty_sma20_distance",
            "nifty_sma50_distance",
        ]

        result = nifty[result_columns].copy()

        if not vix.empty:

            vix = (
                MarketFeatureBuilder
                ._normalize_columns(vix)
            )

            vix["india_vix"] = vix["close"]

            vix_result = vix[
                [
                    "timestamp",
                    "india_vix",
                ]
            ].copy()

            result = result.merge(
                vix_result,
                on="timestamp",
                how="left",
            )

        else:

            result["india_vix"] = np.nan

        return result

    @staticmethod
    def _normalize_columns(
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        df = dataframe.copy()

        # yfinance can return a MultiIndex
        # depending on the installed version.

        if isinstance(
            df.columns,
            pd.MultiIndex,
        ):

            df.columns = [
                column[0]
                for column in df.columns
            ]

        df.columns = [
            str(column).lower()
            for column in df.columns
        ]

        if "date" in df.columns:

            df["timestamp"] = pd.to_datetime(
                df["date"]
            )

        elif "datetime" in df.columns:

            df["timestamp"] = pd.to_datetime(
                df["datetime"]
            )

        elif isinstance(
            df.index,
            pd.DatetimeIndex,
        ):

            df["timestamp"] = pd.to_datetime(
                df.index
            )

        else:

            raise ValueError(
                "Could not determine date column."
            )

        df["timestamp"] = (
            df["timestamp"]
            .dt.tz_localize(None)
        )

        return df