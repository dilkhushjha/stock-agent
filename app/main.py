from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.scheduler import start_scheduler, stop_scheduler
from app.api.alerts import router as alerts_router
from app.api.fundamentals import router as fundamentals_router
from app.api.graph import router as graph_router
from app.api.exposure import router as exposure_router
from app.api.signals import router as signals_router
from app.api.predictions import router as predictions_router
from app.api.regime import router as regime_router
from app.api.market_context import router as market_context_router
from app.api.sector import router as sector_router
from app.api.ml_predictions import router as ml_predictions_router
from app.api.backtest import router as backtest_router
from app.api.agent import router as agent_router
from app.api.recommendations import router as recommendations_router
from app.data.database_init import initialize_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Indian Market Intelligence Agent",
    description="AI-powered Indian stock market intelligence and proactive opportunity alerts",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fundamentals_router)
app.include_router(graph_router)
app.include_router(exposure_router)
app.include_router(signals_router)
app.include_router(predictions_router)
app.include_router(regime_router)
app.include_router(market_context_router)
app.include_router(sector_router)
app.include_router(ml_predictions_router)
app.include_router(alerts_router)
app.include_router(backtest_router)
app.include_router(agent_router)
app.include_router(recommendations_router)


@app.get("/")
def root():
    return {
        "name": "Indian Market Intelligence Agent",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
