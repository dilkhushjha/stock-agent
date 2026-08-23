
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.database import get_db
from app.models.ml_prediction import MLPrediction
from app.models.stock import Stock


router = APIRouter(
    prefix="/predictions",
    tags=["Predictions"],
)


@router.get("/")
def get_predictions(
    limit: int = Query(
        50,
        ge=1,
        le=200,
    ),
    db: Session = Depends(get_db),
):
    """
    Return latest ML predictions with stock symbols.
    """

    rows = db.execute(
        select(
            MLPrediction,
            Stock.symbol,
        )
        .join(
            Stock,
            MLPrediction.stock_id == Stock.id,
        )
        .order_by(
            MLPrediction.prediction_time.desc()
        )
        .limit(limit)
    ).all()

    results = []

    for prediction, symbol in rows:

        results.append(
            {
                "id": prediction.id,
                "stock_id": prediction.stock_id,
                "symbol": symbol,

                "prediction_time": (
                    prediction.prediction_time
                ),

                "price_at_prediction": (
                    prediction.price_at_prediction
                ),

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
        )

    return results
