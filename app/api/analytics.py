from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.data.database import get_db
from app.intelligence.historical_stats import (
    HistoricalStatsService,
)


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)


@router.get("/historical/{symbol}")
def historical_statistics(
    symbol: str,
    db: Session = Depends(get_db),
):

    try:

        return HistoricalStatsService.get_stock_statistics(
            db=db,
            symbol=symbol.upper(),
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )