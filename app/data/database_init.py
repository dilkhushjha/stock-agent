from sqlalchemy import inspect, text

from app.data.database import Base, engine

# Import all models so SQLAlchemy knows about every table.
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

    # create_all() does not alter existing SQLite tables. Keep this migration
    # lightweight so existing user databases continue working after model changes.
    _add_missing_column("market_events", "event_date", "DATETIME")
