from sqlalchemy.orm import Session

from app.data.market.market_ingestion import (
    MarketDataIngestionService,
)

from app.data.market.nifty50_universe import (
    get_nifty50_symbols,
)


class BulkMarketDataIngestionService:

    @staticmethod
    def ingest_nifty50(
        db: Session,
        period: str = "5y",
        interval: str = "1d",
    ) -> dict:

        universe = get_nifty50_symbols()

        results = {
            "total": len(universe),
            "success": 0,
            "failed": 0,
            "records_inserted": 0,
            "records_skipped": 0,
            "records_invalid": 0,
            "failures": [],
        }

        print()
        print("=" * 70)
        print("NIFTY 50 BULK INGESTION")
        print("=" * 70)

        for index, symbol in enumerate(
            universe.keys(),
            start=1,
        ):

            print()
            print(
                f"[{index}/{len(universe)}] "
                f"{symbol}"
            )

            try:

                # Always start each stock
                # with a clean transaction.
                db.rollback()

                result = (
                    MarketDataIngestionService
                    .ingest_history(
                        db=db,
                        symbol=symbol,
                        period=period,
                        interval=interval,
                    )
                )

                results["success"] += 1

                results[
                    "records_inserted"
                ] += result[
                    "records_inserted"
                ]

                results[
                    "records_skipped"
                ] += result[
                    "records_skipped"
                ]

                results[
                    "records_invalid"
                ] += result[
                    "records_invalid"
                ]

                print(
                    f"  Inserted: "
                    f"{result['records_inserted']}"
                )

                print(
                    f"  Skipped: "
                    f"{result['records_skipped']}"
                )

                print(
                    f"  Invalid: "
                    f"{result['records_invalid']}"
                )

            except Exception as exc:

                db.rollback()

                results["failed"] += 1

                results[
                    "failures"
                ].append(
                    {
                        "symbol": symbol,
                        "error": str(exc),
                    }
                )

                print(
                    f"  FAILED: {exc}"
                )

        print()
        print("=" * 70)
        print("INGESTION SUMMARY")
        print("=" * 70)

        print(
            f"Total stocks: "
            f"{results['total']}"
        )

        print(
            f"Successful: "
            f"{results['success']}"
        )

        print(
            f"Failed: "
            f"{results['failed']}"
        )

        print(
            f"Records inserted: "
            f"{results['records_inserted']}"
        )

        print(
            f"Records skipped: "
            f"{results['records_skipped']}"
        )

        print(
            f"Invalid rows skipped: "
            f"{results['records_invalid']}"
        )

        if results["failures"]:

            print()
            print("FAILURES:")

            for failure in (
                results["failures"]
            ):

                print(
                    f"  "
                    f"{failure['symbol']}: "
                    f"{failure['error']}"
                )

        return results