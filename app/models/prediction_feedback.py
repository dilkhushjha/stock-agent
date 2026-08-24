from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint

from app.data.database import Base


class PredictionFeedback(Base):
    """Auditable outcome record used to learn which forecasts actually worked."""

    __tablename__ = "prediction_feedback"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer, ForeignKey("ml_predictions.id"), nullable=False, index=True)
    horizon = Column(String(10), nullable=False)
    predicted_return_pct = Column(Float, nullable=False)
    actual_return_pct = Column(Float, nullable=False)
    target_hit = Column(Integer, nullable=False, default=0)
    direction_correct = Column(Integer, nullable=False, default=0)
    feedback = Column(String(20), nullable=False)
    evaluated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("prediction_id", "horizon", name="uq_prediction_feedback_horizon"),
    )
