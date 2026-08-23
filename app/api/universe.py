from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.data.database import get_db
from app.intelligence.market_data_sync import MarketDataSyncService
from app.intelligence.nse_universe import NSEUniverseService

router = APIRouter(prefix="/universe", tags=["Universe"])


@router.post("/sync")
def sync_nse_universe(db: Session = Depends(get_db)):
    """Import the current NSE equity master before broad recommendation scans."""
    return NSEUniverseService.sync(db)


@router.post("/market-data/bootstrap")
def bootstrap_market_data(
    history_days: int = Query(365, ge=30, le=3650),
    limit: int | None = Query(None, ge=1, le=5000),
    workers: int = Query(8, ge=1, le=16),
    db: Session = Depends(get_db),
):
    """Populate historical OHLCV for the broad NSE universe.

    This is an explicit bootstrap operation, not a live scheduler job. Use limit
    for a controlled first run, then remove it to process the full universe.
    """
    service = MarketDataSyncService()
    return service.sync(db, history_days=history_days, limit=limit, workers=workers)
