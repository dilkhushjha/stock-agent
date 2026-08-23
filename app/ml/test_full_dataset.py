from app.data.database import SessionLocal

from app.ml.dataset_builder import (
    DatasetBuilder,
)


def main():

    db = SessionLocal()

    try:

        dataset = (
            DatasetBuilder.build(db)
        )

        print()
        print("=" * 70)
        print("FINAL DATASET SAMPLE")
        print("=" * 70)

        columns = [
            "symbol",
            "timestamp",
            "close",
            "return_1d",
            "return_5d",
            "return_20d",
            "volatility_20d",
            "sma20_distance",
            "sma50_distance",
            "volume_ratio",
            "momentum_5d",
            "momentum_20d",
            "nifty_return_1d",
            "nifty_return_5d",
            "nifty_return_20d",
            "sector_return_1d",
            "sector_return_5d",
            "sector_return_20d",
            "target_return_5d",
            "target_return_10d",
            "target_return_20d",
        ]

        available = [
            column
            for column in columns
            if column in dataset.columns
        ]

        print(
            dataset[
                available
            ].tail(20).to_string(
                index=False
            )
        )

    finally:

        db.close()


if __name__ == "__main__":
    main()
