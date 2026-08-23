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

    stock_columns = {
        "exchange": "VARCHAR(10)",
        "isin": "VARCHAR(20)",
        "series": "VARCHAR(10)",
        "macro_economic_sector": "VARCHAR(100)",
        "sector": "VARCHAR(100)",
        "industry": "VARCHAR(150)",
        "basic_industry": "VARCHAR(200)",
        "sector_code": "VARCHAR(30)",
        "industry_code": "VARCHAR(30)",
        "basic_industry_code": "VARCHAR(40)",
        "sector_source": "VARCHAR(50)",
        "classification_updated_at": "DATETIME",
    }
    for column_name, column_type in stock_columns.items():
        _add_missing_column("stocks", column_name, column_type)

    # Existing rows predate the canonical exchange fields.
    with engine.begin() as connection:
        connection.execute(text("UPDATE stocks SET exchange='NSE' WHERE exchange IS NULL OR exchange=''"))
