from fastapi import APIRouter

from app.intelligence.graph_engine import (
    MarketGraph,
)


router = APIRouter(
    prefix="/graph",
    tags=["Market Graph"],
)

graph = MarketGraph()


@router.get("/{source}")
def get_market_impacts(
    source: str,
    direction: str = "UP",
):

    return {
        "source": source.upper(),
        "direction": direction.upper(),
        "impacts": graph.calculate_impact(
            source,
            direction,
        ),
    }