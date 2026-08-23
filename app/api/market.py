from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.data.database import get_db
from app.data.market.market_ingestion import (
    MarketDataIngestionService,
)
from app.intelligence.prediction_service import (
    PredictionService,
)


router = APIRouter(
    prefix="/market",
    tags=["Market"],
)


# ============================================================
# MARKET DATA INGESTION
# ============================================================

@router.post("/ingest")
def ingest_market_data(
    symbol: str,
    period: str = "1y",
    interval: str = "1d",
    db: Session = Depends(get_db),
):
    return MarketDataIngestionService.ingest_history(
        db=db,
        symbol=symbol,
        period=period,
        interval=interval,
    )


# ============================================================
# ML PREDICTION — SINGLE STOCK
# ============================================================

@router.get("/prediction/{symbol}")
def get_stock_prediction(
    symbol: str,
    db: Session = Depends(get_db),
):
    result = PredictionService.predict_stock(
        db=db,
        symbol=symbol,
    )

    if result.get("status") == "NOT_FOUND":
        raise HTTPException(
            status_code=404,
            detail=f"Stock {symbol.upper()} not found.",
        )

    return result


# ============================================================
# ML PREDICTIONS — ENTIRE UNIVERSE
# ============================================================

@router.get("/predictions")
def get_all_predictions(
    db: Session = Depends(get_db),
):
    return {
        "status": "OK",
        "predictions": (
            PredictionService
            .predict_all_stocks(db)
        ),
    }

# ============================================================
# DASHBOARD PREDICTION SUMMARY
# ============================================================


@router.get("/dashboard")
def get_dashboard_predictions(
    db: Session = Depends(get_db),
):
    predictions = (
        PredictionService
        .predict_all_stocks(db)
    )

    usable = [
        prediction
        for prediction in predictions
        if prediction.get("status") == "OK"
    ]

    buy_count = sum(
        1
        for prediction in usable
        if prediction.get("signal") == "BUY"
    )

    hold_count = sum(
        1
        for prediction in usable
        if prediction.get("signal") == "HOLD"
    )

    sell_count = sum(
        1
        for prediction in usable
        if prediction.get("signal") == "SELL"
    )

    ranked = sorted(
        usable,
        key=lambda item: item.get(
            "predicted_return",
            0,
        ),
        reverse=True,
    )

    return {
        "status": "OK",

        "market_summary": {
            "stocks_analyzed": len(usable),
            "buy": buy_count,
            "hold": hold_count,
            "sell": sell_count,
        },

        "top_opportunities": ranked[:10],

        "top_risks": sorted(
            usable,
            key=lambda item: item.get(
                "predicted_return",
                0,
            ),
        )[:10],

        "predictions": predictions,
    }
