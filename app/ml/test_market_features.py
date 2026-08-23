from datetime import datetime, timedelta

from app.ml.market_features import (
    MarketFeatureBuilder,
)


def main():

    end_date = datetime.now()

    start_date = (
        end_date
        - timedelta(days=365)
    )

    print()
    print("=" * 60)
    print("MARKET FEATURE TEST")
    print("=" * 60)

    data = (
        MarketFeatureBuilder
        .fetch_market_data(
            start_date=start_date,
            end_date=end_date,
        )
    )

    print(
        f"Rows: {len(data)}"
    )

    print(
        f"Columns: {list(data.columns)}"
    )

    print()
    print(
        data.tail(10).to_string(
            index=False
        )
    )

    print()
    print("=" * 60)
    print("MARKET FEATURE TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()