import os
import joblib
import pandas as pd

from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

from app.data.database import SessionLocal
from app.ml.dataset_builder import DatasetBuilder


MODEL_DIR = "models"

MODEL_PATH = os.path.join(
    MODEL_DIR,
    "stock_return_model.pkl",
)

TARGETS = [
    "target_return_5d",
    "target_return_10d",
    "target_return_20d",
]


def get_feature_columns(dataset: pd.DataFrame) -> list[str]:
    """
    Automatically determine numeric ML features.

    Excludes:
    - target columns
    - identifiers
    - timestamps
    - categorical metadata
    """

    excluded = {
        "timestamp",
        "symbol",
        "sector",
        "industry",
        "stock_id",
        "target_return_5d",
        "target_return_10d",
        "target_return_20d",
    }

    features = []

    for column in dataset.columns:

        if column in excluded:
            continue

        if pd.api.types.is_numeric_dtype(
            dataset[column]
        ):
            features.append(column)

    if not features:
        raise ValueError(
            "No numeric feature columns found."
        )

    return features


def train_single_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    horizon: str,
):
    print()
    print(
        f"Training {horizon} model..."
    )

    model = HistGradientBoostingRegressor(
        max_iter=300,
        learning_rate=0.05,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        random_state=42,
    )

    model.fit(
        X_train,
        y_train,
    )

    return model


def evaluate_model(
    model,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    horizon: str,
):
    predictions = model.predict(
        X_test
    )

    mae = mean_absolute_error(
        y_test,
        predictions,
    )

    rmse = (
        mean_squared_error(
            y_test,
            predictions,
        )
        ** 0.5
    )

    r2 = r2_score(
        y_test,
        predictions,
    )

    actual_direction = (
        y_test > 0
    )

    predicted_direction = (
        predictions > 0
    )

    directional_accuracy = (
        actual_direction
        == predicted_direction
    ).mean()

    print()
    print(
        f"{horizon} MODEL PERFORMANCE"
    )
    print("-" * 60)

    print(
        f"MAE:                 {mae:.4f}%"
    )

    print(
        f"RMSE:                {rmse:.4f}%"
    )

    print(
        f"R²:                   {r2:.4f}"
    )

    print(
        f"Directional Accuracy: "
        f"{directional_accuracy:.2%}"
    )

    return {
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "directional_accuracy": (
            directional_accuracy
        ),
    }


def train():

    db = SessionLocal()

    try:

        print()
        print("=" * 70)
        print("STOCK AGENT - MODEL TRAINING")
        print("=" * 70)

        # ==================================================
        # BUILD DATASET
        # ==================================================

        dataset = DatasetBuilder.build(
            db
        )

        if dataset.empty:

            raise ValueError(
                "Training dataset is empty."
            )

        print()
        print(
            f"Dataset rows: "
            f"{len(dataset)}"
        )

        print(
            f"Stocks: "
            f"{dataset['symbol'].nunique()}"
        )

        # ==================================================
        # VERIFY TARGETS
        # ==================================================

        missing_targets = [
            target
            for target in TARGETS
            if target not in dataset.columns
        ]

        if missing_targets:

            raise ValueError(
                "Missing target columns: "
                f"{missing_targets}"
            )

        # ==================================================
        # SORT CHRONOLOGICALLY
        # ==================================================

        dataset = (
            dataset
            .sort_values(
                "timestamp"
            )
            .reset_index(
                drop=True
            )
        )

        # ==================================================
        # FEATURES
        # ==================================================

        features = get_feature_columns(
            dataset
        )

        print()
        print(
            f"Feature count: "
            f"{len(features)}"
        )

        print(
            "Features:"
        )

        for feature in features:
            print(
                f"  - {feature}"
            )

        X = dataset[
            features
        ].copy()

        # Make sure all feature values
        # are numeric.

        X = X.apply(
            pd.to_numeric,
            errors="coerce",
        )

        # ==================================================
        # TIME BASED SPLIT
        # ==================================================

        split_index = int(
            len(dataset) * 0.80
        )

        if split_index <= 0:
            raise ValueError(
                "Training split is empty."
            )

        if split_index >= len(dataset):
            raise ValueError(
                "Testing split is empty."
            )

        X_train = X.iloc[
            :split_index
        ]

        X_test = X.iloc[
            split_index:
        ]

        print()
        print(
            f"Training rows: "
            f"{len(X_train)}"
        )

        print(
            f"Testing rows: "
            f"{len(X_test)}"
        )

        print(
            f"Training period: "
            f"{dataset['timestamp'].iloc[0]}"
            f" -> "
            f"{dataset['timestamp'].iloc[split_index - 1]}"
        )

        print(
            f"Testing period: "
            f"{dataset['timestamp'].iloc[split_index]}"
            f" -> "
            f"{dataset['timestamp'].iloc[-1]}"
        )

        # ==================================================
        # TRAIN THREE MODELS
        # ==================================================

        models = {}
        metrics = {}

        for target in TARGETS:

            y = dataset[
                target
            ].copy()

            y = pd.to_numeric(
                y,
                errors="coerce",
            )

            # DatasetBuilder normally removes
            # missing targets, but keep this
            # safeguard here.

            valid_train = (
                y.iloc[:split_index]
                .notna()
            )

            X_train_target = (
                X_train.loc[
                    valid_train
                ]
            )

            y_train_target = (
                y.iloc[
                    :split_index
                ].loc[
                    valid_train
                ]
            )

            valid_test = (
                y.iloc[split_index:]
                .notna()
            )

            X_test_target = (
                X_test.loc[
                    valid_test
                ]
            )

            y_test_target = (
                y.iloc[
                    split_index:
                ].loc[
                    valid_test
                ]
            )

            if y_train_target.empty:
                raise ValueError(
                    f"No training data for "
                    f"{target}."
                )

            if y_test_target.empty:
                raise ValueError(
                    f"No testing data for "
                    f"{target}."
                )

            horizon = (
                target
                .replace(
                    "target_return_",
                    ""
                )
            )

            model = train_single_model(
                X_train_target,
                y_train_target,
                horizon,
            )

            model_metrics = evaluate_model(
                model,
                X_test_target,
                y_test_target,
                horizon,
            )

            models[target] = model
            metrics[target] = model_metrics

        # ==================================================
        # SAVE ARTIFACT
        # ==================================================

        os.makedirs(
            MODEL_DIR,
            exist_ok=True,
        )

        artifact = {
            "models": models,
            "features": features,
            "targets": TARGETS,
            "metrics": metrics,
            "model_name": "stock_return_model",
            "model_version": "v2",
        }

        joblib.dump(
            artifact,
            MODEL_PATH,
        )

        print()
        print("=" * 70)
        print("MODEL ARTIFACT SAVED")
        print("=" * 70)

        print(
            f"Path: {MODEL_PATH}"
        )

        print(
            "Models:"
        )

        for target in TARGETS:
            print(
                f"  {target}"
            )

        print()
        print("=" * 70)
        print("TRAINING COMPLETE")
        print("=" * 70)

    finally:

        db.close()


if __name__ == "__main__":
    train()
