from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.stock import Stock
from app.models.market_data import MarketData
from app.models.prediction import SignalPrediction

from app.ml.historical_features import (
    HistoricalFeatureBuilder,
)
from app.ml.market_features import (
    MarketFeatureBuilder,
)
from app.ml.sector_features import (
    SectorFeatureBuilder,
)


class PredictionService:
    """
    Central prediction service.

    Responsibilities:
        1. Store existing intelligence/event signals.
        2. Generate ML predictions for individual stocks.
        3. Generate predictions across the stock universe.
        4. Convert predicted returns into trading signals.

    TATAMOTORS is automatically skipped when insufficient
    market data is available.
    """

    # ---------------------------------------------------------
    # Existing signal storage
    # ---------------------------------------------------------

    @staticmethod
    def store_signal(
        db: Session,
        symbol: str,
        factor: str,
        direction: str,
        impact: str,
        signal_score: float,
        article_id: int | None = None,
    ):
        stock = db.scalar(
            select(Stock).where(
                Stock.symbol == symbol.upper()
            )
        )

        if not stock:
            return None

        latest_price = db.scalar(
            select(MarketData.close)
            .where(
                MarketData.stock_id == stock.id
            )
            .order_by(
                MarketData.timestamp.desc()
            )
        )

        prediction = SignalPrediction(
            stock_id=stock.id,
            article_id=article_id,
            factor=factor.upper(),
            direction=direction.upper(),
            predicted_impact=impact,
            signal_score=signal_score,
            confidence=min(
                abs(signal_score) / 100,
                1.0,
            ),
            price_at_signal=latest_price,
            signal_time=datetime.utcnow(),
        )

        db.add(prediction)
        db.commit()
        db.refresh(prediction)

        return prediction

    # ---------------------------------------------------------
    # Model discovery
    # ---------------------------------------------------------

    @staticmethod
    def _find_model() -> Path | None:
        """
        Locate the trained model artifact without hardcoding
        a machine-specific absolute path.
        """

        project_root = Path(__file__).resolve().parents[2]

        candidates = [
            project_root / "models",
            project_root / "model",
            project_root / "artifacts",
            project_root / "app" / "ml" / "models",
            project_root / "app" / "ml" / "artifacts",
        ]

        extensions = (
            "*.joblib",
            "*.pkl",
            "*.pickle",
        )

        for directory in candidates:

            if not directory.exists():
                continue

            for extension in extensions:

                matches = list(
                    directory.glob(extension)
                )

                if matches:
                    return matches[0]

        return None

    # ---------------------------------------------------------
    # Load model
    # ---------------------------------------------------------

    @staticmethod
    def _load_model():
        model_path = (
            PredictionService._find_model()
        )

        if model_path is None:
            raise FileNotFoundError(
                "No trained ML model artifact was found."
            )

        return joblib.load(model_path)

    # ---------------------------------------------------------
    # Load stock history from database
    # ---------------------------------------------------------

    @staticmethod
    def _get_stock_history(
        db: Session,
        stock: Stock,
    ) -> pd.DataFrame:

        rows = db.scalars(
            select(MarketData)
            .where(
                MarketData.stock_id == stock.id
            )
            .order_by(
                MarketData.timestamp.asc()
            )
        ).all()

        if not rows:
            return pd.DataFrame()

        records = []

        for row in rows:

            records.append(
                {
                    "timestamp": row.timestamp,
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "adjusted_close": row.adjusted_close,
                    "volume": row.volume,
                }
            )

        return pd.DataFrame(records)

    # ---------------------------------------------------------
    # Determine sector
    # ---------------------------------------------------------

    @staticmethod
    def _get_sector(
        stock: Stock,
    ) -> str | None:

        return getattr(
            stock,
            "sector",
            None,
        )

    # ---------------------------------------------------------
    # Build historical features
    # ---------------------------------------------------------

    @staticmethod
    def _build_historical_features(
        history: pd.DataFrame,
    ) -> pd.DataFrame:

        if history.empty:
            return history

        return HistoricalFeatureBuilder.build(
            history
        )

    # ---------------------------------------------------------
    # Build market features
    # ---------------------------------------------------------

    @staticmethod
    def _build_market_features(
        start_date,
        end_date,
    ) -> pd.DataFrame:

        return MarketFeatureBuilder.fetch_market_data(
            start_date=start_date,
            end_date=end_date,
        )

    # ---------------------------------------------------------
    # Build sector features
    # ---------------------------------------------------------

    @staticmethod
    def _build_sector_features(
        sector: str | None,
        start_date,
        end_date,
    ) -> pd.DataFrame:

        if not sector:
            return pd.DataFrame()

        result = (
            SectorFeatureBuilder.fetch_sector_data(
                sectors=[sector],
                start_date=start_date,
                end_date=end_date,
            )
        )

        return result.get(
            sector,
            pd.DataFrame(),
        )

    # ---------------------------------------------------------
    # Prepare latest feature row
    # ---------------------------------------------------------

    @staticmethod
    def _prepare_features(
        db: Session,
        stock: Stock,
    ) -> pd.DataFrame:

        history = (
            PredictionService
            ._get_stock_history(
                db,
                stock,
            )
        )

        if history.empty:
            return pd.DataFrame()

        historical = (
            PredictionService
            ._build_historical_features(
                history
            )
        )

        if historical.empty:
            return pd.DataFrame()

        latest_timestamp = (
            historical["timestamp"].max()
        )

        start_date = (
            historical["timestamp"].min()
        )

        end_date = (
            latest_timestamp
            + pd.Timedelta(days=1)
        )

        # -----------------------------------------------------
        # Market features
        # -----------------------------------------------------

        try:

            market = (
                PredictionService
                ._build_market_features(
                    start_date,
                    end_date,
                )
            )

        except Exception as exc:

            print(
                f"[PREDICTION] "
                f"Market features failed: {exc}"
            )

            market = pd.DataFrame()

        # -----------------------------------------------------
        # Sector features
        # -----------------------------------------------------

        sector = (
            PredictionService
            ._get_sector(stock)
        )

        try:

            sector_data = (
                PredictionService
                ._build_sector_features(
                    sector,
                    start_date,
                    end_date,
                )
            )

        except Exception as exc:

            print(
                f"[PREDICTION] "
                f"Sector features failed: {exc}"
            )

            sector_data = pd.DataFrame()

        # -----------------------------------------------------
        # Merge
        # -----------------------------------------------------

        result = historical.copy()

        if not market.empty:

            result = result.merge(
                market,
                on="timestamp",
                how="left",
            )

        if not sector_data.empty:

            result = result.merge(
                sector_data,
                on="timestamp",
                how="left",
            )

        result = (
            result
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

        return result

    # ---------------------------------------------------------
    # Detect model feature schema
    # ---------------------------------------------------------

    @staticmethod
    def _get_model_features(
        model,
    ) -> list[str] | None:

        if hasattr(
            model,
            "feature_names_in_",
        ):

            return list(
                model.feature_names_in_
            )

        if hasattr(
            model,
            "named_steps",
        ):

            for step in model.named_steps.values():

                if hasattr(
                    step,
                    "feature_names_in_",
                ):

                    return list(
                        step.feature_names_in_
                    )

        return None

    # ---------------------------------------------------------
    # Generate prediction
    # ---------------------------------------------------------

    @staticmethod
    def predict_stock(
        db: Session,
        symbol: str,
    ) -> dict[str, Any]:

        symbol = symbol.upper()

        stock = db.scalar(
            select(Stock).where(
                Stock.symbol == symbol
            )
        )

        if not stock:

            return {
                "symbol": symbol,
                "status": "NOT_FOUND",
            }

        if not stock.is_active:

            return {
                "symbol": symbol,
                "status": "INACTIVE",
            }

        features = (
            PredictionService
            ._prepare_features(
                db,
                stock,
            )
        )

        if features.empty:

            return {
                "symbol": symbol,
                "status": "NO_DATA",
            }

        # -----------------------------------------------------
        # Latest usable row
        # -----------------------------------------------------

        latest = (
            features
            .sort_values("timestamp")
            .iloc[-1]
        )

        model = (
            PredictionService
            ._load_model()
        )

        model_features = (
            PredictionService
            ._get_model_features(
                model
            )
        )

        if model_features is None:

            return {
                "symbol": symbol,
                "status": "MODEL_FEATURE_SCHEMA_UNAVAILABLE",
            }

        missing = [
            column
            for column in model_features
            if column not in features.columns
        ]

        if missing:

            return {
                "symbol": symbol,
                "status": "MISSING_FEATURES",
                "missing_features": missing,
            }

        X = pd.DataFrame(
            [
                [
                    latest[column]
                    for column in model_features
                ]
            ],
            columns=model_features,
        )

        # -----------------------------------------------------
        # Final NaN protection
        # -----------------------------------------------------

        if X.isna().any().any():

            return {
                "symbol": symbol,
                "status": "INSUFFICIENT_FEATURE_DATA",
            }

        # -----------------------------------------------------
        # Prediction
        # -----------------------------------------------------

        prediction = model.predict(X)

        values = np.asarray(
            prediction
        ).reshape(-1)

        if len(values) == 0:

            return {
                "symbol": symbol,
                "status": "NO_PREDICTION",
            }

        predicted_return = float(
            values[0]
        )

        # -----------------------------------------------------
        # Signal
        # -----------------------------------------------------

        signal = (
            PredictionService
            ._return_to_signal(
                predicted_return
            )
        )

        confidence = (
            PredictionService
            ._calculate_confidence(
                predicted_return
            )
        )

        latest_price = float(
            latest["close"]
        )

        return {
            "symbol": symbol,
            "company_name": stock.company_name,
            "sector": stock.sector,
            "industry": stock.industry,
            "timestamp": latest["timestamp"],
            "price": latest_price,
            "predicted_return": predicted_return,
            "signal": signal,
            "confidence": confidence,
            "status": "OK",
        }

    # ---------------------------------------------------------
    # Convert return into trading signal
    # ---------------------------------------------------------

    @staticmethod
    def _return_to_signal(
        predicted_return: float,
    ) -> str:

        if predicted_return >= 2.0:
            return "BUY"

        if predicted_return <= -2.0:
            return "SELL"

        return "HOLD"

    # ---------------------------------------------------------
    # Confidence
    # ---------------------------------------------------------

    @staticmethod
    def _calculate_confidence(
        predicted_return: float,
    ) -> float:

        magnitude = abs(
            predicted_return
        )

        # Saturating confidence curve.
        confidence = (
            50.0
            + min(
                magnitude * 8.0,
                45.0,
            )
        )

        return round(
            confidence,
            2,
        )

    # ---------------------------------------------------------
    # Predict entire universe
    # ---------------------------------------------------------

    @staticmethod
    def predict_all_stocks(
        db: Session,
    ) -> list[dict[str, Any]]:

        stocks = db.scalars(
            select(Stock)
            .where(
                Stock.is_active == True
            )
            .order_by(
                Stock.symbol.asc()
            )
        ).all()

        results = []

        for stock in stocks:

            try:

                result = (
                    PredictionService
                    .predict_stock(
                        db,
                        stock.symbol,
                    )
                )

                results.append(result)

                print(
                    f"[PREDICTION] "
                    f"{stock.symbol}: "
                    f"{result.get('status')}"
                )

            except Exception as exc:

                print(
                    f"[PREDICTION] "
                    f"{stock.symbol} failed: "
                    f"{exc}"
                )

                results.append(
                    {
                        "symbol": stock.symbol,
                        "status": "ERROR",
                        "error": str(exc),
                    }
                )

        return results