from sqlalchemy import select

from app.data.database import SessionLocal

from app.data.market.market_ingestion import (
    MarketDataIngestionService,
)

from app.models.stock import Stock


def main():

    db = SessionLocal()

    try:

        stocks = db.scalars(
            select(Stock)
            .where(
                Stock.is_active == True
            )
            .order_by(
                Stock.symbol
            )
        ).all()

        print()
        print("=" * 60)
        print("HISTORICAL MARKET DATA BACKFILL")
        print("=" * 60)

        print(
            f"Stocks found: {len(stocks)}"
        )

        print()

        for stock in stocks:

            print(
                f"[BACKFILL] "
                f"{stock.symbol}"
            )

            try:

                result = (
                    MarketDataIngestionService
                    .ingest_history(
                        db=db,
                        symbol=stock.symbol,
                        period="5y",
                        interval="1d",
                    )
                )

                print(
                    f"  Downloaded: "
                    f"{result['total_downloaded']}"
                )

                print(
                    f"  Inserted: "
                    f"{result['records_inserted']}"
                )

                print(
                    f"  Skipped: "
                    f"{result['records_skipped']}"
                )

            except Exception as exc:

                print(
                    f"  FAILED: {exc}"
                )

        print()
        print("=" * 60)
        print("BACKFILL COMPLETE")
        print("=" * 60)

    finally:

        db.close()


if __name__ == "__main__":

    main()