from sqlalchemy import select

from app.data.database import SessionLocal
from app.models.stock import Stock

from app.data.market.sector_universe import (
    STOCK_SECTOR_MAP,
)


def main():

    db = SessionLocal()

    try:

        stocks = db.scalars(
            select(Stock)
            .where(
                Stock.is_active == True
            )
        ).all()

        print()
        print("=" * 60)
        print("SECTOR ENRICHMENT")
        print("=" * 60)

        updated = 0

        for stock in stocks:

            metadata = (
                STOCK_SECTOR_MAP
                .get(stock.symbol)
            )

            if not metadata:

                print(
                    f"{stock.symbol}: "
                    f"No local classification"
                )

                continue

            stock.sector = (
                metadata["sector"]
            )

            stock.industry = (
                metadata["industry"]
            )

            updated += 1

            print(
                f"{stock.symbol} | "
                f"{stock.sector} | "
                f"{stock.industry}"
            )

        db.commit()

        print()
        print(
            f"Updated stocks: {updated}"
        )

    finally:

        db.close()


if __name__ == "__main__":
    main()