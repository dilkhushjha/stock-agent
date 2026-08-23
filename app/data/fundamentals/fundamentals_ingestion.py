from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.fundamentals_collector import (
    FundamentalsCollector,
)

from app.models.stock import Stock


class FundamentalsIngestionService:

    @staticmethod
    def ingest_all(
        db: Session,
    ) -> dict:

        stocks = db.scalars(
            select(Stock)
            .where(
                Stock.is_active == True
            )
        ).all()

        results = {
            "total": len(stocks),
            "success": 0,
            "failed": 0,
            "sector_updated": 0,
            "industry_updated": 0,
            "failures": [],
        }

        print()
        print("=" * 70)
        print("FUNDAMENTALS / STOCK METADATA INGESTION")
        print("=" * 70)

        for index, stock in enumerate(
            stocks,
            start=1,
        ):

            print()
            print(
                f"[{index}/{len(stocks)}] "
                f"{stock.symbol}"
            )

            try:

                db.rollback()

                data = (
                    FundamentalsCollector.collect(
                        stock.yahoo_symbol
                    )
                )

                sector = data.get(
                    "sector"
                )

                industry = data.get(
                    "industry"
                )

                if sector:

                    stock.sector = sector

                    results[
                        "sector_updated"
                    ] += 1

                if industry:

                    stock.industry = industry

                    results[
                        "industry_updated"
                    ] += 1

                db.commit()

                results[
                    "success"
                ] += 1

                print(
                    f"  Sector: "
                    f"{sector}"
                )

                print(
                    f"  Industry: "
                    f"{industry}"
                )

            except Exception as exc:

                db.rollback()

                results[
                    "failed"
                ] += 1

                results[
                    "failures"
                ].append(
                    {
                        "symbol":
                            stock.symbol,
                        "error":
                            str(exc),
                    }
                )

                print(
                    f"  FAILED: {exc}"
                )

        print()
        print("=" * 70)
        print("FUNDAMENTALS SUMMARY")
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
            f"Sectors updated: "
            f"{results['sector_updated']}"
        )

        print(
            f"Industries updated: "
            f"{results['industry_updated']}"
        )

        return results