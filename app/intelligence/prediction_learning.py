from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ml_prediction import MLPrediction
from app.models.prediction_feedback import PredictionFeedback


class PredictionLearning:
    """Turn evaluated predictions into an auditable reliability signal.

    This does not retrain the ML model directly. It adjusts future opportunity
    confidence based on how the model has actually performed for the stock.
    """

    @staticmethod
    def stock_reliability(db: Session, stock_id: int, horizon: str = "5d", days: int = 180) -> dict:
        cutoff = datetime.utcnow() - timedelta(days=max(7, days))
        rows = db.scalars(
            select(PredictionFeedback)
            .join(MLPrediction, MLPrediction.id == PredictionFeedback.prediction_id)
            .where(
                MLPrediction.stock_id == stock_id,
                PredictionFeedback.horizon == horizon,
                PredictionFeedback.evaluated_at >= cutoff,
            )
            .order_by(PredictionFeedback.evaluated_at.desc())
            .limit(100)
        ).all()

        if not rows:
            return {
                "samples": 0,
                "target_hit_rate_pct": None,
                "direction_accuracy_pct": None,
                "reliability_score": None,
                "feedback_bias": 0.0,
            }

        target_rate = sum(int(r.target_hit) for r in rows) / len(rows)
        direction_rate = sum(int(r.direction_correct) for r in rows) / len(rows)
        # Target achievement matters most for the product's entry objective.
        reliability = (target_rate * 0.65 + direction_rate * 0.35) * 100
        # Positive history gives a modest boost; poor history creates a penalty.
        bias = max(-10.0, min(10.0, (reliability - 50.0) * 0.20))

        return {
            "samples": len(rows),
            "target_hit_rate_pct": round(target_rate * 100, 2),
            "direction_accuracy_pct": round(direction_rate * 100, 2),
            "reliability_score": round(reliability, 2),
            "feedback_bias": round(bias, 2),
        }
