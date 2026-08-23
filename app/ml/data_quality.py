from sqlalchemy import func, select

from app.data.database import SessionLocal
from app.models.market_data import MarketData
from app.models.stock import Stock


def main():

    db = SessionLocal()

    try:

        print()
        print("=" * 75)
        print("MARKET DATA QUALITY AUDIT")
        print("=" * 75)

        # =========================================
        # STOCK COUNT
        # =========================================

        stocks = db.scalars(
            select(Stock)
            .where(
                Stock.is_active == True
            )
        ).all()

        print()
        print("ACTIVE STOCKS")
        print("-" * 75)
        print(
            f"Count: {len(stocks)}"
        )

        # =========================================
        # TOTAL MARKET DATA
        # =========================================

        total_rows = db.scalar(
            select(
                func.count(MarketData.id)
            )
        )

        print()
        print("TOTAL MARKET DATA")
        print("-" * 75)
        print(
            f"Rows: {total_rows}"
        )

        # =========================================
        # GLOBAL DATE RANGE
        # =========================================

        earliest = db.scalar(
            select(
                func.min(
                    MarketData.timestamp
                )
            )
        )

        latest = db.scalar(
            select(
                func.max(
                    MarketData.timestamp
                )
            )
        )

        print()
        print("GLOBAL DATE RANGE")
        print("-" * 75)
        print(
            f"Earliest: {earliest}"
        )
        print(
            f"Latest:   {latest}"
        )

        # =========================================
        # PER-STOCK AUDIT
        # =========================================

        print()
        print("PER-STOCK DATA")
        print("-" * 75)

        print(
            f"{'SYMBOL':<15}"
            f"{'ROWS':>8}"
            f"{'START':>15}"
            f"{'END':>15}"
        )

        print("-" * 75)

        for stock in stocks:

            count = db.scalar(
                select(
                    func.count(
                        MarketData.id
                    )
                ).where(
                    MarketData.stock_id
                    == stock.id
                )
            )

            start = db.scalar(
                select(
                    func.min(
                        MarketData.timestamp
                    )
                ).where(
                    MarketData.stock_id
                    == stock.id
                )
            )

            end = db.scalar(
                select(
                    func.max(
                        MarketData.timestamp
                    )
                ).where(
                    MarketData.stock_id
                    == stock.id
                )
            )

            print(
                f"{stock.symbol:<15}"
                f"{count:>8}"
                f"{str(start)[:10]:>15}"
                f"{str(end)[:10]:>15}"
            )

        # =========================================
        # NULL CHECK
        # =========================================

        print()
        print("NULL / INVALID PRICE CHECK")
        print("-" * 75)

        null_close = db.scalar(
            select(
                func.count(
                    MarketData.id
                )
            ).where(
                MarketData.close.is_(None)
            )
        )

        null_open = db.scalar(
            select(
                func.count(
                    MarketData.id
                )
            ).where(
                MarketData.open.is_(None)
            )
        )

        null_high = db.scalar(
            select(
                func.count(
                    MarketData.id
                )
            ).where(
                MarketData.high.is_(None)
            )
        )

        null_low = db.scalar(
            select(
                func.count(
                    MarketData.id
                )
            ).where(
                MarketData.low.is_(None)
            )
        )

        print(
            f"NULL close: {null_close}"
        )

        print(
            f"NULL open:  {null_open}"
        )

        print(
            f"NULL high:  {null_high}"
        )

        print(
            f"NULL low:   {null_low}"
        )

        # =========================================
        # VOLUME CHECK
        # =========================================

        null_volume = db.scalar(
            select(
                func.count(
                    MarketData.id
                )
            ).where(
                MarketData.volume.is_(None)
            )
        )

        print()
        print("VOLUME")
        print("-" * 75)

        print(
            f"NULL volume rows: "
            f"{null_volume}"
        )

        # =========================================
        # DUPLICATE TIMESTAMPS
        # =========================================

        duplicate_groups = db.execute(
            select(
                MarketData.stock_id,
                MarketData.timestamp,
                func.count(
                    MarketData.id
                ).label("count"),
            )
            .group_by(
                MarketData.stock_id,
                MarketData.timestamp,
            )
            .having(
                func.count(
                    MarketData.id
                ) > 1
            )
        ).all()

        print()
        print("DUPLICATES")
        print("-" * 75)

        print(
            f"Duplicate groups: "
            f"{len(duplicate_groups)}"
        )

        # =========================================
        # SECTOR COVERAGE
        # =========================================

        print()
        print("SECTOR COVERAGE")
        print("-" * 75)

        sector_counts = db.execute(
            select(
                Stock.sector,
                func.count(
                    Stock.id
                )
            )
            .where(
                Stock.is_active == True
            )
            .group_by(
                Stock.sector
            )
        ).all()

        for sector, count in (
            sector_counts
        ):

            print(
                f"{str(sector):<35}"
                f"{count}"
            )

        # =========================================
        # FINAL
        # =========================================

        print()
        print("=" * 75)
        print("DATA QUALITY AUDIT COMPLETE")
        print("=" * 75)

    finally:

        db.close()


if __name__ == "__main__":
    main()