import pandas as pd
import yfinance as yf

from app.data.market.sector_universe import (
    SECTOR_INDEX_MAP,
)


class SectorFeatureBuilder:

    @staticmethod
    def fetch_sector_data(
        sectors: list[str],
        start_date,
        end_date,
    ) -> dict[str, pd.DataFrame]:

        result = {}

        for sector in sectors:

            symbol = (
                SECTOR_INDEX_MAP
                .get(sector)
            )

            if not symbol:

                print(
                    f"[SECTOR] "
                    f"No index mapping for "
                    f"{sector}"
                )

                continue

            try:

                data = yf.download(
                    symbol,
                    start=start_date,
                    end=end_date,
                    interval="1d",
                    auto_adjust=False,
                    progress=False,
                )

                if data.empty:

                    print(
                        f"[SECTOR] "
                        f"No data for {sector}"
                    )

                    continue

                data = (
                    SectorFeatureBuilder
                    ._normalize(data)
                )

                # Remove rows without price
                data = data.dropna(
                    subset=["close"]
                )

                if data.empty:

                    continue

                data[
                    "sector_return_1d"
                ] = (
                    data["close"]
                    .pct_change(1)
                    * 100
                )

                data[
                    "sector_return_5d"
                ] = (
                    data["close"]
                    .pct_change(5)
                    * 100
                )

                data[
                    "sector_return_20d"
                ] = (
                    data["close"]
                    .pct_change(20)
                    * 100
                )

                # Remove rows where the
                # requested feature windows
                # are not yet available.
                data = data.dropna(
                    subset=[
                        "sector_return_1d",
                        "sector_return_5d",
                        "sector_return_20d",
                    ]
                )

                result[sector] = data[
                    [
                        "timestamp",
                        "sector_return_1d",
                        "sector_return_5d",
                        "sector_return_20d",
                    ]
                ].copy()

            except Exception as exc:

                print(
                    f"[SECTOR] "
                    f"{sector} failed: "
                    f"{exc}"
                )

        return result

    @staticmethod
    def _normalize(
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        df = dataframe.copy()

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

            df["timestamp"] = (
                pd.to_datetime(
                    df["date"]
                )
            )

        elif isinstance(
            df.index,
            pd.DatetimeIndex,
        ):

            df["timestamp"] = (
                pd.to_datetime(
                    df.index
                )
            )

        else:

            raise ValueError(
                "Unable to determine date."
            )

        df["timestamp"] = (
            df["timestamp"]
            .dt.tz_localize(None)
            .dt.normalize()
        )

        return df