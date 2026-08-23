from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.data.database import get_db
from app.intelligence.nse_classification import NSEClassificationService

router = APIRouter(prefix="/classification", tags=["Classification"])


@router.post("/sync")
def sync_nse_classification(
    limit: int | None = Query(default=None, ge=1, le=2500),
    db: Session = Depends(get_db),
):
    """Populate official NSE Indices sector/industry fields for active equities."""
    return NSEClassificationService.sync(db, limit=limit)
