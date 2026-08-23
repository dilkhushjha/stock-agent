import os
from datetime import datetime, timezone

import joblib
import pandas as pd

from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from app.data.database import SessionLocal
from app.ml.dataset_builder import DatasetBuilder


MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "stock_return_model.pkl")
TARGETS = ["target_return_5d", "target_return_10d", "target_return_20d"]
MIN_TRAINING_STOCKS = 100


def get_feature_columns(dataset: pd.DataFrame) -> list[str]:
    """Return scale-safe numeric features for a cross-stock model."""
    excluded = {
        "timestamp", "symbol", "sector", "industry", "basic_industry", "stock_id",
        "open", "high", "low", "close", "adjusted_close", "volume", "sma20", "sma50",
        *TARGETS,
    }
    features = [
        c for c in dataset.columns
        if c not in excluded and pd.api.types.is_numeric_dtype(dataset[c])
    ]
    if not features:
        raise ValueError("No numeric feature columns found.")
    return features


def train_single_model(X_train, y_train, horizon: str):
    print(f"Training {horizon} model on {len(X_train)} rows...")
    model = HistGradientBoostingRegressor(
        max_iter=300,
        learning_rate=0.05,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        random_state=42,
    )
    model.fit(X_train, y_train)
    return model


def evaluate_model(model, X_test, y_test, horizon: str):
    predictions = model.predict(X_test)
    mae = mean_absolute_error(y_test, predictions)
    rmse = mean_squared_error(y_test, predictions) ** 0.5
    r2 = r2_score(y_test, predictions)
    directional_accuracy = ((y_test > 0) == (predictions > 0)).mean()
    return {
        "mae": float(mae),
        "rmse": float(rmse),
        "r2": float(r2),
        "directional_accuracy": float(directional_accuracy),
        "test_rows": int(len(y_test)),
    }


def train():
    db = SessionLocal()
    try:
        print("=" * 70)
        print("STOCKAGENT - GENERALIZED CROSS-STOCK MODEL TRAINING")
        print("=" * 70)

        dataset = DatasetBuilder.build(db)
        if dataset.empty:
            raise ValueError("Training dataset is empty.")

        stock_count = dataset["symbol"].nunique()
        if stock_count < MIN_TRAINING_STOCKS:
            raise ValueError(
                f"Only {stock_count} stocks have usable training data. "
                f"At least {MIN_TRAINING_STOCKS} are required for the broad-universe model. "
                "Complete the market-data bootstrap first."
            )

        dataset = dataset.sort_values(["timestamp", "stock_id"]).reset_index(drop=True)
        features = get_feature_columns(dataset)
        X = dataset[features].apply(pd.to_numeric, errors="coerce")

        # Split by trading date, not arbitrary rows. This keeps all stocks from
        # a given date on the same side of validation and avoids cross-sectional
        # leakage caused by uneven stock histories.
        unique_dates = sorted(dataset["timestamp"].dropna().unique())
        if len(unique_dates) < 60:
            raise ValueError("At least 60 trading dates are required for training.")

        split_date = unique_dates[int(len(unique_dates) * 0.80)]
        train_mask = dataset["timestamp"] < split_date
        test_mask = dataset["timestamp"] >= split_date
        X_train = X.loc[train_mask]
        X_test = X.loc[test_mask]

        print(f"Stocks: {stock_count}")
        print(f"Rows: {len(dataset)}")
        print(f"Features: {len(features)}")
        print(f"Training: {dataset.loc[train_mask, 'timestamp'].min()} -> {dataset.loc[train_mask, 'timestamp'].max()}")
        print(f"Testing:  {dataset.loc[test_mask, 'timestamp'].min()} -> {dataset.loc[test_mask, 'timestamp'].max()}")

        models = {}
        metrics = {}

        for target in TARGETS:
            y = pd.to_numeric(dataset[target], errors="coerce")
            train_valid = train_mask & y.notna()
            test_valid = test_mask & y.notna()
            if train_valid.sum() == 0 or test_valid.sum() == 0:
                raise ValueError(f"Insufficient data for {target}.")

            horizon = target.replace("target_return_", "")
            model = train_single_model(
                X.loc[train_valid], y.loc[train_valid], horizon
            )
            metrics[target] = evaluate_model(
                model, X.loc[test_valid], y.loc[test_valid], horizon
            )
            models[target] = model
            print(f"{horizon}: {metrics[target]}")

        os.makedirs(MODEL_DIR, exist_ok=True)
        artifact = {
            "models": models,
            "features": features,
            "targets": TARGETS,
            "metrics": metrics,
            "model_name": "stock_return_model",
            "model_version": "v3_cross_sectional",
            "universe": "broad_active_nse_equities",
            "training_stocks": int(stock_count),
            "training_rows": int(len(dataset)),
            "training_started_at": datetime.now(timezone.utc).isoformat(),
            "split_date": str(split_date),
        }
        joblib.dump(artifact, MODEL_PATH)

        print("=" * 70)
        print(f"MODEL SAVED: {MODEL_PATH}")
        print(f"VERSION: {artifact['model_version']}")
        print(f"UNIVERSE: {artifact['universe']}")
        print(f"STOCKS: {stock_count}")
        print("=" * 70)
    finally:
        db.close()


if __name__ == "__main__":
    train()
