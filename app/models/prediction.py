from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
)

from app.data.database import Base


class SignalPrediction(Base):

    __tablename__ = "signal_predictions"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    stock_id = Column(
        Integer,
        ForeignKey("stocks.id"),
        nullable=False,
        index=True,
    )

    article_id = Column(
        Integer,
        ForeignKey("news_articles.id"),
        nullable=True,
        index=True,
    )

    factor = Column(
        String(100),
        nullable=False,
    )

    direction = Column(
        String(20),
        nullable=False,
    )

    predicted_impact = Column(
        String(20),
        nullable=False,
    )

    signal_score = Column(
        Float,
        nullable=False,
    )

    confidence = Column(
        Float,
        nullable=True,
    )

    price_at_signal = Column(
        Float,
        nullable=True,
    )

    signal_time = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    return_1h = Column(
        Float,
        nullable=True,
    )

    return_1d = Column(
        Float,
        nullable=True,
    )

    return_3d = Column(
        Float,
        nullable=True,
    )

    return_5d = Column(
        Float,
        nullable=True,
    )

    evaluated = Column(
        Integer,
        default=0,
        nullable=False,
    )