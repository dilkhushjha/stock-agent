from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from sqlalchemy.orm import Session

from app.data.database import get_db

from app.intelligence.fundamentals import (
    FundamentalsService,
)


router = APIRouter(
    prefix="/fundamentals",
    tags=["Fundamentals"],
)


@router.post("/{symbol}/refresh")
def refresh_fundamentals(
    symbol: str,
    db: Session = Depends(get_db),
):

    try:

        return FundamentalsService.update_stock(
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
