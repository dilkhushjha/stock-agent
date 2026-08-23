from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.data.database import get_db
from app.intelligence.pipeline_diagnostics import OpportunityPipelineDiagnostics
from app.intelligence.run_backtest import BacktestRunner
from app.models.event import MarketEvent
from app.models.market_data import MarketData
from app.models.stock import Stock

router = APIRouter(prefix="/backtest", tags=["Backtest"])


@router.get("/data-health")
def data_health(db: Session = Depends(get_db)):
    event_count = db.scalar(select(func.count(MarketEvent.id))) or 0
    stock_count = db.scalar(select(func.count(Stock.id))) or 0
    market_rows = db.scalar(select(func.count(MarketData.id))) or 0
    first_market = db.scalar(select(func.min(MarketData.timestamp)))
    last_market = db.scalar(select(func.max(MarketData.timestamp)))
    first_event = db.scalar(select(func.min(MarketEvent.event_date)))
    last_event = db.scalar(select(func.max(MarketEvent.event_date)))

    return {
        "ready": event_count > 0 and stock_count > 0 and market_rows > 0,
        "events": event_count,
        "stocks": stock_count,
        "market_data_rows": market_rows,
        "market_data_range": {"from": first_market, "to": last_market},
        "event_range": {"from": first_event, "to": last_event},
    }


@router.get("/diagnose/{event_id}")
def diagnose_event(event_id: int, db: Session = Depends(get_db)):
    return OpportunityPipelineDiagnostics.inspect_event(db, event_id)


@router.post("/run")
def run_backtest(
    limit: int = Query(100, ge=1, le=5000),
    event_type: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return BacktestRunner.run(db, limit=limit, event_type=event_type)
