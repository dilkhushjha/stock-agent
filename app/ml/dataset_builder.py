import numpy as np
import pandas as pd

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.stock import Stock
from app.models.market_data import MarketData
from app.ml.historical_features import HistoricalFeatureBuilder
from app.ml.market_features import MarketFeatureBuilder
from app.ml.sector_features import SectorFeatureBuilder


class DatasetBuilder:
    """Build the cross-stock, sector-aware ML dataset."""

    @staticmethod
    def _load_stock_data(db: Session, stock: Stock) -> pd.DataFrame:
        rows = db.scalars(
            select(MarketData)
            .where(MarketData.stock_id == stock.id)
            .order_by(MarketData.timestamp)
        ).all()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([
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
            for row in rows
        ])

    @staticmethod
    def _build_market_features(dataset: pd.DataFrame) -> pd.DataFrame:
        start_date = dataset["timestamp"].min()
        end_date = pd.Timestamp(dataset["timestamp"].max()) + pd.Timedelta(days=1)
        market_features = MarketFeatureBuilder.fetch_market_data(start_date, end_date)
        if market_features.empty:
            return market_features
        market_features["timestamp"] = pd.to_datetime(market_features["timestamp"]).dt.normalize()
        return market_features

    @staticmethod
    def _build_sector_features(db: Session, dataset: pd.DataFrame) -> pd.DataFrame:
        sectors = sorted(dataset["sector"].dropna().unique().tolist())
        if not sectors:
            return pd.DataFrame()
        start_date = dataset["timestamp"].min()
        end_date = pd.Timestamp(dataset["timestamp"].max()) + pd.Timedelta(days=1)
        sector_data = SectorFeatureBuilder.fetch_sector_data(sectors, start_date, end_date)
        frames = []
        for sector, data in sector_data.items():
            if data.empty:
                continue
            frame = data.copy()
            frame["sector"] = sector
            frames.append(frame)
        if not frames:
            return pd.DataFrame()
        result = pd.concat(frames, ignore_index=True)
        result["timestamp"] = pd.to_datetime(result["timestamp"]).dt.normalize()
        return result

    @staticmethod
    def _add_cross_sectional_features(dataset: pd.DataFrame) -> pd.DataFrame:
        """Add relative features so one model can rank the broad universe."""
        df = dataset.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.normalize()

        def rank_pct(column: str, name: str) -> None:
            if column in df.columns:
                df[name] = df.groupby("timestamp")[column].rank(pct=True, method="average")

        for column in (
            "return_1d", "return_5d", "return_20d",
            "momentum_5d", "momentum_20d", "volume_ratio",
            "sma20_distance", "sma50_distance", "volatility_20d",
        ):
            rank_pct(column, f"universe_rank_{column}")

        if "sector" in df.columns:
            for column in ("return_1d", "return_5d", "return_20d", "momentum_20d"):
                if column not in df.columns:
                    continue
                grouped = df.groupby(["timestamp", "sector"])[column]
                mean = grouped.transform("mean")
                std = grouped.transform("std")
                df[f"sector_relative_{column}"] = df[column] - mean
                df[f"sector_zscore_{column}"] = (df[column] - mean) / std.replace(0, np.nan)

            rank_pct("sector_return_5d", "universe_rank_sector_return_5d")
            rank_pct("sector_return_20d", "universe_rank_sector_return_20d")

        if "nifty_return_5d" in df.columns and "return_5d" in df.columns:
            df["market_relative_return_5d"] = df["return_5d"] - df["nifty_return_5d"]
        if "nifty_return_20d" in df.columns and "return_20d" in df.columns:
            df["market_relative_return_20d"] = df["return_20d"] - df["nifty_return_20d"]

        return df.replace([np.inf, -np.inf], np.nan)

    @staticmethod
    def build(db: Session) -> pd.DataFrame:
        stocks = db.scalars(
            select(Stock)
            .where(Stock.is_active == True)
            .order_by(Stock.symbol)
        ).all()
        if not stocks:
            raise ValueError("No active stocks found.")

        stock_frames = []
        skipped_stocks = []

        print("=" * 70)
        print("BUILDING CROSS-STOCK ML DATASET")
        print("=" * 70)

        for index, stock in enumerate(stocks, start=1):
            print(f"[{index}/{len(stocks)}] {stock.symbol}")
            raw_data = DatasetBuilder._load_stock_data(db, stock)
            if raw_data.empty:
                skipped_stocks.append(stock.symbol)
                continue

            feature_data = HistoricalFeatureBuilder.build(raw_data)
            if feature_data.empty:
                skipped_stocks.append(stock.symbol)
                continue

            feature_data["sector"] = stock.sector
            feature_data["industry"] = stock.industry
            feature_data["basic_industry"] = getattr(stock, "basic_industry", None)
            stock_frames.append(feature_data)

        if not stock_frames:
            raise ValueError("No usable stock datasets were generated.")

        dataset = pd.concat(stock_frames, ignore_index=True)
        dataset["timestamp"] = pd.to_datetime(dataset["timestamp"]).dt.normalize()
        dataset = dataset.sort_values(["timestamp", "stock_id"]).reset_index(drop=True)

        market_features = DatasetBuilder._build_market_features(dataset)
        if not market_features.empty:
            dataset = dataset.merge(market_features, on="timestamp", how="left")

        sector_features = DatasetBuilder._build_sector_features(db, dataset)
        if not sector_features.empty:
            dataset = dataset.merge(
                sector_features,
                on=["timestamp", "sector"],
                how="left",
            )

        dataset = DatasetBuilder._add_cross_sectional_features(dataset)
        dataset = dataset.replace([np.inf, -np.inf], np.nan)

        targets = HistoricalFeatureBuilder.TARGET_COLUMNS
        missing_targets = [c for c in targets if c not in dataset.columns]
        if missing_targets:
            raise ValueError(f"Missing target columns: {missing_targets}")

        dataset = dataset.dropna(subset=targets).reset_index(drop=True)

        print("=" * 70)
        print("DATASET BUILD COMPLETE")
        print(f"Active stocks: {len(stocks)}")
        print(f"Stocks with usable data: {dataset['symbol'].nunique()}")
        print(f"Rows: {len(dataset)}")
        print(f"Features/columns: {len(dataset.columns)}")
        print(f"Skipped stocks: {len(skipped_stocks)}")
        print("Sector coverage:")
        print(dataset["sector"].value_counts(dropna=False).head(30))

        return dataset
