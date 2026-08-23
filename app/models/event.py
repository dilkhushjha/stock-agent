from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
)

from app.data.database import Base


class MarketEvent(Base):
    __tablename__ = "market_events"

    id = Column(Integer, primary_key=True, index=True)

    news_id = Column(
        Integer,
        ForeignKey("news_articles.id"),
        nullable=False,
        index=True,
    )

    event_type = Column(
        String(100),
        nullable=False,
        index=True,
    )

    title = Column(
        String(500),
        nullable=False,
    )

    description = Column(
        Text,
        nullable=True,
    )

    entity = Column(
        String(200),
        nullable=True,
        index=True,
    )

    sector = Column(
        String(100),
        nullable=True,
        index=True,
    )

    direction = Column(
        String(30),
        nullable=True,
    )

    impact = Column(
        String(30),
        nullable=True,
    )

    confidence = Column(
        Float,
        nullable=True,
    )

    time_horizon = Column(
        String(50),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )