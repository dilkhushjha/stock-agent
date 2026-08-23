from app.ml.cross_sectional_features import (
    CrossSectionalFeatureBuilder,
)


def main():

    print("=" * 60)
    print("CROSS-SECTIONAL FEATURE TEST")
    print("=" * 60)

    data = {
        "symbol": [
            "HDFCBANK",
            "SBIN",
            "RELIANCE",
            "AXISBANK",
        ],
        "sector": [
            "Financial Services",
            "Financial Services",
            "Energy",
            "Financial Services",
        ],
        "timestamp": [
            "2026-08-21",
            "2026-08-21",
            "2026-08-21",
            "2026-08-21",
        ],
        "return_1d": [
            1.0,
            2.0,
            0.5,
            -1.0,
        ],
        "return_5d": [
            3.0,
            5.0,
            1.0,
            -2.0,
        ],
        "return_20d": [
            6.0,
            8.0,
            2.0,
            -4.0,
        ],
        "nifty_return_1d": [
            0.5,
            0.5,
            0.5,
            0.5,
        ],
        "nifty_return_5d": [
            1.0,
            1.0,
            1.0,
            1.0,
        ],
        "nifty_return_20d": [
            2.0,
            2.0,
            2.0,
            2.0,
        ],
        "sector_return_1d": [
            0.2,
            0.2,
            0.1,
            0.2,
        ],
        "sector_return_5d": [
            0.5,
            0.5,
            0.2,
            0.5,
        ],
        "sector_return_20d": [
            1.0,
            1.0,
            0.5,
            1.0,
        ],
    }

    import pandas as pd

    df = pd.DataFrame(data)

    result = CrossSectionalFeatureBuilder.build(df)

    print()
    print(result[
        [
            "symbol",
            "relative_market_return_5d",
            "relative_sector_return_5d",
            "market_rank_5d",
            "sector_rank_5d",
        ]
    ].to_string(index=False))

    print()
    print("=" * 60)
    print("CROSS-SECTIONAL FEATURE TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
