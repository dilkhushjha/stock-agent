from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from app.data.database import get_db

from app.intelligence.signal_engine import (
    SignalEngine,
)


router = APIRouter(
    prefix="/signals",
    tags=["Signals"],
)


@router.get("/factor/{factor}")
def factor_signal(
    factor: str,
    direction: str = "UP",
    db: Session = Depends(get_db),
):

    engine = SignalEngine()

    return {
        "factor": factor.upper(),
        "direction": direction.upper(),
        "signals": engine.generate(
            db=db,
            factor=factor,
            direction=direction,
        ),
    }