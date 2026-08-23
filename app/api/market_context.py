from fastapi import APIRouter

from app.intelligence.market_context import (
    MarketContext,
)


router = APIRouter(
    prefix="/market-context",
    tags=["Market Context"],
)


@router.get("/")
def get_market_context():

    return MarketContext.get()