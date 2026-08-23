from fastapi import APIRouter

from app.agent.orchestrator import MarketAgent

router = APIRouter(prefix="/agent", tags=["Live Agent"])


@router.post("/run-now")
def run_now():
    """Run the same live news -> event -> opportunity pipeline used by the scheduler."""
    return MarketAgent().run_news_cycle()
