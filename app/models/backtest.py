from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    DateTime,
    ForeignKey,
)

from app.data.database import Base


class EventOutcome(Base):
    __tablename__ = "event_outcomes"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    event_id = Column(
        Integer,
        ForeignKey("market_events.id"),
        nullable=False,
        index=True,
    )

    stock_id = Column(
        Integer,
        ForeignKey("stocks.id"),
        nullable=False,
        index=True,
    )

    event_price = Column(
        Float,
        nullable=True,
    )

    return_1d = Column(
        Float,
        nullable=True,
    )

    return_5d = Column(
        Float,
        nullable=True,
    )

    return_20d = Column(
        Float,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )