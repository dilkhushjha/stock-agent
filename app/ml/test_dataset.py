from app.data.database import SessionLocal
from app.ml.dataset_builder import HistoricalDatasetBuilder


def main():

    db = SessionLocal()

    try:

        print()
        print("=" * 70)
        print("ENHANCED DATASET TEST")
        print("=" * 70)

        df = HistoricalDatasetBuilder.build(db)

        if df.empty:

            print("STATUS: NO DATA")
            return

        print()
        print("DATASET SUMMARY")
        print("-" * 70)

        print(
            f"Rows: {len(df)}"
        )

        print(
            f"Stocks: {df['symbol'].nunique()}"
        )

        print(
            f"Date range: "
            f"{df['timestamp'].min()} "
            f"→ "
            f"{df['timestamp'].max()}"
        )

        print()
        print("COLUMNS")
        print("-" * 70)

        print(
            list(df.columns)
        )

        print()
        print("RELATIVE STRENGTH FEATURES")
        print("-" * 70)

        columns = [
            "symbol",
            "sector",
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

            "stock_vs_sector_1d",
            "stock_vs_sector_5d",
            "stock_vs_sector_20d",

            "stock_vs_market_1d",
            "stock_vs_market_5d",
            "stock_vs_market_20d",

            "target_return_5d",
        ]

        available = [
            column
            for column in columns
            if column in df.columns
        ]

        print(
            df[
                available
            ]
            .tail(20)
            .to_string(
                index=False
            )
        )

        print()
        print("MISSING VALUES")
        print("-" * 70)

        check_columns = [
            column
            for column in available
            if column not in [
                "symbol",
                "sector",
            ]
        ]

        print(
            df[
                check_columns
            ]
            .isna()
            .sum()
            .to_string()
        )

        print()
        print("=" * 70)
        print("ENHANCED DATASET TEST COMPLETE")
        print("=" * 70)

    finally:

        db.close()


if __name__ == "__main__":
    main()