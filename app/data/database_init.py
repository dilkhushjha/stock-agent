from sqlalchemy import inspect, text

from app.data.database import Base, engine

from app.models import *  # noqa: F401,F403


def _add_missing_column(table_name: str, column_name: str, column_type: str):
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name not in columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    f'ALTER TABLE "{table_name}" '
                    f'ADD COLUMN "{column_name}" {column_type}'
                )
            )


def initialize_database():
    Base.metadata.create_all(bind=engine)

    _add_missing_column("market_events", "event_date", "DATETIME")
    _add_missing_column("news_articles", "fingerprint", "VARCHAR(64)")
    _add_missing_column("stocks", "exchange", "VARCHAR(10)")
    _add_missing_column("stocks", "isin", "VARCHAR(20)")
    _add_missing_column("stocks", "series", "VARCHAR(10)")
    _add_missing_column("stocks", "sector_source", "VARCHAR(50)")

    # Existing rows predate the canonical exchange fields.
    with engine.begin() as connection:
        connection.execute(text("UPDATE stocks SET exchange='NSE' WHERE exchange IS NULL OR exchange=''"))
