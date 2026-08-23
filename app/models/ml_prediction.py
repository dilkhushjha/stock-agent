from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)

from app.data.database import Base


class MLPrediction(Base):

    __tablename__ = "ml_predictions"

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

    # ---------------------------------------------------------
    # Prediction timestamp
    # ---------------------------------------------------------

    prediction_time = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    market_timestamp = Column(
        DateTime,
        nullable=False,
        index=True,
    )

    # ---------------------------------------------------------
    # Price
    # ---------------------------------------------------------

    price_at_prediction = Column(
        Float,
        nullable=False,
    )

    # ---------------------------------------------------------
    # ML forecasts
    # ---------------------------------------------------------

    predicted_return_5d = Column(
        Float,
        nullable=True,
    )

    predicted_return_10d = Column(
        Float,
        nullable=True,
    )

    predicted_return_20d = Column(
        Float,
        nullable=True,
    )

    # ---------------------------------------------------------
    # Trading signal
    # ---------------------------------------------------------

    signal = Column(
        String(20),
        nullable=False,
    )

    confidence = Column(
        Float,
        nullable=False,
    )

    # ---------------------------------------------------------
    # Model identification
    # ---------------------------------------------------------

    model_name = Column(
        String(100),
        nullable=True,
    )

    model_version = Column(
        String(100),
        nullable=True,
    )

    # ---------------------------------------------------------
    # Evaluation
    # ---------------------------------------------------------

    actual_return_5d = Column(
        Float,
        nullable=True,
    )

    actual_return_10d = Column(
        Float,
        nullable=True,
    )

    actual_return_20d = Column(
        Float,
        nullable=True,
    )

    evaluated = Column(
        Integer,
        default=0,
        nullable=False,
    )

    # ---------------------------------------------------------
    # Prevent duplicate prediction for the same stock/date
    # ---------------------------------------------------------

    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "market_timestamp",
            name="uq_ml_prediction_stock_timestamp",
        ),
    )
