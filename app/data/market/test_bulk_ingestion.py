from app.data.database import SessionLocal

from app.data.market.bulk_ingestion import (
    BulkMarketDataIngestionService,
)


def main():

    db = SessionLocal()

    try:

        result = (
            BulkMarketDataIngestionService
            .ingest_nifty50(
                db=db,
                period="5y",
                interval="1d",
            )
        )

        print()
        print(
            "FINAL RESULT:"
        )

        print(result)

    finally:

        db.close()


if __name__ == "__main__":
    main()
