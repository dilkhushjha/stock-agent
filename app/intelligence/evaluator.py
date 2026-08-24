from __future__ import annotations

from datetime import datetime, timedelta
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market_data import MarketData
from app.models.ml_prediction import MLPrediction
from app.models.prediction_feedback import PredictionFeedback


class PredictionEvaluator:
    """Evaluate forecasts and register whether each target was actually achieved."""

    HORIZONS = {
        "5d": (5, "predicted_return_5d", "actual_return_5d"),
        "10d": (10, "predicted_return_10d", "actual_return_10d"),
        "20d": (20, "predicted_return_20d", "actual_return_20d"),
    }

    @classmethod
    def _register_feedback(cls, db: Session, prediction: MLPrediction, horizon: str, predicted: float, actual: float):
        # A forecast target is considered hit when price reaches or exceeds the
        # predicted move in the predicted direction. This is deliberately
        # auditable rather than using a vague "close enough" score.
        if predicted > 0:
            target_hit = actual >= predicted
        elif predicted < 0:
            target_hit = actual <= predicted
        else:
            target_hit = abs(actual) < 0.25

        direction_correct = (predicted >= 0) == (actual >= 0)
        if target_hit:
            feedback = "POSITIVE"
        elif direction_correct:
            feedback = "PARTIAL"
        else:
            feedback = "NEGATIVE"

        existing = db.scalar(
            select(PredictionFeedback).where(
                PredictionFeedback.prediction_id == prediction.id,
                PredictionFeedback.horizon == horizon,
            )
        )
        if existing is None:
            db.add(PredictionFeedback(
                prediction_id=prediction.id,
                horizon=horizon,
                predicted_return_pct=round(predicted, 4),
                actual_return_pct=round(actual, 4),
                target_hit=int(target_hit),
                direction_correct=int(direction_correct),
                feedback=feedback,
            ))
        else:
            existing.predicted_return_pct = round(predicted, 4)
            existing.actual_return_pct = round(actual, 4)
            existing.target_hit = int(target_hit)
            existing.direction_correct = int(direction_correct)
            existing.feedback = feedback

    @classmethod
    def evaluate(cls, db: Session):
        predictions = db.scalars(
            select(MLPrediction)
            .order_by(MLPrediction.prediction_time.asc())
            .limit(5000)
        ).all()

        evaluated = 0
        partially_evaluated = 0
        positive = 0
        negative = 0

        for prediction in predictions:
            if not prediction.price_at_prediction or not prediction.market_timestamp:
                continue

            changed = False
            for name, (days, predicted_field, actual_field) in cls.HORIZONS.items():
                predicted = getattr(prediction, predicted_field)
                if predicted is None:
                    continue
                actual = getattr(prediction, actual_field)

                if actual is None:
                    target_time = prediction.market_timestamp + timedelta(days=days)
                    if datetime.utcnow() < target_time:
                        continue

                    future_price = db.scalar(
                        select(MarketData.close)
                        .where(
                            MarketData.stock_id == prediction.stock_id,
                            MarketData.timestamp >= target_time,
                        )
                        .order_by(MarketData.timestamp.asc())
                        .limit(1)
                    )
                    if future_price is None:
                        continue

                    actual = (float(future_price) / float(prediction.price_at_prediction) - 1) * 100
                    setattr(prediction, actual_field, round(actual, 4))
                    changed = True

                cls._register_feedback(db, prediction, name, float(predicted), float(actual))
                feedback = db.scalar(select(PredictionFeedback).where(
                    PredictionFeedback.prediction_id == prediction.id,
                    PredictionFeedback.horizon == name,
                ))
                if feedback:
                    positive += feedback.feedback == "POSITIVE"
                    negative += feedback.feedback == "NEGATIVE"

            if changed:
                partially_evaluated += 1

            if prediction.actual_return_20d is not None:
                prediction.evaluated = 1
                evaluated += 1

        db.commit()
        return {
            "checked": len(predictions),
            "partially_evaluated": partially_evaluated,
            "evaluated": evaluated,
            "positive_feedback": positive,
            "negative_feedback": negative,
        }

    @classmethod
    def summary(cls, db: Session, days: int = 90):
        cutoff = datetime.utcnow() - timedelta(days=max(1, days))
        rows = db.scalars(
            select(MLPrediction)
            .where(
                MLPrediction.prediction_time >= cutoff,
                MLPrediction.actual_return_5d.is_not(None),
            )
            .order_by(MLPrediction.prediction_time.desc())
            .limit(10000)
        ).all()

        result = {"period_days": days, "evaluated_predictions": len(rows), "horizons": {}}
        for name, (_, predicted_field, actual_field) in cls.HORIZONS.items():
            pairs = [
                (float(getattr(row, predicted_field)), float(getattr(row, actual_field)))
                for row in rows
                if getattr(row, predicted_field) is not None and getattr(row, actual_field) is not None
            ]
            if not pairs:
                result["horizons"][name] = {"samples": 0}
                continue
            directional = sum((p >= 0) == (a >= 0) for p, a in pairs) / len(pairs)
            mae = mean(abs(p - a) for p, a in pairs)
            result["horizons"][name] = {
                "samples": len(pairs),
                "directional_accuracy": round(directional * 100, 2),
                "mae_pct_points": round(mae, 4),
                "average_predicted_return_pct": round(mean(p for p, _ in pairs), 4),
                "average_actual_return_pct": round(mean(a for _, a in pairs), 4),
            }
        return result
