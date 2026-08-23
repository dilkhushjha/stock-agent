from sqlalchemy import select

from app.models.stock import Stock
from app.ml.prediction_engine import MLPredictionEngine


DEFAULT_BATCH_SIZE = 200


def predict_stock_batch(db, offset: int, batch_size: int = DEFAULT_BATCH_SIZE):
    """Predict only one slice of the active NSE universe.

    The scheduler rotates the offset so a multi-thousand-stock universe is covered
    continuously without trying to calculate every stock every 15 minutes.
    """
    stocks = db.scalars(
        select(Stock)
        .where(Stock.is_active.is_(True), Stock.exchange == "NSE")
        .order_by(Stock.symbol)
        .offset(max(0, offset))
        .limit(max(1, batch_size))
    ).all()

    engine = MLPredictionEngine(db)
    engine.load_model_artifact()
    results = []
    failures = []
    for stock in stocks:
        if stock.symbol in engine.EXCLUDED_SYMBOLS:
            continue
        try:
            results.append(engine.predict_stock(stock))
        except Exception as exc:
            failures.append({"symbol": stock.symbol, "error": str(exc)})

    return {
        "offset": offset,
        "batch_size": len(stocks),
        "successful": len(results),
        "failed": len(failures),
        "results": results,
        "failures": failures,
    }
