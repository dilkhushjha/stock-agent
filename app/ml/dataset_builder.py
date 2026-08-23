import numpy as np
import pandas as pd

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.stock import Stock
from app.models.market_data import MarketData

from app.ml.historical_features import (
    HistoricalFeatureBuilder,
)

from app.ml.market_features import (
    MarketFeatureBuilder,
)

from app.ml.sector_features import (
    SectorFeatureBuilder,
)


class DatasetBuilder:
    """
    Builds the complete cross-stock ML dataset.

    TATAMOTORS remains in the stock universe but is skipped
    automatically when no market data exists.
    """

    # ==========================================================
    # LOAD STOCK MARKET DATA
    # ==========================================================

    @staticmethod
    def _load_stock_data(
        db: Session,
        stock: Stock,
    ) -> pd.DataFrame:

        rows = db.scalars(
            select(MarketData)
            .where(
                MarketData.stock_id == stock.id
            )
            .order_by(
                MarketData.timestamp
            )
        ).all()

        if not rows:
            return pd.DataFrame()

        data = []

        for row in rows:

            data.append(
                {
                    "symbol": stock.symbol,
                    "stock_id": stock.id,
                    "timestamp": row.timestamp,
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "adjusted_close": row.adjusted_close,
                    "volume": row.volume,
                }
            )

        return pd.DataFrame(data)

    # ==========================================================
    # BUILD MARKET FEATURES
    # ==========================================================

    @staticmethod
    def _build_market_features(
        dataset: pd.DataFrame,
    ) -> pd.DataFrame:

        start_date = dataset["timestamp"].min()
        end_date = dataset["timestamp"].max()

        # Add one day because yfinance's `end` is exclusive.
        end_date = (
            pd.Timestamp(end_date)
            + pd.Timedelta(days=1)
        )

        print()
        print(
            f"Market feature range: "
            f"{start_date.date()} -> "
            f"{end_date.date()}"
        )

        market_features = (
            MarketFeatureBuilder.fetch_market_data(
                start_date=start_date,
                end_date=end_date,
            )
        )

        if market_features.empty:

            print(
                "WARNING: Market feature data is empty."
            )

            return market_features

        market_features[
            "timestamp"
        ] = pd.to_datetime(
            market_features["timestamp"]
        )

        return market_features

    # ==========================================================
    # BUILD SECTOR FEATURES
    # ==========================================================

    @staticmethod
    def _build_sector_features(
        db: Session,
        dataset: pd.DataFrame,
    ) -> pd.DataFrame:

        sectors = sorted(
            dataset["sector"]
            .dropna()
            .unique()
            .tolist()
        )

        if not sectors:

            print(
                "WARNING: No sector metadata available."
            )

            return pd.DataFrame()

        start_date = dataset["timestamp"].min()
        end_date = dataset["timestamp"].max()

        end_date = (
            pd.Timestamp(end_date)
            + pd.Timedelta(days=1)
        )

        print()
        print(
            f"Sector feature range: "
            f"{start_date.date()} -> "
            f"{end_date.date()}"
        )

        print(
            f"Sectors requested: "
            f"{sectors}"
        )

        sector_data = (
            SectorFeatureBuilder.fetch_sector_data(
                sectors=sectors,
                start_date=start_date,
                end_date=end_date,
            )
        )

        if not sector_data:

            print(
                "WARNING: "
                "No sector feature data returned."
            )

            return pd.DataFrame()

        frames = []

        for sector, data in sector_data.items():

            if data.empty:
                continue

            sector_frame = data.copy()

            sector_frame["sector"] = sector

            frames.append(
                sector_frame
            )

        if not frames:

            return pd.DataFrame()

        result = pd.concat(
            frames,
            ignore_index=True,
        )

        result["timestamp"] = pd.to_datetime(
            result["timestamp"]
        )

        return result

    # ==========================================================
    # BUILD COMPLETE DATASET
    # ==========================================================

    @staticmethod
    def build(
        db: Session,
    ) -> pd.DataFrame:

        stocks = db.scalars(
            select(Stock)
            .where(
                Stock.is_active == True
            )
            .order_by(
                Stock.symbol
            )
        ).all()

        if not stocks:

            raise ValueError(
                "No active stocks found."
            )

        stock_frames = []
        skipped_stocks = []

        print()
        print("=" * 70)
        print("BUILDING CROSS-STOCK ML DATASET")
        print("=" * 70)

        # ======================================================
        # STOCK FEATURES
        # ======================================================

        for index, stock in enumerate(
            stocks,
            start=1,
        ):

            print()
            print(
                f"[{index}/{len(stocks)}] "
                f"{stock.symbol}"
            )

            raw_data = (
                DatasetBuilder._load_stock_data(
                    db,
                    stock,
                )
            )

            # --------------------------------------------------
            # Skip stocks with no market data
            # --------------------------------------------------

            if raw_data.empty:

                print(
                    "  SKIPPED - "
                    "no market data"
                )

                skipped_stocks.append(
                    stock.symbol
                )

                continue

            print(
                f"  Raw rows: "
                f"{len(raw_data)}"
            )

            # --------------------------------------------------
            # Historical features
            # --------------------------------------------------

            feature_data = (
                HistoricalFeatureBuilder.build(
                    raw_data
                )
            )

            if feature_data.empty:

                print(
                    "  SKIPPED - "
                    "no usable feature rows"
                )

                skipped_stocks.append(
                    stock.symbol
                )

                continue

            # --------------------------------------------------
            # Metadata
            # --------------------------------------------------

            feature_data["sector"] = (
                stock.sector
            )

            feature_data["industry"] = (
                stock.industry
            )

            stock_frames.append(
                feature_data
            )

            print(
                f"  Feature rows: "
                f"{len(feature_data)}"
            )

        if not stock_frames:

            raise ValueError(
                "No usable stock datasets "
                "were generated."
            )

        # ======================================================
        # COMBINE STOCK DATA
        # ======================================================

        dataset = pd.concat(
            stock_frames,
            ignore_index=True,
        )

        dataset["timestamp"] = pd.to_datetime(
            dataset["timestamp"]
        )

        dataset = dataset.sort_values(
            [
                "timestamp",
                "stock_id",
            ]
        ).reset_index(
            drop=True
        )

        print()
        print(
            f"Combined stock rows: "
            f"{len(dataset)}"
        )

        # ======================================================
        # MARKET FEATURES
        # ======================================================

        print()
        print("=" * 70)
        print("ADDING MARKET FEATURES")
        print("=" * 70)

        market_features = (
            DatasetBuilder._build_market_features(
                dataset
            )
        )

        if not market_features.empty:

            dataset = dataset.merge(
                market_features,
                on="timestamp",
                how="left",
            )

            print(
                f"Market feature rows: "
                f"{len(market_features)}"
            )

        # ======================================================
        # SECTOR FEATURES
        # ======================================================

        print()
        print("=" * 70)
        print("ADDING SECTOR FEATURES")
        print("=" * 70)

        sector_features = (
            DatasetBuilder._build_sector_features(
                db=db,
                dataset=dataset,
            )
        )

        if not sector_features.empty:

            dataset = dataset.merge(
                sector_features,
                on=[
                    "timestamp",
                    "sector",
                ],
                how="left",
            )

            print(
                f"Sector feature rows: "
                f"{len(sector_features)}"
            )

        # ======================================================
        # CLEAN NUMERICAL VALUES
        # ======================================================

        dataset = dataset.replace(
            [np.inf, -np.inf],
            np.nan,
        )

        # ======================================================
        # TARGETS
        # ======================================================

        target_columns = [
            "target_return_5d",
            "target_return_10d",
            "target_return_20d",
        ]

        missing_targets = [
            column
            for column in target_columns
            if column not in dataset.columns
        ]

        if missing_targets:

            raise ValueError(
                "Missing target columns: "
                f"{missing_targets}"
            )

        before_drop = len(dataset)

        dataset = dataset.dropna(
            subset=target_columns
        )

        print()
        print(
            "Rows removed due to "
            f"missing targets: "
            f"{before_drop - len(dataset)}"
        )

        # ======================================================
        # FINAL SORT
        # ======================================================

        dataset = dataset.sort_values(
            [
                "timestamp",
                "stock_id",
            ]
        ).reset_index(
            drop=True
        )

        # ======================================================
        # FINAL REPORT
        # ======================================================

        print()
        print("=" * 70)
        print("DATASET BUILD COMPLETE")
        print("=" * 70)

        print(
            f"Stocks in universe: "
            f"{len(stocks)}"
        )

        print(
            f"Stocks skipped: "
            f"{len(skipped_stocks)}"
        )

        if skipped_stocks:

            print(
                f"Skipped stocks: "
                f"{skipped_stocks}"
            )

        print(
            f"Stocks in dataset: "
            f"{dataset['symbol'].nunique()}"
        )

        print(
            f"Rows: "
            f"{len(dataset)}"
        )

        print(
            f"Columns: "
            f"{len(dataset.columns)}"
        )

        # ------------------------------------------------------
        # Stock coverage
        # ------------------------------------------------------

        print()
        print("STOCK COVERAGE")
        print("-" * 70)

        coverage = (
            dataset
            .groupby("symbol")
            .size()
            .sort_values(
                ascending=False
            )
        )

        print(coverage)

        # ------------------------------------------------------
        # Sector coverage
        # ------------------------------------------------------

        print()
        print("SECTOR COVERAGE")
        print("-" * 70)

        print(
            dataset["sector"]
            .value_counts(
                dropna=False
            )
        )

        # ------------------------------------------------------
        # Missing-value summary
        # ------------------------------------------------------

        print()
        print("FEATURE MISSING VALUES")
        print("-" * 70)

        feature_missing = (
            dataset.isna()
            .sum()
            .sort_values(
                ascending=False
            )
        )

        print(
            feature_missing[
                feature_missing > 0
            ].head(20)
        )

        return dataset