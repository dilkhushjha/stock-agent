import os
import joblib
import numpy as np
import pandas as pd

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.stock import Stock
from app.models.market_data import MarketData
from app.models.ml_prediction import MLPrediction

from app.ml.historical_features import (
    HistoricalFeatureBuilder,
)

from app.ml.market_features import (
    MarketFeatureBuilder,
)

from app.ml.sector_features import (
    SectorFeatureBuilder,
)

from app.data.market.sector_universe import (
    SECTOR_INDEX_MAP,
)


MODEL_PATH = os.path.join(
    "models",
    "stock_return_model.pkl",
)


class MLPredictionEngine:

    MODEL_NAME = "stock_return_model"
    MODEL_VERSION = "v2"

    TARGET_5D = "target_return_5d"
    TARGET_10D = "target_return_10d"
    TARGET_20D = "target_return_20d"

    EXCLUDED_SYMBOLS = {
        "TATAMOTORS",
    }

    def __init__(
        self,
        db: Session,
    ):

        self.db = db

        self.models = {}
        self.features = []
        self.targets = []

        self.loaded = False

    # ==========================================================
    # LOAD MODEL
    # ==========================================================

    def load_model_artifact(
        self,
    ):

        if not os.path.exists(
            MODEL_PATH
        ):

            raise FileNotFoundError(
                f"Model not found: "
                f"{MODEL_PATH}"
            )

        artifact = joblib.load(
            MODEL_PATH
        )

        required = [
            "models",
            "features",
            "targets",
        ]

        missing = [
            key
            for key in required
            if key not in artifact
        ]

        if missing:

            raise ValueError(
                "Model artifact is missing: "
                f"{missing}"
            )

        self.models = artifact[
            "models"
        ]

        self.features = artifact[
            "features"
        ]

        self.targets = artifact[
            "targets"
        ]

        if not self.models:
            raise ValueError(
                "Model artifact contains "
                "no models."
            )

        self.loaded = True

        print(
            f"Loaded model artifact: "
            f"{MODEL_PATH}"
        )

        print(
            f"Features: "
            f"{len(self.features)}"
        )

        print(
            f"Targets: "
            f"{self.targets}"
        )

    # ==========================================================
    # LOAD STOCK DATA
    # ==========================================================

    def _load_stock_data(
        self,
        stock: Stock,
        limit: int = 100,
    ) -> pd.DataFrame:

        rows = self.db.scalars(
            select(MarketData)
            .where(
                MarketData.stock_id
                == stock.id
            )
            .order_by(
                MarketData.timestamp.desc()
            )
            .limit(limit)
        ).all()

        if not rows:
            return pd.DataFrame()

        rows = list(
            reversed(rows)
        )

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
                    "adjusted_close": (
                        row.adjusted_close
                    ),
                    "volume": row.volume,
                }
            )

        return pd.DataFrame(
            data
        )

    # ==========================================================
    # BUILD FEATURES
    # ==========================================================

    def _build_features(
        self,
        stock: Stock,
    ) -> pd.DataFrame:

        raw = self._load_stock_data(
            stock,
            limit=100,
        )

        if raw.empty:
            raise ValueError(
                "No market data."
            )

        features = (
            HistoricalFeatureBuilder.build(
                raw
            )
        )

        if features.empty:
            raise ValueError(
                "No historical features."
            )

        features["sector"] = (
            stock.sector
        )

        features["industry"] = (
            stock.industry
        )

        # ------------------------------------------------------
        # Market features
        # ------------------------------------------------------

        start_date = (
            features["timestamp"].min()
        )

        end_date = (
            features["timestamp"].max()
            + pd.Timedelta(days=1)
        )

        market = (
            MarketFeatureBuilder
            .fetch_market_data(
                start_date=start_date,
                end_date=end_date,
            )
        )

        if not market.empty:

            market["timestamp"] = (
                pd.to_datetime(
                    market["timestamp"]
                )
                .dt.normalize()
            )

            features["timestamp"] = (
                pd.to_datetime(
                    features["timestamp"]
                )
                .dt.normalize()
            )

            features = features.merge(
                market,
                on="timestamp",
                how="left",
            )

        # ------------------------------------------------------
        # Sector features
        # ------------------------------------------------------

        sector = stock.sector

        sector_symbol = (
            SECTOR_INDEX_MAP.get(
                sector
            )
        )

        if sector_symbol:

            sector_data = (
                SectorFeatureBuilder
                .fetch_sector_data(
                    sectors=[sector],
                    start_date=start_date,
                    end_date=end_date,
                )
            )

            sector_frame = (
                sector_data.get(
                    sector,
                    pd.DataFrame(),
                )
            )

            if not sector_frame.empty:

                sector_frame = (
                    sector_frame.copy()
                )

                sector_frame[
                    "timestamp"
                ] = (
                    pd.to_datetime(
                        sector_frame[
                            "timestamp"
                        ]
                    )
                    .dt.normalize()
                )

                features[
                    "timestamp"
                ] = (
                    pd.to_datetime(
                        features[
                            "timestamp"
                        ]
                    )
                    .dt.normalize()
                )

                features = features.merge(
                    sector_frame,
                    on="timestamp",
                    how="left",
                )

        # ------------------------------------------------------
        # Stock vs sector / market
        # ------------------------------------------------------

        if (
            "sector_return_1d"
            in features.columns
        ):

            features[
                "stock_vs_sector_1d"
            ] = (
                features[
                    "return_1d"
                ]
                - features[
                    "sector_return_1d"
                ]
            )

            features[
                "stock_vs_sector_5d"
            ] = (
                features[
                    "return_5d"
                ]
                - features[
                    "sector_return_5d"
                ]
            )

            features[
                "stock_vs_sector_20d"
            ] = (
                features[
                    "return_20d"
                ]
                - features[
                    "sector_return_20d"
                ]
            )

        else:

            features[
                "stock_vs_sector_1d"
            ] = np.nan

            features[
                "stock_vs_sector_5d"
            ] = np.nan

            features[
                "stock_vs_sector_20d"
            ] = np.nan

        if (
            "nifty_return_1d"
            in features.columns
        ):

            features[
                "stock_vs_market_1d"
            ] = (
                features[
                    "return_1d"
                ]
                - features[
                    "nifty_return_1d"
                ]
            )

            features[
                "stock_vs_market_5d"
            ] = (
                features[
                    "return_5d"
                ]
                - features[
                    "nifty_return_5d"
                ]
            )

            features[
                "stock_vs_market_20d"
            ] = (
                features[
                    "return_20d"
                ]
                - features[
                    "nifty_return_20d"
                ]
            )

        else:

            features[
                "stock_vs_market_1d"
            ] = np.nan

            features[
                "stock_vs_market_5d"
            ] = np.nan

            features[
                "stock_vs_market_20d"
            ] = np.nan

        # ------------------------------------------------------
        # Clean
        # ------------------------------------------------------

        features = features.replace(
            [np.inf, -np.inf],
            np.nan,
        )

        features = features.sort_values(
            "timestamp"
        )

        return features

    # ==========================================================
    # SIGNAL
    # ==========================================================

    @staticmethod
    def _get_signal(
        predicted_return_5d: float,
    ):

        if predicted_return_5d >= 2.0:
            return "BUY"

        if predicted_return_5d <= -2.0:
            return "SELL"

        return "HOLD"

    # ==========================================================
    # CONFIDENCE
    # ==========================================================

    @staticmethod
    def _get_confidence(
        returns: list[float],
    ) -> float:

        absolute_returns = [
            abs(value)
            for value in returns
            if pd.notna(value)
        ]

        if not absolute_returns:
            return 0.0

        strength = (
            sum(absolute_returns)
            / len(absolute_returns)
        )

        confidence = (
            0.65
            + min(
                strength / 10.0,
                0.30,
            )
        )

        return round(
            min(
                confidence,
                0.95,
            ),
            2,
        )

    # ==========================================================
    # STORE
    # ==========================================================

    def store_prediction(
        self,
        stock: Stock,
        timestamp,
        price: float,
        predicted_return_5d: float,
        predicted_return_10d: float,
        predicted_return_20d: float,
    ):

        existing = self.db.scalar(
            select(MLPrediction)
            .where(
                MLPrediction.stock_id
                == stock.id,
                MLPrediction.market_timestamp
                == timestamp,
            )
        )

        if existing:

            existing.price_at_prediction = (
                price
            )

            existing.predicted_return_5d = (
                predicted_return_5d
            )

            existing.predicted_return_10d = (
                predicted_return_10d
            )

            existing.predicted_return_20d = (
                predicted_return_20d
            )

            existing.model_name = (
                self.MODEL_NAME
            )

            existing.model_version = (
                self.MODEL_VERSION
            )

            self.db.commit()

            self.db.refresh(
                existing
            )

            return existing

        prediction = MLPrediction(
            stock_id=stock.id,
            market_timestamp=timestamp,
            prediction_time=datetime.utcnow(),
            price_at_prediction=price,
            predicted_return_5d=(
                predicted_return_5d
            ),
            predicted_return_10d=(
                predicted_return_10d
            ),
            predicted_return_20d=(
                predicted_return_20d
            ),
            model_name=self.MODEL_NAME,
            model_version=self.MODEL_VERSION,
        )

        self.db.add(
            prediction
        )

        self.db.commit()

        self.db.refresh(
            prediction
        )

        return prediction

    # ==========================================================
    # PREDICT ONE
    # ==========================================================

    def predict_stock(
        self,
        stock: Stock,
    ):

        features = (
            self._build_features(
                stock
            )
        )

        latest = (
            features
            .sort_values(
                "timestamp"
            )
            .iloc[-1]
        )

        X = pd.DataFrame(
            [
                {
                    feature: latest.get(
                        feature,
                        np.nan,
                    )
                    for feature
                    in self.features
                }
            ]
        )

        X = X.apply(
            pd.to_numeric,
            errors="coerce",
        )

        predictions = {}

        for target in self.targets:

            model = self.models.get(
                target
            )

            if model is None:
                raise ValueError(
                    f"No model found for "
                    f"{target}"
                )

            value = float(
                model.predict(X)[0]
            )

            predictions[target] = value

        price = float(
            latest["close"]
        )

        timestamp = pd.Timestamp(
            latest["timestamp"]
        ).to_pydatetime()

        prediction = (
            self.store_prediction(
                stock=stock,
                timestamp=timestamp,
                price=price,
                predicted_return_5d=(
                    predictions[
                        self.TARGET_5D
                    ]
                ),
                predicted_return_10d=(
                    predictions[
                        self.TARGET_10D
                    ]
                ),
                predicted_return_20d=(
                    predictions[
                        self.TARGET_20D
                    ]
                ),
            )
        )

        returns = [
            predictions[
                self.TARGET_5D
            ],
            predictions[
                self.TARGET_10D
            ],
            predictions[
                self.TARGET_20D
            ],
        ]

        signal = self._get_signal(
            predictions[
                self.TARGET_5D
            ]
        )

        confidence = (
            self._get_confidence(
                returns
            )
        )

        return {
            "symbol": stock.symbol,
            "predicted_return_5d": round(
                predictions[
                    self.TARGET_5D
                ],
                3,
            ),
            "predicted_return_10d": round(
                predictions[
                    self.TARGET_10D
                ],
                3,
            ),
            "predicted_return_20d": round(
                predictions[
                    self.TARGET_20D
                ],
                3,
            ),
            "signal": signal,
            "confidence": confidence,
            "prediction": prediction,
        }

    # ==========================================================
    # PREDICT ALL
    # ==========================================================

    def predict_all(self):

        if not self.loaded:
            self.load_model_artifact()

        stocks = self.db.scalars(
            select(Stock)
            .where(
                Stock.is_active == True
            )
            .order_by(
                Stock.symbol
            )
        ).all()

        print()
        print("=" * 70)
        print("STOCK AGENT - ML PREDICTIONS")
        print("=" * 70)

        print(
            f"Model: "
            f"{self.MODEL_NAME} "
            f"{self.MODEL_VERSION}"
        )

        print(
            f"Stocks: "
            f"{len(stocks)}"
        )

        success = 0
        failed = 0

        results = []

        for stock in stocks:

            if (
                stock.symbol
                in self.EXCLUDED_SYMBOLS
            ):
                continue

            try:

                result = (
                    self.predict_stock(
                        stock
                    )
                )

                results.append(
                    result
                )

                print(
                    f"{stock.symbol:<15}"
                    f"{result['predicted_return_5d']:>8.3f}% "
                    f"{result['predicted_return_10d']:>8.3f}% "
                    f"{result['predicted_return_20d']:>8.3f}% "
                    f"{result['signal']:<5} "
                    f"confidence="
                    f"{result['confidence']:.2f}"
                )

                success += 1

            except Exception as exc:

                print(
                    f"{stock.symbol:<15}"
                    f"FAILED: {exc}"
                )

                failed += 1

        print()
        print("=" * 70)

        print(
            f"SUCCESS: {success}"
        )

        print(
            f"FAILED:  {failed}"
        )

        print("=" * 70)

        return results