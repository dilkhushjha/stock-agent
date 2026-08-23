from datetime import datetime, timedelta

from app.ml.sector_features import (
    SectorFeatureBuilder,
)


def main():

    end_date = datetime.now()

    start_date = (
        end_date
        - timedelta(days=365)
    )

    sectors = [
        "Financial Services",
        "Energy",
    ]

    print()
    print("=" * 60)
    print("SECTOR FEATURE TEST")
    print("=" * 60)

    data = (
        SectorFeatureBuilder
        .fetch_sector_data(
            sectors=sectors,
            start_date=start_date,
            end_date=end_date,
        )
    )

    for sector, dataframe in data.items():

        print()
        print(
            f"SECTOR: {sector}"
        )

        print(
            f"Rows: {len(dataframe)}"
        )

        print(
            dataframe.tail(5)
            .to_string(index=False)
        )

    print()
    print("=" * 60)
    print("SECTOR FEATURE TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":

    main()