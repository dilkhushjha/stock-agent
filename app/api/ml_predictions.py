from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.database import get_db
from app.models.ml_prediction import MLPrediction
from app.models.stock import Stock


router = APIRouter(
    prefix="/ml-predictions",
    tags=["ML Predictions"],
)


@router.get("/")
def get_ml_predictions(
    limit: int = 50,
    db: Session = Depends(get_db),
):
    predictions = db.scalars(
        select(MLPrediction)
        .join(
            Stock,
            MLPrediction.stock_id == Stock.id,
        )
        .order_by(
            MLPrediction.prediction_time.desc()
        )
        .limit(limit)
    ).all()

    return [
        {
            "id": prediction.id,
            "stock_id": prediction.stock_id,
            "symbol": (
                db.get(
                    Stock,
                    prediction.stock_id,
                ).symbol
                if prediction.stock_id
                else None
            ),
            "prediction_time": prediction.prediction_time,
            "market_timestamp": prediction.market_timestamp,
            "price_at_prediction": prediction.price_at_prediction,

            "predicted_return_5d": (
                prediction.predicted_return_5d
            ),

            "predicted_return_10d": (
                prediction.predicted_return_10d
            ),

            "predicted_return_20d": (
                prediction.predicted_return_20d
            ),

            "signal": prediction.signal,
            "confidence": prediction.confidence,

            "model_name": prediction.model_name,
            "model_version": prediction.model_version,
        }
        for prediction in predictions
    ]