from app.data.database import SessionLocal

from app.data.fundamentals.fundamentals_ingestion import (
    FundamentalsIngestionService,
)


def main():

    db = SessionLocal()

    try:

        result = (
            FundamentalsIngestionService
            .ingest_all(db)
        )

        print()
        print("FINAL RESULT:")
        print(result)

    finally:

        db.close()


if __name__ == "__main__":
    main()